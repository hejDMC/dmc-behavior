'''
Auditory two-alternative forced (?) choice task with tone clouds
December 2022 - FJ

Updated script from spring 2022

Aim:
    Animals are trained to perform an auditory two-alternative forced choice task
     by presenting either a high or a low tone clouds, the animals are then asked to move the wheel in the
     correct direction

    In correct trials, a water reward is given (depending on overall performance between 3ul - 1.5 ul)
    In incorrect trials, a white noise is played
    In ommision trials, a white noise is played

    Tones clouds are either comprised of either high, low or intermediate tones.
    Depending of task stage, the difficulties differ. On easy trials the tones clouds are comprised to 100 % of tones
    from the target frequency range (either high or low), increasing difficulties sample more tones of the two
    non-target octaves (ratios are 85/15, 70/30 and 60/40).

    From Coen et al., 2021: the turning threshold for a decision was 30 degrees in wheel turning.

    Training stages are:
    Stage 0
        --> **Aim** is to train animals that moving the wheel is important for obtaining reward,
            ideally animals learn already that tones are important too (stim-response), but this feels a bit unlikely.
        --> **Implementation:** Give 3 ul reward everytime wheel is moved in response window, irrespective of direction.
            Wheel gain is adjusted, once the animal has performed more than 200 trials in one session, it is set to full
            (before it's half, so we encourage more rigourus movement). The response window likewise decreases to double
            the task response_window (in the very beginning it's 4x the duration)
        --> **Criteria** to advance should reflect that animals understood that moving the wheel is *somehow* important.
            Min. two days of training in that stage plus a minimum of 200 trials on two successive days.

    Stage 1:
        --> **Aim** is to train animals to learn the basic task structure of moving *either* left or right upon high/low tone cloud presentation.
        --> **Implementation:** Give reward for correct trials and play white noise in omission/incorrect trials. Reward size is dynamically set between 3 ul and 1.5 ul (de-/increase by 0.1 depending on if 1 ml reward was consumed the previous session). Soft, motivational debiasing: Higher likelyhood of repeat trials, plus double reward size is anti-bias side.
        --> **Criteria**

'''



##
# import modules
import RPi.GPIO as GPIO
import sys, socket
import numpy as np
import pandas as pd
import sounddevice as sd
import time
import random
import threading
from datetime import datetime
from sklearn import preprocessing
from utils.encoder import Encoder
from utils.sync_pulse import Sync_Pulse
from utils.utils import get_today, check_first_day, get_stage, make_exp_dir, check_dir, start_option, \
    plot_behavior_terminal
from utils.utils_audio import pitch_to_frequency, weighted_octave_choice, create_tone
from utils.utilsIO import load_droid_setting, load_task_prefs, load_response_matrix, store_meta_data, store_pref_data,\
    store_reaction_times, load_pump_calibration
from utils.utils_2afc import check_stage_4_advance, check_ready_for_experiment, get_bias_correction

##

class TriggerPulse(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.droid_settings = load_droid_setting()
        self.trigger_rate = self.droid_settings['base_params']['camera_trigger_rate']  # in Hz
        self.trigger_pin = self.droid_settings['pin_map']['OUT']['trigger_camera']
        self.trigger_state = 0
        self.fn = exp_dir.joinpath(f'{get_today()}_camera_pulse_data.csv')
        self.stop = False

    def write_camera_data(self):
        with open(self.fn, "a") as log:
            log.write("{0},{1}\n".format(time.time(), self.trigger_state))

    def pull_trigger(self):
        self.trigger_state = 1
        GPIO.setup(self.trigger_pin, GPIO.OUT)
        GPIO.output(self.trigger_pin, self.trigger_state)
        self.write_camera_data()
        self.trigger_state = 0
        GPIO.output(self.trigger_pin, self.trigger_state)
        self.write_camera_data()
        time.sleep(1/self.trigger_rate)

    def run(self):
        while not self.stop:
            # Loop this infinitely until stop
            self.pull_trigger()

class RotaryRecorder(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.droid_settings = load_droid_setting()
        self.rotary_rate = self.droid_settings['base_params']['rotary_rate']  # Hz for sampling
        self.animal_dir = animal_dir
        self.fn = exp_dir.joinpath(f'{get_today()}_rotary_data.csv')

        # get pin info from droid settings and initialize pins (GPIO numbers)
        # set encoder parameters and initialize pins (GPIO numbers!)
        self.encoder_left = self.droid_settings['pin_map']['IN']['encoder_left_rec']  # pin of left encoder (green wire)
        self.encoder_right = self.droid_settings['pin_map']['IN']['encoder_right_rec']  # pin of right encoder (gray wire)
        self.encoder_data = Encoder(self.encoder_left, self.encoder_right)
        # self.wheel_position = self.encoder_data.getValue()

        self.stop = False

    def write_sync_data(self):

        self.wheel_position = self.encoder_data.getValue()
        with open(self.fn, "a") as log:
            log.write("{0},{1}\n".format(time.time(), str(self.wheel_position)))  #  todo: 0: time_stamp, 1: 2p sync_pulse
            time.sleep(1/self.rotary_rate)

    def run(self):
        while not self.stop:
            # Loop this infinitely until stop
            self.write_sync_data()


class SyncRecorder(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.droid_settings = load_droid_setting()
        self.sync_rate = self.droid_settings['base_params']['2p_sync_rate']  # Hz for sampling, needs to be at least twice as high as 2p sync freq. (Nyquist)
        self.animal_dir = animal_dir
        self.fn = exp_dir.joinpath(f'{get_today()}_sync_pulse_data.csv')

        # get pin info from droid settings and initialize pins (GPIO numbers)
        self.sync_pin = self.droid_settings['pin_map']['IN']['microscope_sync']
        self.sync_pulse = Sync_Pulse(self.sync_pin)
        self.stop = False

    def write_sync_data(self):
        with open(self.fn, "a") as log:
            log.write("{0},{1}\n".format(time.time(), str(self.sync_pulse.get_value())))  #  todo: 0: time_stamp, 1: 2p sync_pulse
            time.sleep(1/self.sync_rate)

    def run(self):
        while not self.stop:
            # Loop this infinitely until stop
            self.write_sync_data()


class Auditory2AFC(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        # load pref files

        self.droid_settings = load_droid_setting()  # general paramters (e.g. pin layout map and sampling rates used)
        self.task_prefs = load_task_prefs(procedure)  # task specifics (e.g. tones used and their duration)
        self.first_day = check_first_day(animal_dir, procedure)
        # get current stage
        self.stage = get_stage(animal_dir, procedure, self.first_day)  # current stage of the animal
        self.stage_advance = False  # set this boolean to true if animal can advance a stage
        if self.stage <= 1:
            self.bias_correction = get_bias_correction(animal_dir, self.first_day)
        else:
            self.bias_correction = False
        self.bias_counter = 0  # bias counter to avoid that animals develop a bias to higher rewarded side
        self.bias_counter_max = self.task_prefs['task_prefs']['bias_counter_max']

        # set task parameters
        # octave params and create cloud arrays
        self.l_oct = self.task_prefs['task_prefs']['low_octave']  # low octave in pitch (start pitch, end pitch, num_pitch)
        self.m_oct = self.task_prefs['task_prefs']['middle_octave']  # middle octave in pitch (start pitch, end pitch, num_pitch)
        self.h_oct = self.task_prefs['task_prefs']['high_octave']  # high octave in pitch (start pitch, end pitch, num_pitch)
        self.low_octave = np.linspace(self.l_oct[0], self.l_oct[1], self.l_oct[2])
        self.middle_octave = np.linspace(self.m_oct[0], self.m_oct[1], self.m_oct[2])
        self.high_octave = np.linspace(self.h_oct[0], self.h_oct[1], self.h_oct[2])
        # create array with octaves
        self.tones_arr = self.low_octave
        self.tones_arr = np.vstack([self.tones_arr, self.middle_octave])
        self.tones_arr = np.vstack([self.tones_arr, self.high_octave])
        self.tone_duration = self.task_prefs['task_prefs']['tone_duration']  # duration of individual tones in cloud in sec
        self.cloud_duration = self.task_prefs['task_prefs']['cloud_duration']  # duration of cloud in sec, needs to be dividable by tone length for now!!
        self.tone_amplitude = self.task_prefs['task_prefs']['tone_amplitude']  # amplitude of tones
        self.cloud_range = self.task_prefs['task_prefs']['cloud_range']
        self.scaler = preprocessing.MinMaxScaler(
            feature_range=(self.cloud_range[0], self.cloud_range[1]))  # scaler for tone cloud to set min max to int16 range

        self.stim_strength = self.task_prefs['task_prefs']['stim_strength']
        self.curr_stim_strength = False  # to be decided eacht trial
        self.fs = self.droid_settings['base_params']['tone_sampling_rate']  # sampling rate for tones presented
        self.tone_fs = self.task_prefs['task_prefs']['tone_fs']  # sampling rate of tones in cloud
        self.num_tones = int(self.cloud_duration * 100 - (self.tone_duration - 1 / self.tone_fs) * 100)  # number of tones in cloud
        self.cloud = []  # ini of tone cloud
        self.cancel_audio = False  # boolean for cancelling audio

        # punishment sound info
        self.punish_sound = self.task_prefs['task_prefs']['punishment_sound']
        self.punish_duration = self.task_prefs['task_prefs']['punishment_sound_duration']
        self.punish_amplitude = self.task_prefs['task_prefs']['punishment_sound_amplitude']
        # other task params
        self.iti = self.task_prefs['task_prefs']['inter_trial_interval']
        self.response_window = self.task_prefs['task_prefs']['response_window']

        # set pump parameters and initialize pin (GPIO numbers!)
        self.pump_log = exp_dir.joinpath(f'{get_today()}_pump_data.csv')
        self.reward_min_max = self.task_prefs['task_prefs']['reward_size']  # [max, min] reward size in ul
        self.pump_time = load_pump_calibration()
        self.pump_min_max = [p * self.pump_time for p in self.reward_min_max]  # [max, min] pump duration
        self.pump_duration = self.get_pump_duration()
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.pump = self.droid_settings['pin_map']['OUT']['pump']
        GPIO.setup(self.pump, GPIO.OUT)

        # set encoder parameters and initialize pins (GPIO numbers!)
        self.encoder_left = self.droid_settings['pin_map']['IN']['encoder_left']  # pin of left encoder (green wire)
        self.encoder_right = self.droid_settings['pin_map']['IN']['encoder_right']  # pin of right encoder (gray wire)
        self.encoder_data = Encoder(self.encoder_left, self.encoder_right)
        self.encoder_to_degree = 1024/360  # the encoder has 1024 steps corresponding to 360 degrees
        self.turning_goal = self.encoder_to_degree * self.task_prefs['encoder_specs']['target_degrees']  # threshold in degrees of wheel turn to count as 'choice' - converted into absolute values of 1024 encoder range
        self.rotary_rate = self.droid_settings['base_params']['rotary_rate']  # Hz for sampling
        self.rotary_log = exp_dir.joinpath(f'{get_today()}_rotary_data.csv')


        self.quite_window = self.task_prefs['task_prefs']['quite_window']  # quite window -> mouse needs to hold wheel still for x time, before new trial starts [0] baseline [1] exponential, as in IBL task
        self.quite_jitter = round(self.encoder_to_degree * self.task_prefs['encoder_specs']['quite_jitter'])  # jitter of allowed movements (input from json in degree; then converted into encoder range)
        self.animal_quite = True

        # data logging
        self.trial_data_fn = exp_dir.joinpath(f'{get_today()}_trial_data.csv')
        self.tone_cloud_fn = exp_dir.joinpath(f'{get_today()}_tone_cloud_data.csv')
        self.trial_num = 0
        self.trial_stat = [0, 0, 0]  # number of [correct, incorrect, omission] trials
        self.trial_start = 0
        self.trial_id = 0

        self.tone_played = 0
        self.decision_var = 0
        self.choice = 0
        self.reward_time = 0
        self.curr_iti = 0

        self.correct_hist = []  # history of correct trials for block structure in stage 0
        self.last_trial = 0
        self.decision_history = []  # list of choices 1 for right, -1 for left, 0 for undecided, average of 0 indicates no bias
        self.decision_sd = 0.5

        self.cloud_bool = False
        if self.stage == 0:
            self.turning_goal = int(self.turning_goal / 2)

        self.block = 0  # only in stage 5
        self.block_length = 0
        self.block_counter = 0

        # disengagement boolean
        self.disengage = False
        self.reaction_times = []
        # stop boolean - entered in terminal to terminate session
        self.stop = False
        self.ending_criteria = "manual"  # default ending criteria is "manual", gets overwritten if trial ends based on automatic criteria


    def stage_checker(self):
        # function to check if one advances in stages, to be called at the end of a session
        if self.stage == 0:
            # criteria to advance from stage 0 to stage 1 --> more than 300 correct trials
            if self.trial_stat[0] > 300:
                self.stage_advance = True
                print(">>>>>  FINISHED STAGE " + str(self.stage) + " !!! <<<<<<<<<")
        elif self.stage == 1:  # to advance 80 % correct on left and right side respectively
            right_trials = [c for d, c in zip(self.decision_history, self.correct_hist) if d == 1]  # get right side trials
            left_trials = [c for d, c in zip(self.decision_history, self.correct_hist) if d == -1]  # get right side trials
            if np.mean(right_trials) >= 0.8 and np.mean(left_trials) >= 0.8:
                self.stage_advance = True
                print(">>>>>  FINISHED STAGE " + str(self.stage) + " !!! <<<<<<<<<")
        elif self.stage == 2:
            right_trials = [c for d, c in zip(self.decision_history, self.correct_hist) if
                            d == 1]  # get right side trials
            left_trials = [c for d, c in zip(self.decision_history, self.correct_hist) if
                           d == -1]  # get right side trials
            if np.mean(right_trials) >= 0.75 and np.mean(left_trials) >= 0.75:
                self.stage_advance = True
                print(">>>>>  FINISHED STAGE " + str(self.stage) + " !!! <<<<<<<<<")
        elif self.stage == 3:
            if self.trial_num > 350:  # this criteria feels weird, but in IBL they use 200 trials irrespective of performnce
                self.stage_advance = True
                print(">>>>>  FINISHED STAGE " + str(self.stage) + " !!! <<<<<<<<<")
        elif self.stage == 4:
            self.stage_advance = check_stage_4_advance(animal_dir)

        elif self.stage == 5:
            check_ready_for_experiment(animal_dir)

    def get_pump_duration(self):
        # calculate the pump duration
        if not self.first_day:
            if self.stage == 0:
                pump_duration = self.pump_min_max[0]  # on stage 0, pump duration is always max
            else:  # on later stages dynamically calculate pump time
                pump_data = pd.DataFrame()
                pump_data_header = ["time", "pump_duration"]
                last_exp_day = sorted([day for day in animal_dir.iterdir() if day.is_dir()])[-1]
                last_exp_list = sorted([exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()])
                for exp_dir in last_exp_list:
                    pump_data_fn = exp_dir.joinpath(f'{exp_dir.parts[-2]}_pump_data.csv')
                    if pump_data_fn.exists():
                        temp_df = pd.read_csv(pump_data_fn, names=pump_data_header)
                        pump_data = pd.concat((pump_data, temp_df))
                if pump_data.empty:  # if no previous records of pump duration exist, go for max
                    print('no previous records of pump duration found, defaulting to max')
                    pump_duration = self.pump_min_max[0]  # in ms
                else:
                    if pump_data['pump_duration'].max() == pump_data['pump_duration'].min():  # if not bias correction, all trials with same amount of reward, check if reward size is reduced
                        amount_reward = pump_data['pump_duration'].sum()/self.pump_time
                        prev_pump_duration = pump_data['pump_duration'].min()
                        if amount_reward >= 1000:  # if more than 1 ml reward given reduce pump duration by 0.1 ul = 5 ms;  in IBL task also criteria of min 200 trials, but here animal always needs to do more than 200 trials to get 1000 ul, likewise it will always perform < 200 trials if it received < 1 ml
                            pump_duration = prev_pump_duration - (self.pump_time/10)  # in ms
                        else:
                            pump_duration = prev_pump_duration + (self.pump_time/10)  # in ms
                        if pump_duration > self.pump_min_max[0]:  # max pump duration is 150 ms = 3 ul
                            pump_duration = self.pump_min_max[0]
                        elif pump_duration < self.pump_min_max[1]:  # min pump duration is 75 ms = 1.5 ul
                            pump_duration = self.pump_min_max[1]
                    else:
                        pump_duration = pump_data['pump_duration'].min()  # otherwise, keep reward volume constant
        else:
            pump_duration = self.pump_min_max[0]
        print("pump_duration:" + str(pump_duration))
        return pump_duration
    #
    def get_block(self):

        if self.block == 0:  # first block to be decided
            self.block = random.choice([-1, 1])
            self.block_length = random.randrange(30, 70)
            self.block_counter = 0
        else:
            if self.block == -1:
                self.block = 1
            else:
                self.block = -1
            self.block_length = random.randrange(30, 70)
            self.block_counter = 0
            print(self.block_length)


    def get_trial(self):
        # randomly choose either high vs. low tone trial
        if self.stage < 5:  # no bias before stage 5
            if random.random() < 0.5:
                self.trial_id = 'high'
            else:
                self.trial_id = 'low'
        elif self.stage == 5:
            if self.trial_num <= 90:  # first 90 trials, no bias
                if self.trial_num == 90:
                    self.get_block()
                if random.random() < 0.5:
                    self.trial_id = 'high'
                else:
                    self.trial_id = 'low'
            else:
                if self.block == -1:
                    if random.random() < 0.2:
                        self.trial_id = 'high'
                    else:
                        self.trial_id = 'low'
                elif self.block == 1:
                    if random.random() < 0.8:
                        self.trial_id = 'high'
                    else:
                        self.trial_id = 'low'
                self.block_counter += 1
                print(self.block_counter)
                if self.block_length <= self.block_counter:
                    self.get_block()

        else:
            print("NO STAGE ???")

        return self.trial_id
    #
    def trigger_reward(self):
        # function to open pump for defined duration and log this data
        GPIO.output(self.pump, GPIO.HIGH)
        self.reward_time = 1
        self.data_logger()
        if self.decision_var == self.bias_correction and self.bias_counter <= self.bias_counter_max:  # if the animal choose anti-bias side, give more reward
            curr_pump_duration = int(self.pump_duration * 2)
            self.bias_counter += 1  # only reward first x trials with higher volume
        else:
            curr_pump_duration = int(self.pump_duration)  # the usual case, pump_duration is the default one
        self.pump_logger(curr_pump_duration)
        time.sleep(curr_pump_duration / 1000)
        GPIO.output(self.pump, GPIO.LOW)
        self.reward_time = 0
    #
    def create_tone_cloud(self, tgt_octave, stim_strength):
        # get random tone sequence to be played in cloud
        # tone sequence (irrespective of octave they are drawn from)
        tone_sequence_idx = [random.choice(range(np.shape(self.tones_arr[1])[0])) for i in range(self.num_tones)]
        # draw actual tone_sequence from the respective octaves; prob. to draw from tgt vs. non-tgt octaves depends on stimulus strength
        tone_sequence = np.array([self.tones_arr[weighted_octave_choice(tgt_octave, stim_strength)][idx] for idx in tone_sequence_idx])
        tone_sequence = [pitch_to_frequency(pitch) for pitch in tone_sequence]  # convert the tones (pitches) to frequencies
        tone_cloud_duration = self.fs * self.cloud_duration  # in samples  # duration of tone_cloud
        tone_cloud = np.zeros([int(tone_cloud_duration), len(tone_sequence)])  # pre-allocate
        k = 0
        # save tone cloud
        pd.DataFrame(tone_sequence).T.to_csv(self.tone_cloud_fn, index=False, header=False, mode='a')
        # iterate over each spot in tone_cloud matrix and insert tone at correct time_point
        for i, tone in enumerate(tone_sequence):
            tone_cloud[k:k + int(self.fs * self.tone_duration), i] = create_tone(self.fs, tone, self.tone_duration, self.tone_amplitude)
            k += int(tone_cloud_duration / (((self.tone_duration - 1 / self.tone_fs) * 100) + self.num_tones))
        tone_cloud = tone_cloud.sum(axis=1) // len(tone_sequence)  #2  # create tone_cloud signal to be played
        tone_cloud = tone_cloud.reshape(-1, 1)
        tone_cloud = self.scaler.fit_transform(tone_cloud)
        tone_cloud = tone_cloud.astype(np.int16)
        return tone_cloud
    #
    def play_tone(self, tone, duration, amplitude):
        #
        audio = self.create_tone(int(tone), duration, amplitude)
        # print(str(tone))
        sd.play(audio, self.fs, blocking=True)
    #
    def callback(self, outdata, frames, time, status):
        # callback function for audio stream
        if self.cancel_audio:
            raise sd.CallbackStop()
        outdata[:] = np.column_stack((self.cloud, self.cloud))  # two channels
    #
    def get_target_cloud(self):
        if self.stage <= 1:
            self.curr_stim_strength = self.stim_strength[0]
        elif self.stage == 2:
            # 50/50 chance of getting 100 or 80 stim_strength
            selector = random.choice(np.arange(self.stage))
            if selector == 0:
                self.curr_stim_strength = self.stim_strength[0]  # 100
            else:
                self.curr_stim_strength = self.stim_strength[1]  # 80
        elif self.stage == 3:
            selector = random.choice(np.arange(self.stage))
            if selector == 0:
                self.curr_stim_strength = self.stim_strength[0]  # 100
            elif selector == 1:
                self.curr_stim_strength = self.stim_strength[1]  # 80
            else:
                self.curr_stim_strength = self.stim_strength[2]  # 70
        elif self.stage >= 4:
            selector = random.choice(np.arange(self.stage))
            if selector == 0:
                self.curr_stim_strength = self.stim_strength[0]  # 100
            elif selector == 1:
                self.curr_stim_strength = self.stim_strength[1]  # 80
            elif selector == 3:
                self.curr_stim_strength = self.stim_strength[2]  # 80
            else:
                self.curr_stim_strength = self.stim_strength[3]  # 60
        else:
            print('NOT IMPLEMENTED TO DO HIGHER STAGES THAN STAGE XX !!!')
        if self.trial_id == 'high':
            self.tgt_octave = 2
            # print("before wave creation: " + str(time.time()))
            self.cloud = self.create_tone_cloud(self.tgt_octave, self.curr_stim_strength)
            # print("after wave creation: " + str(time.time()))
        else:
            self.tgt_octave = 0
            # print("before wave creation: " + str(time.time()))
            self.cloud = self.create_tone_cloud(self.tgt_octave, self.curr_stim_strength)
            # print("after wave creation: " + str(time.time()))
        return self.cloud

    def check_quite_window(self, cloud):

        start_pos = self.encoder_data.getValue()  # start position of the wheel
        q_w = self.quite_window[0] + np.random.exponential(self.quite_window[1])
        if q_w > 1.5:
            q_w = 1.5
        quite_time = time.time() + q_w
        while True:
            curr_pos = self.encoder_data.getValue()
            if not self.cloud_bool: # todo this is ugly and not clean
                self.cloud = self.get_target_cloud()
                self.cloud_bool = True
            if curr_pos not in range(start_pos-self.quite_jitter, start_pos+self.quite_jitter):  # the curr_pos of the wheel is out of allowed range, exit and checker function will be called again
                self.animal_quite = False
                break
            elif time.time() > quite_time:  # if animal is still for QW, bool to True and exit --> trial will be initialized
                self.animal_quite = True
                break
            time.sleep(0.001)  # 1 ms sleep, otherwise some threading issue occur
        return self.animal_quite, self.cloud

    def get_trial_id(self):

        if self.stage == 0:
            if len(self.correct_hist) < 3:  # if less than 3 trials, just repeat
                self.trial_id = self.last_trial
            else:
                # check last three trials
                corr_hist = self.correct_hist[-3:]
                corr_sum = np.sum(corr_hist)
                if corr_sum == 3:  # if all were correct, use opposite trial
                    self.correct_hist = []
                    if self.last_trial == 'high':
                        self.trial_id = 'low'
                    else:
                        self.trial_id = 'high'
                else:  # otherwise keep trial
                    self.trial_id = self.last_trial

        elif 0 < self.stage < 4:
            if self.choice == "incorrect" and self.trial_num > 10:  # if previous trial was incorrect, do the debiasing
                self.trial_id = self.debias()
                print("call debias")
            else:  # otherwise just initialize the trial randomly
                self.trial_id = self.get_trial()  # get trial ID

        else:  # drop debiasing after stage 4
            self.trial_id = self.get_trial()

        return self.trial_id

    def calculate_decision(self):  #  , wheel_position, turning_goal):

        # continously stream the wheel_position --> if it crosses threshold (30 degree) mark choice as left/right; otherwise it's "undecided"
        # right turns are positive and left turns are negative --> depends on how you wire the encoder
        self.current_position = self.encoder_data.getValue()
        # self.rotary_logger(self.current_position)
        self.wheel_position = self.current_position - self.wheel_start_position
        if self.wheel_position > self.turning_goal:
            self.decision_var = "right"
        elif self.wheel_position < -self.turning_goal:
            self.decision_var = "left"
        else:
            self.decision_var = "undecided"
        time.sleep(0.001)  # 1 ms sleep, otherwise some threading issue occur
        return self.decision_var

    def choice_evaluation(self):#, trial_id):

        self.decision_var = self.calculate_decision() #self.wheel_position, self.turning_goal) # get the decision from continous stream
        if self.decision_var == "undecided":
            self.choice = "undecided"
            # pass
        elif self.decision_var == self.target_position:
            self.choice = "correct"
        else:
            self.choice = "incorrect"
        return self.decision_var, self.choice
    #
    def data_logger(self): # todo mark debiase trials
        # always add one line to csv file upon event with timestamp for sync
        with open(self.trial_data_fn, "a") as log:
            log.write("{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10}\n".format(time.time(), str(self.trial_num), str(self.trial_start), str(self.trial_id), str(self.curr_stim_strength), str(self.tone_played), str(self.decision_var), str(self.choice), str(self.reward_time), str(self.curr_iti), str(self.block)))  # todo: 0: time_stamp, 1: trial_num, 2: trial_start, 3: trial_type:, 4: tone_played, 5: decision_variable, 6: choice_variable, 7: reward_time, 8: inter-trial-intervall, 10: block

    def pump_logger(self, curr_pump_duration):
        # log pump data to calculate total volume given and number of trials etc.
        # only log data for correct trials, when reward was given
        with open(self.pump_log, "a") as log:
            log.write("{0},{1}\n".format(time.time(), str(curr_pump_duration)))  #  todo: 0: time_stamp, 1: pump_duration

    # def rotary_logger(self, wheel_pos):
    #     if wheel_pos != self.last_wheel_pos:
    #         with open(self.rotary_log, "a") as log:
    #             log.write("{0},{1}\n".format(time.time(), str(wheel_pos)))  #  todo: 0: time_stamp, 1: 2p sync_pulse
    #     self.last_wheel_pos = wheel_pos

    def debias(self):
        # should only be calculated after incorrect trials
        # function for debiasing --> calculate the mean response over the last 10 trials, if animal only goes in one direction, present tones only on other side
        # open trial data file and read the last 10 trials and calculate the average
        hist_list = self.decision_history[-10:]
        hist_mean = np.mean(hist_list)
        debias_val = random.gauss(hist_mean, self.decision_sd)
        if debias_val > 0:  # indicating more right choices
            bias_side = 'right'
            # get the 'opposite' tone to what the bias is, otherwise it would be correct, so if the pairing is high->right, then select the low tone
            tone = list(response_matrix.keys())[list(response_matrix.values()).index(bias_side)]
            if tone == 'high':
                self.trial_id = 'low'
            else:
                self.trial_id = 'high'
        else:
            bias_side = 'left'
            # get the 'opposite' tone to what the bias is, otherwise it would be correct, so if the pairing is high->right, then select the low tone
            tone = list(response_matrix.keys())[list(response_matrix.values()).index(bias_side)]
            if tone == 'high':
                self.trial_id = 'low'
            else:
                self.trial_id = 'high'
        return self.trial_id

    def check_disengage(self):
        sess_median = pd.DataFrame(self.reaction_times).median()  # median of reaction times of session
        roll_median = pd.DataFrame(self.reaction_times).rolling(20).median()  # rolling median (window=20) of reaction times
        if (sess_median[0]*4) < roll_median.iloc[-1][0]:  # check if last roll_median is > 4x the session median todo check if this makes sense, or rather 3x
            self.disengage = True  # set disengage bool to True
        elif roll_median.iloc[-1][0] >= self.response_window:
            self.disengage = True
        else:
            self.disengage = False  # can be reversed (for now..)
        return self.disengage
    #
    def check_trial_end(self):
        if time.time() > time_out:  # max length reach
            mess = "90 min passed -- time limit reached, enter 'stop' and take out animal"
            print(mess)
            self.ending_criteria = "max_time"
            self.stop = True
        elif time.time() > time_out_lt and task.trial_num < low_trial_lim:  # low trial number in first 45 min
            mess = "low number of trials, enter 'stop' and take out animal"
            print(mess)
            self.ending_criteria = "low_trial_num"
            self.send_mail_dummy(animal_id, droid, mess)
            self.stop = True
        # check disengagement
        if time.time() > time_out_lt and self.trial_num > low_trial_lim:
            self.disengage = self.check_disengage()
            if self.disengage:  # disengagement after > 45 min
                mess = "animal is disengaged, please enter 'stop' and take out animal"
                print(mess)
                self.ending_criteria = "disengagement"
                self.stop = True


    def auditory_2afc(self):
        # self.seconds = self.get_seconds()
        self.trial_start = 1
        self.data_logger()
        self.trial_start = 0
        if self.trial_num == 0:  # for first trial of session, randomly choose "last" trial, only for init of task
            self.last_trial = self.get_trial()
        self.trial_id = self.get_trial_id()  # I put this hear as computing the cloud takes some 250 ms
        self.cloud_bool = False

        while True:
            self.animal_quite, self.cloud = self.check_quite_window(self.cloud)  # call the QW checker function, stay in function as long animal holds wheel still, otherwise return and call function again
            if self.animal_quite:  # if animal is quite for quite window length, ini new trial, otherwise stay in loop
                trial_start = time.time()
                self.animal_quite = False
                break

        self.target_position = response_matrix[self.trial_id]
        self.timeout = time.time() + self.response_window  # start a timer at the size of the response window
        self.trial_num += 1

        with sd.OutputStream(samplerate=self.fs, blocksize=len(self.cloud), channels=2, dtype='int16',
                             latency='low', callback=self.callback):
            time.sleep(self.cloud_duration * 2)  # to avoid zero shot trials, stream buffers 2x the cloud duration before tone onset
            self.tone_played = 1
            self.data_logger()
            self.tone_played = 0
            self.wheel_start_position = self.encoder_data.getValue()
            while True:
                self.decision_var, self.choice = self.choice_evaluation()
                if self.choice == "correct":  # if choice was correct
                    self.cancel_audio = True
                    self.trial_stat[0] += 1
                    self.data_logger()
                    self.reaction_times.append(time.time() - trial_start)
                    self.trigger_reward()
                    if self.target_position == 'right':
                        self.decision_history.append(1)
                    else:
                        self.decision_history.append(-1)
                    self.correct_hist.append(1)
                    break
                elif self.choice == "incorrect": # if choice was incorrect
                    self.cancel_audio = True
                    self.trial_stat[1] += 1
                    self.data_logger()
                    self.reaction_times.append(time.time() - trial_start)
                    if self.target_position == 'right':
                        self.decision_history.append(-1)
                    else:
                        self.decision_history.append(1)
                    self.correct_hist.append(0)
                    break
                elif time.time() > self.timeout:  # omission trials: no response in response window
                    self.cancel_audio = True
                    self.trial_stat[2] += 1
                    self.data_logger()
                    self.reaction_times.append(time.time() - trial_start)
                    self.decision_history.append(0)
                    self.correct_hist.append(0)
                    break

        if self.choice == "correct":
            self.curr_iti = self.iti[0]
        elif self.choice == "incorrect":
            self.play_tone(self.punish_sound, self.punish_duration, self.punish_amplitude)
            self.curr_iti = self.iti[1] * 2  # if incorrect, add 3 sec punishment timeout
        else:
            self.play_tone(self.punish_sound, self.punish_duration, self.punish_amplitude)
            self.curr_iti = self.iti[1]  # if omission, add 1.5 sec punishment timeout

        self.last_trial = self.trial_id  # only for stage 0
        self.cancel_audio = False
        time.sleep(self.curr_iti)  # inter-trial-interval
        self.data_logger()
        print("trial number: ", self.trial_num, " - correct trials: ", self.trial_stat[0])
        self.check_trial_end()
        #if self.trial_num < 2:
       #     print("\ntrial number: ", self.trial_num, " - correct trials: ", self.corr_trials, end="")
        #else:
          #  print("\rtrial number: ", self.trial_num, " - correct trials: ", self.corr_trials, end="")


    # run is where the dothis code will be
    def run(self):
        while not self.stop:
            # Loop this infinitely until I tell it stop
            self.auditory_2afc()



task = None
sync_rec = None
camera = None
rotary = None
exp_dir_create = False
droid = socket.gethostname()
procedure = "auditory_2afc"

# get the animal id and load the response matrix
animal_id = input("enter the mouse ID:")

experimenter = input("who is running the experiment?")

hour_format = "%H:%M:%S"
start_time = datetime.now().strftime(hour_format)

response_matrix, pre_reversal = load_response_matrix(animal_id)

# booleans to set if you want to trigger camera/record sync pulses from 2p
sync_bool = False
camera_bool = False

# comment these lines if you don't want to get questions asked
# if droid == "bb8":
#     sync_bool = start_option('sync_pulse')
#     camera_bool = start_option('camera_trigger') # for bb8 comment this line too (for now) todo: check if you want ot change this


# define session ending criteria
# 1. time_out = session > 90 min
start_time_diff = time.time()  # for calculating timeout, was to lazy to figure out, how to do it with datetime moduel..
time_limit = 90  # time_limit in min
time_out = start_time_diff + (time_limit * 60)

# 2. Low number of trials - > 45 min && < 300 trials (irrespective of performance)
time_limit_lt = 45  # in min, time_limit low trials
time_out_lt = start_time_diff + (time_limit_lt * 60)
low_trial_lim = 350

# 3. disengagement > 300 trials && roll.median of last 20 trials > than 5x median of previous 300 trials


while True:
    command = input("Enter 'start' to begin:")
    if command == "start":
        if not exp_dir_create:
            animal_dir = check_dir(animal_id)
            exp_dir = make_exp_dir(animal_dir)
            exp_dir_create = True
        task = Auditory2AFC()
        rotary = RotaryRecorder()
        if sync_bool:
            sync_rec = SyncRecorder()
        if camera_bool:
            camera = TriggerPulse()
        task.start()
        rotary.start()
        if sync_bool:
            sync_rec.start()
        if camera_bool:
            camera.start()

    if command == "stop":
        ending_criteria = task.ending_criteria
        task.stage_checker()
        task.stop = True
        rotary.stop = True
        if sync_bool:
            sync_rec.stop = True
        if camera_bool:
            camera.stop = True
        # GPIO.cleanup()
        end_time = datetime.now().strftime(hour_format) # not the real endtime, but the time of entering "stop"
        store_meta_data(animal_id, droid, start_time, end_time, exp_dir, task, sync_bool, camera_bool,
                        ending_criteria=ending_criteria, procedure=procedure, pre_reversal=pre_reversal,
                        experimenter=experimenter)
        store_reaction_times(exp_dir, task)
        store_pref_data(exp_dir, procedure=procedure)
        task.join()
        rotary.join()
        if sync_bool:
            sync_rec.join()
        if camera_bool:
            camera.join()
        plot_behavior_terminal(exp_dir, procedure)  # plot behavior in terminal
        print("ending_criteria: " + ending_criteria)
        sys.exit()

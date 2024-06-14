'''
Auditory go/no-go task with tone clouds


Aim:
    Animals are trained to perform an auditory (reversal) go/no-go task with tone clouds. Animals are randomly assigned
    to one of two groups (either high or low tone clouds serves as go signal, this is changed after the reversal).
    Animals indicate responses by turning the wheel.

    There are two types of correct trials:
        - correct detection (wheel turn upon go cue) --> 10 % sucrose reward is given (3ul, maybe this will be reduced later on)
        - correct rejection (no wheel turn upon no-go cue)
    and two types of errors:
        - false alarm (wheel turn upon no-go cue)
        - omission (no wheel turn upon go cue)
        --> in both cases a white noise is played, plus 1.5 sec timeout (i.e. increased ITI)

    From Coen et al., 2021: the turning threshold for a decision was 30 degrees in wheel turning.

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
    plot_behavior_terminal, \
    pitch_to_frequency, weighted_octave_choice, create_tone, \
    load_droid_setting, load_task_prefs, load_response_matrix, store_meta_data, store_pref_data,\
        store_reaction_times, load_pump_calibration

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


class AuditoryDetection(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        # load pref files

        self.droid_settings = load_droid_setting()  # general paramters (e.g. pin layout map and sampling rates used)
        self.task_prefs = load_task_prefs(procedure)  # task specifics (e.g. tones used and their duration)
        self.first_day = check_first_day(animal_dir, procedure)
        # get current stage
        self.stage = get_stage(animal_dir, procedure, self.first_day)  # current stage of the animal
        self.stage_advance = False  # set this boolean to true if animal can advance a stage

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
        self.left_right = 0
        self.curr_iti = 0

        self.tone_history = []  # list for keeping track of tone history, make sure to have same tone max 3x

        self.cloud_bool = False
        if self.stage == 0:
            self.turning_goal = int(self.turning_goal / 2)

        # disengagement boolean
        self.disengage = False
        self.reaction_times = []
        self.choice_hist = []
        # stop boolean - entered in terminal to terminate session
        self.stop = False
        self.ending_criteria = "manual"  # default ending criteria is "manual", gets overwritten if trial ends based on automatic criteria


    def stage_checker(self):
        # function to check if one advances in stages, to be called at the end of a session
        if self.stage == 0:
            # criteria to advance from stage 0 to stage 1 --> more than 200 correct trials on two consecutive days
            if self.trial_stat[0] > 150:  # if more than 150 correct trials, check if there were also > 150 correct trials in the previous session
                self.stage_advance = True
                print(">>>>>  FINISHED STAGE " + str(self.stage) + " !!! <<<<<<<<<")

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
    def trigger_reward(self):
        # function to open pump for defined duration and log this data
        GPIO.output(self.pump, GPIO.HIGH)
        self.reward_time = 1
        self.data_logger()
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
        audio = create_tone(self.tone_fs, int(tone), duration, amplitude)
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
        curr_stim_strength = self.stim_strength[0]

        self.tgt_octave = 1  # at stage 0 --> middle octave only

        cloud = self.create_tone_cloud(self.tgt_octave, curr_stim_strength)

        return cloud

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

    def calculate_decision(self):  #  , wheel_position, turning_goal):

        # continously stream the wheel_position --> if it crosses threshold (30 degree) mark choice as left/right; otherwise it's "undecided"
        # right turns are positive and left turns are negative --> depends on how you wire the encoder
        self.current_position = self.encoder_data.getValue()
        # self.rotary_logger(self.current_position)
        self.wheel_position = self.current_position - self.wheel_start_position
        if self.wheel_position > self.turning_goal:
            self.left_right = "right"
            self.decision_var = "moved_wheel"
            self.choice_hist.append(1)  # one for moved wheel
        elif self.wheel_position < -self.turning_goal:
            self.left_right = "left"
            self.decision_var = "moved_wheel"
            self.choice_hist.append(1) # one for moved wheel
        elif time.time() > self.timeout:
            self.left_right = "none"
            self.decision_var = "no_response"
            self.choice_hist.append(0)  # one for moved wheel
        time.sleep(0.001)  # 1 ms sleep, otherwise some threading issue occur
        return self.decision_var

    def data_logger(self):
        # always add one line to csv file upon event with timestamp for sync
        with open(self.trial_data_fn, "a") as log:
            log.write("{0},{1},{2},{3},{4},{5},{6},{7},{8},{9}\n".format(time.time(), str(self.trial_num), str(self.trial_start), str(self.trial_id), str(self.tone_played), str(self.decision_var), str(self.choice), str(self.left_right), str(self.reward_time), str(self.curr_iti)))  # todo: 0: time_stamp, 1: trial_num, 2: trial_start, 3: trial_type:, 4: tone_played, 5: decision_variable, 6: choice_variable, 7: reward_time, 8: inter-trial-intervall

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

    def check_disengage(self):
        # check the number of no_responses in last 20 trials, if > 16 (=80 %), stop session
        if np.sum(self.choice_hist[-20:]) < 4:  # value of 4 corresponds to 4x moved_wheel responses
            self.disengage = True  # set disengage bool to True
        else:
            self.disengage = False  # can be reversed (for now..)
        return self.disengage
    #
    def check_trial_end(self):
        if time.time() > time_out:  # max length reach
            mess = "60 min passed -- time limit reached, enter 'stop' and take out animal"
            print(mess)
            self.ending_criteria = "max_time"
            self.stop = True
        elif time.time() > time_out_lt:  # time_out_lt is minimum time (45 min), if animal disengages afterwards, take it out
            self.disengage = self.check_disengage()
            if self.disengage:  # disengagement after > 45 min
                mess = "animal is disengaged, please enter 'stop' and take out animal"
                print(mess)
                self.ending_criteria = "disengagement"
                self.stop = True

    def auditory_detection(self):
        # self.seconds = self.get_seconds()
        self.trial_start = 1
        self.data_logger()
        self.trial_start = 0
        self.trial_id = 'middle'
        self.tone_history.append(self.trial_id)
        self.cloud_bool = False

        while True:
            self.animal_quite, self.cloud = self.check_quite_window(self.cloud)  # call the QW checker function, stay in function as long animal holds wheel still, otherwise return and call function again
            if self.animal_quite:  # if animal is quite for quite window length, ini new trial, otherwise stay in loop
                trial_start = time.time()
                self.animal_quite = False
                break

        self.target_position = "moved_wheel"
        self.timeout = time.time() + self.response_window  # start a timer at the size of the response window
        self.trial_num += 1
        self.decision_var = False  # set decision variable to False for start of trial, and then in the loop check for decision

        with sd.OutputStream(samplerate=self.fs, blocksize=len(self.cloud), channels=2, dtype='int16',
                             latency='low', callback=self.callback):
            time.sleep(self.cloud_duration * 2)  # to avoid zero shot trials, stream buffers 2x the cloud duration before tone onset
            self.tone_played = 1
            self.data_logger()
            self.tone_played = 0
            self.wheel_start_position = self.encoder_data.getValue()
            while True:
                self.decision_var = self.calculate_decision()  # should stay False until either response window is over or animal moved the wheel
                if self.decision_var == self.target_position:  # if choice was correct
                    self.cancel_audio = True
                    self.choice = "correct"
                    self.trial_stat[0] += 1
                    self.data_logger()
                    if self.decision_var == "moved_wheel":  # reward only in go trials
                        self.trigger_reward()
                    self.reaction_times.append(time.time()-trial_start)
                    break
                elif self.decision_var == "no_response": # if choice was incorrect and variable is NOT False, trial was incorrect
                    self.cancel_audio = True
                    self.choice = "incorrect"
                    self.trial_stat[1] += 1
                    self.data_logger()
                    self.reaction_times.append(time.time() - trial_start)
                    break

        if self.choice == "correct":
            self.curr_iti = self.iti[0]
        else:
            self.curr_iti = self.iti[1]  # if not correct, add 3 sec punishment timeout

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
            self.auditory_detection()



task = None
sync_rec = None
camera = None
rotary = None
exp_dir_create = False
droid = socket.gethostname()
procedure = "auditory_detection"

# get the animal id and load the response matrix
animal_id = input("enter the mouse ID:")

experimenter = input("who is running the experiment?")

hour_format = "%H:%M:%S"
start_time = datetime.now().strftime(hour_format)

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
time_limit = 60  # time_limit in min
time_out = start_time_diff + (time_limit * 60)

# 2. Low number of trials - > 45 min && < 300 trials (irrespective of performance)
time_limit_lt = 45  # in min, time_limit low trials
time_out_lt = start_time_diff + (time_limit_lt * 60)
low_trial_lim = 200
# 3. disengagement > 300 trials && roll.median of last 20 trials > than 5x median of previous 300 trials


while True:
    command = input("Enter 'start' to begin:")
    if command == "start":
        if not exp_dir_create:
            animal_dir = check_dir(animal_id)
            exp_dir = make_exp_dir(animal_dir)
            exp_dir_create = True
        task = AuditoryDetection()
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
                        ending_criteria=ending_criteria, procedure=procedure, pre_reversal=False,
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

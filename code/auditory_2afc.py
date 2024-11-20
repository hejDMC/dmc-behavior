'''
Auditory two-alternative forced choice task with tone clouds

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

'''

#%% import modules
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
from base_auditory_task import BaseAuditoryTask
from reader_writers import TriggerPulse, RotaryRecorder, SyncRecorder
from path_manager import PathManager
from data_io import DataIO
from auditory_2afc_helpers import StageChecker, BiasCorrectionHandler

#%%

# Example of a Task Specific Class using the Base Class
class Auditory2AFC(BaseAuditoryTask):
    DECISION_SD = 0.5
    MIN_TRIAL_DEBIAS = 10
    def __init__(self, procedure, animal_dir):
        super().__init__(procedure, animal_dir)
        self.turning_goal = self.droid_settings['base_params']['turning_goal']
        self.encoder_data = Encoder(self.droid_settings['pin_map']['IN']['encoder_left'],
                                    self.droid_settings['pin_map']['IN']['encoder_right'])

        self.bc_handler = BiasCorrectionHandler(self.animal_dir, self.first_day, self.stage)
        self.bias_correction = self.bc_handler.get_bias_correction()
        self.bias_counter = 0  # bias counter to avoid that animals develop a bias to higher rewarded side
        self.bias_counter_max = self.task_prefs['task_prefs']['bias_counter_max']

        self.curr_stim_strength = False  # to be decided eacht trial

        self.correct_hist = []  # history of correct trials for block structure in stage 0
        self.last_trial = 0
        self.decision_history = []  # list of choices 1 for right, -1 for left, 0 for undecided, average of 0 indicates no bias

        self.cloud_bool = False

        self.block = 0  # only in stage 5
        self.block_length = 0
        self.block_counter = 0

        # disengagement boolean
        self.disengage = False
        self.reaction_times = []
        # stop boolean - entered in terminal to terminate session
        self.stop = False
        self.ending_criteria = "manual"

    def get_trial(self):
        """
        Determine the trial type (high or low tone) based on the current stage and trial number.
        Returns:
            str: The trial ID ('high' or 'low').
        """
        # Constants for easier adjustment
        NO_BIAS_PROB = 0.5
        HIGH_PROB_STAGE_5_BLOCK_NEG = 0.2
        HIGH_PROB_STAGE_5_BLOCK_POS = 0.8
        NO_BIAS_TRIALS_STAGE_5 = 90

        if self.stage < 5:
            # Stage < 5: Random choice, no bias
            self.trial_id = 'high' if random.random() < NO_BIAS_PROB else 'low'

        elif self.stage == 5:
            # Stage 5 logic
            if self.trial_num <= NO_BIAS_TRIALS_STAGE_5:
                # First 90 trials, no bias
                if self.trial_num == NO_BIAS_TRIALS_STAGE_5:
                    self.get_block()  # Set up the block after first 90 trials
                self.trial_id = 'high' if random.random() < NO_BIAS_PROB else 'low'
            else:
                # After 90 trials, follow block bias
                high_prob = HIGH_PROB_STAGE_5_BLOCK_NEG if self.block == -1 else HIGH_PROB_STAGE_5_BLOCK_POS
                self.trial_id = 'high' if random.random() < high_prob else 'low'

                # Increment block counter and switch block if needed
                self.block_counter += 1
                print(f"Block counter: {self.block_counter}")
                if self.block_counter >= self.block_length:
                    self.get_block()  # Change block when block length is reached

        else:
            # Undefined stage handling
            raise ValueError(f"Unexpected stage value: {self.stage}. Only stages 0-5 are implemented.")

        return self.trial_id

    def get_trial_id(self):
        """
        Determine the trial ID based on the current stage, correct history, and trial outcomes.
        Returns:
            str: The trial ID ('high' or 'low').
        """

        # Constants for improved readability
        MIN_CORRECT_HISTORY = 3
        DEBIASING_STAGE_THRESHOLD = 4
        # Stage 0: Handle initial learning stage
        if self.stage == 0:
            if len(self.correct_hist) < MIN_CORRECT_HISTORY:
                # Repeat the last trial if fewer than 3 trials have occurred
                self.trial_id = self.last_trial
            else:
                # Check the last three trials
                corr_sum = np.sum(self.correct_hist[-MIN_CORRECT_HISTORY:])
                if corr_sum == MIN_CORRECT_HISTORY:  # If the last three trials were all correct, switch trial
                    self.correct_hist = []  # Reset history
                    self.trial_id = 'low' if self.last_trial == 'high' else 'high'
                else:
                    # Otherwise, repeat the last trial
                    self.trial_id = self.last_trial

        # Stages 1-3: Apply debiasing if necessary, otherwise get trial
        elif 0 < self.stage < DEBIASING_STAGE_THRESHOLD:
            if self.choice == "incorrect" and self.trial_num > self.MIN_TRIAL_DEBIAS:
                # Apply debiasing if previous trial was incorrect
                self.trial_id = self.debias()
                print("call debias")
            else:
                # Otherwise, randomly initialize trial ID
                self.trial_id = self.get_trial()

        # Stage 4 and beyond: No debiasing, use get_trial
        else:
            self.trial_id = self.get_trial()

        return self.trial_id

    def debias(self):
        # should only be calculated after incorrect trials
        # function for debiasing --> calculate the mean response over the last 10 trials, if animal only goes in one direction, present tones only on other side
        # open trial data file and read the last 10 trials and calculate the average
        hist_list = self.decision_history[-self.MIN_TRIAL_DEBIAS:]
        hist_mean = np.mean(hist_list)
        debias_val = random.gauss(hist_mean, self.DECISION_SD)
        bias_side = 'right' if debias_val > 0 else 'left'
        tone = list(response_matrix.keys())[list(response_matrix.values()).index(bias_side)]
        self.trial_id = 'low' if tone == 'high' else 'high'

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

            self.stop = True
        # check disengagement
        if time.time() > time_out_lt and self.trial_num > low_trial_lim:
            self.disengage = self.check_disengage()
            if self.disengage:  # disengagement after > 45 min
                mess = "animal is disengaged, please enter 'stop' and take out animal"
                print(mess)
                self.ending_criteria = "disengagement"
                self.stop = True

    def play_tone(self, tone, duration, amplitude):
        audio = self.stimulus_manager.create_tone(self.fs, int(tone), duration, amplitude)
        # print(str(tone))
        sd.play(audio, self.fs, blocking=True)

    def callback(self, outdata, frames, time, status):
        # callback function for audio stream
        if self.cancel_audio:
            raise sd.CallbackStop()
        outdata[:] = np.column_stack((self.cloud, self.cloud))  # two channels
    def execute_task(self):
        # Example implementation for 2AFC task
        trial_id = random.choice(['high', 'low'])
        if trial_id == 'high':
            cloud = self.stimulus_manager.create_tone_cloud(tgt_octave=2, stim_strength=80)
        else:
            cloud = self.stimulus_manager.create_tone_cloud(tgt_octave=0, stim_strength=80)
        # ... More logic for the specific trial

    def check_stage(self):
        # Logic for checking stage progression
        self.stage_checker = StageChecker(self.animal_dir, self.stage, trial_stat, trial_num,
                                         decision_history, correct_hist)
        self.stage_advance = self.stage_checker.check_stage()

    def adjust_pump_duration(self):
        if self.decision_var == self.bias_correction and self.bias_counter <= self.bias_counter_max:  # if the animal choose anti-bias side, give more reward
            curr_pump_duration = int(self.pump_duration * 2)
            self.bias_counter += 1  # only reward first x trials with higher volume
        else:
            curr_pump_duration = int(self.pump_duration)
        return curr_pump_duration

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

    def get_target_cloud(self):
        """
        Determine the current stimulus strength based on the stage, and create the corresponding tone cloud.

        Returns:
            The generated tone cloud.
        """

        # Define the selection logic for stimulus strengths based on stage
        stage_selector = {
            0: [self.stim_strength[0]],  # Stage 0, always 100
            1: [self.stim_strength[0]],  # Stage 1, always 100
            2: [self.stim_strength[0], self.stim_strength[1]],  # Stage 2, 100 or 80
            3: [self.stim_strength[0], self.stim_strength[1], self.stim_strength[2]],  # Stage 3, 100, 80, or 70
            4: [self.stim_strength[0], self.stim_strength[1], self.stim_strength[2], self.stim_strength[3]],  # Stage 4, 100, 80, 70 or 60
            5: [self.stim_strength[0], self.stim_strength[1], self.stim_strength[2], self.stim_strength[3]]  # Stage 5, 100, 80, 70 or 60
        }

        if self.stage in stage_selector:
            options = stage_selector[self.stage]
        else:
            print(f'Warning: Stage {self.stage} out of range (0-5), defaulting to stage 0')
            options = stage_selector[0]  # default to stage 0

        # Select the current stimulus strength randomly from options
        self.curr_stim_strength = random.choice(options)

        # Set octave based on trial type
        self.tgt_octave = 2 if self.trial_id == 'high' else 0

        # Create the tone cloud
        self.cloud = self.stimulus_manager.create_tone_cloud(self.tgt_octave, self.curr_stim_strength)

        return self.cloud
    def check_quiet_window(self):

        start_pos = self.encoder_data.getValue()  # start position of the wheel
        q_w = self.quiet_window[0] + np.random.exponential(self.quiet_window[1])
        if q_w > 1.5:
            q_w = 1.5
        quite_time = time.time() + q_w
        while True:
            curr_pos = self.encoder_data.getValue()
            if not self.cloud_bool:
                self.cloud = self.get_target_cloud()
                self.cloud_bool = True
            if curr_pos not in range(start_pos-self.quite_jitter, start_pos+self.quite_jitter):  # the curr_pos of the wheel is out of allowed range, exit and checker function will be called again
                self.animal_quiet = False
                break
            elif time.time() > quite_time:  # if animal is still for QW, bool to True and exit --> trial will be initialized
                self.animal_quiet = True
                break
            time.sleep(0.001)  # 1 ms sleep, otherwise some threading issue occur
        return self.animal_quiet, self.cloud

task = None
sync_rec = None
camera = None
rotary = None
exp_dir_create = False
droid = socket.gethostname()
task_type = "auditory_2afc"

# get the animal id and load the response matrix
animal_id = input("enter the mouse ID:")

experimenter = input("who is running the experiment?")

hour_format = "%H:%M:%S"
start_time = datetime.now().strftime(hour_format)

response_matrix, pre_reversal = load_response_matrix(animal_id)

# booleans to set if you want to trigger camera/record sync pulses from 2p
sync_bool = False
camera_bool = False

# define session ending criteria todo fix this numbers here
# 1. time_out = session > 90 min
start_time_diff = time.time()  # for calculating timeout, was to lazy to figure out, how to do it with datetime moduel..
time_limit = 90  # time_limit in min
time_out = start_time_diff + (time_limit * 60)

# 2. Low number of trials - > 45 min && < 300 trials (irrespective of performance)
time_limit_lt = 45  # in min, time_limit low trials
time_out_lt = start_time_diff + (time_limit_lt * 60)
low_trial_lim = 350


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
        task.check_stage()
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
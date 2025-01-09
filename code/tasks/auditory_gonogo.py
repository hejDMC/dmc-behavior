'''
Auditory Go/NoGo task with tone clouds


Aim:
    Animals are trained to perform an auditory (reversal) go/no-go task with tone clouds. Animals are randomly assigned
    to one of two groups (either high or low tone clouds serves as go signal, this is changed after the reversal).
    Animals indicate responses by turning the wheel.

    There are two types of correct trials:
        - correct detection (wheel turn upon go cue) --> 5 ul 10 % sucrose reward is given
        - correct rejection (no wheel turn upon no-go cue)
    and two types of errors:
        - false alarm (wheel turn upon no-go cue) --> white noise is played
        - omission (no wheel turn upon go cue)
        --> 1.5 sec timeout (i.e. increased ITI)

    From Coen et al., 2021: the turning threshold for a decision was 30 degrees in wheel turning.

'''

#%% import modules
import numpy as np
import pandas as pd
import sounddevice as sd
import time
import random
from base_auditory_task import BaseAuditoryTask


#%%

class AuditoryGoNoGo(BaseAuditoryTask):
    # todo constants
    STAGE_0_TRIAL_NUM = 150

    TIME_LIMIT = 60
    TIME_LIMIT_LOW_TRIALS = 45
    LOW_TRIAL_NUM = 200
    SECONDS = 60

    PUMP_TIME_ADJUST = 1  # no intra-trial pump time adjustment

    def __init__(self, data_io, exp_dir, procedure):
        super().__init__(data_io, exp_dir, procedure)
        start_time = time.time()
        self.time_out = start_time + self.TIME_LIMIT * self.SECONDS
        self.time_out_low_trials = start_time + self.TIME_LIMIT_LOW_TRIALS * self.SECONDS

        self.response_matrix, self.pre_reversal = data_io.load_response_matrix()
        self.turning_goal = self.task_prefs['encoder_specs']['target_degrees']

        self.left_right = 0
        self.tone_history = []  # list for keeping track of tone history, make sure to have same tone max 3x
        self.choice_hist = []

    def stage_checker(self):
        # function to check if one advances in stages, to be called at the end of a session
        if self.stage == 0:
            # criteria to advance from stage 0 to stage 1 --> more than 150 correct trials on two consecutive days
            if self.trial_stat[0] > self.STAGE_0_TRIAL_NUM:
                self.stage_advance = True
                print(">>>>>  FINISHED STAGE " + str(self.stage) + " !!! <<<<<<<<<")

    def get_trial(self):
        # randomly choose either high vs. low tone trial
        if random.random() < 0.5:
            self.trial_id = 'high'
        else:
            self.trial_id = 'low'
        if self.trial_num > 2:
            if self.tone_history[-3] == self.tone_history[-2] == self.tone_history[-1]:  # limit trial repeats to max 3
                if self.tone_history[-1] == 'high':
                    self.trial_id = 'low'
                else:
                    self.trial_id = 'high'
        return self.trial_id

    def calculate_decision(self, timeout):  #  , wheel_position, turning_goal):

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
        elif time.time() > timeout:
            self.left_right = "none"
            self.decision_var = "no_response"
            self.choice_hist.append(0)  # one for moved wheel
        time.sleep(0.001)  # 1 ms sleep, otherwise some threading issue occur
        return self.decision_var
    #
    def check_trial_end(self):
        if time.time() > self.time_out:  # max length reach
            mess = "60 min passed -- time limit reached, enter 'stop' and take out animal"
            print(mess)
            self.ending_criteria = "max_time"
            self.stop = True
        elif time.time() > self.time_out_low_trials:  # time_out_lt is minimum time (45 min), if animal disengages afterwards, take it out
            self.disengage = self.check_disengage(self.choice_hist)
            if self.disengage:  # disengagement after > 45 min
                mess = "animal is disengaged, please enter 'stop' and take out animal"
                print(mess)
                self.ending_criteria = "disengagement"
                self.stop = True

    def get_log_data(self):
        # always add one line to csv file upon event with timestamp for sync
        return "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9}\n".format(time.time(), str(self.trial_num), str(self.trial_start),
                                                           str(self.trial_id), str(self.tone_played),
                                                           str(self.decision_var), str(self.choice),
                                                           str(self.left_right), str(self.reward_time),
                                                           str(self.curr_iti))  # todo: 0: time_stamp, 1: trial_num, 2: trial_start, 3: trial_type:, 4: tone_played, 5: decision_variable, 6: choice_variable, 7: reward_time, 8: inter-trial-intervall

    def execute_task(self):
        self.trial_start = 1
        self.logger.log_trial_data(self.get_log_data())
        self.trial_start = 0
        self.trial_id = self.get_trial()
        self.tone_history.append(self.trial_id)
        self.cloud_bool = False
        while True:
            self.animal_quiet, self.cloud = self.check_quiet_window()  # call the QW checker function, stay in function as long animal holds wheel still, otherwise return and call function again
            if self.animal_quiet:  # if animal is quiet for quiet window length, ini new trial, otherwise stay in loop
                trial_start = time.time()
                self.animal_quiet = False
                break
        self.target_position = self.response_matrix[self.trial_id]
        timeout = time.time() + self.response_window  # start a timer at the size of the response window
        self.trial_num += 1
        self.decision_var = False  # set decision variable to False for start of trial, and then in the loop check for decision
        with sd.OutputStream(samplerate=self.stimulus_manager.fs, blocksize=len(self.cloud), channels=2, dtype='int16',
                             latency='low', callback=self.callback):
            time.sleep(self.stimulus_manager.cloud_duration * 2)  # to avoid zero shot trials, stream buffers 2x the cloud duration before tone onset
            self.tone_played = 1
            self.logger.log_trial_data(self.get_log_data())
            self.tone_played = 0
            self.wheel_start_position = self.encoder_data.getValue()
            while True:
                self.decision_var = self.calculate_decision(timeout)  # should stay False until either response window is over or animal moved the wheel
                if self.decision_var == self.target_position:  # if choice was correct
                    self.cancel_audio = True
                    self.choice = "correct"
                    self.trial_stat[0] += 1
                    self.logger.log_trial_data(self.get_log_data())
                    if self.decision_var == "moved_wheel":  # reward only in go trials
                        self.reward_system.trigger_reward(self.logger, self.PUMP_TIME_ADJUST)
                    break
                elif self.decision_var: # if choice was incorrect and variable is NOT False, trial was incorrect
                    self.cancel_audio = True
                    self.choice = "incorrect"
                    self.trial_stat[1] += 1
                    self.logger.log_trial_data(self.get_log_data())
                    break
        if self.choice == "correct":
            self.curr_iti = self.iti[0]
        else:
            if self.target_position == "no_response":  # in nogo trials --> play punishment sound
                self.play_tone(self.punish_sound, self.punish_duration, self.punish_amplitude)
            self.curr_iti = self.iti[1]  # if not correct, add 3 sec punishment timeout

        self.cancel_audio = False
        time.sleep(self.curr_iti)  # inter-trial-interval
        self.logger.log_trial_data(self.get_log_data())
        print("trial number: ", self.trial_num, " - correct trials: ", self.trial_stat[0])
        self.check_trial_end()
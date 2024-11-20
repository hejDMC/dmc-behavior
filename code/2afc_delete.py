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
from utils.utils import get_today, check_first_day, get_stage, make_exp_dir, check_dir, start_option, plot_behavior_terminal, \
    pitch_to_frequency, weighted_octave_choice, create_tone, \
    load_droid_setting, load_task_prefs, load_response_matrix, store_meta_data, store_pref_data,\
        store_reaction_times, load_pump_calibration, \
    check_stage_4_advance, check_ready_for_experiment, get_bias_correction


class Auditory2AFC(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)


    #


    #




    #




    #



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
            self.animal_quiet, self.cloud = self.check_quiet_window(self.cloud)  # call the QW checker function, stay in function as long animal holds wheel still, otherwise return and call function again
            if self.animal_quiet:  # if animal is quiet for quiet window length, ini new trial, otherwise stay in loop
                trial_start = time.time()
                self.animal_quiet = False
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

"""
Habituation script for head-fixed mice performing auditory tasks

Aim:
    Habituate animals to setup and being head-fixed. Animals are head-fixed for increasing durations (day 1 = 15 min;
    day 2 = 30 min; day = 45 min). During head-fixation, animals are presented the 'easy' tones and X ul reward (10%
    sucrose) is provided. During habituation the wheel position is fixed.


"""

import random
import socket
import sys
import threading
import time
from datetime import datetime

import numpy as np
import pandas as pd

##
import RPi.GPIO as GPIO
import sounddevice as sd
from sklearn import preprocessing
from utils.utils import (
    check_dir,
    create_tone,
    get_habi_task,
    get_today,
    habi_time_limit,
    load_droid_setting,
    load_pump_calibration,
    load_task_prefs,
    make_exp_dir,
    pitch_to_frequency,
    store_meta_data,
    store_pref_data,
    weighted_octave_choice,
)


# %%
class Habituation(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        # load pref files
        self.droid_settings = (
            load_droid_setting()
        )  # general paramters (e.g. pin layout map and sampling rates used)
        self.task_prefs = load_task_prefs(
            "habituation_auditory_tasks"
        )  # task specifics (e.g. tones used and their duration)

        # set task parameters
        self.l_oct = self.task_prefs["task_prefs"][
            "low_octave"
        ]  # low octave in pitch (start pitch, end pitch, num_pitch)
        self.m_oct = self.task_prefs["task_prefs"][
            "middle_octave"
        ]  # middle octave in pitch (start pitch, end pitch, num_pitch)
        self.h_oct = self.task_prefs["task_prefs"][
            "high_octave"
        ]  # high octave in pitch (start pitch, end pitch, num_pitch)
        self.low_octave = np.linspace(self.l_oct[0], self.l_oct[1], self.l_oct[2])
        self.middle_octave = np.linspace(self.m_oct[0], self.m_oct[1], self.m_oct[2])
        self.high_octave = np.linspace(self.h_oct[0], self.h_oct[1], self.h_oct[2])
        # create array with octaves
        self.tones_arr = self.low_octave
        self.tones_arr = np.vstack([self.tones_arr, self.middle_octave])
        self.tones_arr = np.vstack([self.tones_arr, self.high_octave])
        self.tone_duration = self.task_prefs["task_prefs"][
            "tone_duration"
        ]  # duration of individual tones in cloud in sec
        self.tone_fs = self.task_prefs["task_prefs"][
            "tone_fs"
        ]  # sampling rate of tones in cloud
        self.tone_amplitude = self.task_prefs["task_prefs"][
            "tone_amplitude"
        ]  # amplitude of tones and tone cloud
        self.cloud_range = self.task_prefs["task_prefs"]["cloud_range"]
        self.scaler = preprocessing.MinMaxScaler(
            feature_range=(self.cloud_range[0], self.cloud_range[1])
        )  # scaler for tone cloud to set min max to int16 range

        self.cloud_duration = self.task_prefs["task_prefs"][
            "cloud_duration"
        ]  # duration of cloud in sec, needs to be dividable by tone length for now!!
        self.num_tones = int(
            self.cloud_duration * 100 - (self.tone_duration - 1 / self.tone_fs) * 100
        )  # number of tones in cloud
        self.fs = self.droid_settings["base_params"][
            "tone_sampling_rate"
        ]  # sampling rate for tones presented
        self.cloud = []  # ini of tone cloud
        self.cancel_audio = False  # boolean for cancelling audio
        self.stim_strength = (
            100  # in habi always 100, but change this along the training!!
        )

        self.pump_log = exp_dir.joinpath(f"{get_today()}_pump_data.csv")
        # set pump parameters and initialize pin (GPIO numbers!)
        self.reward_size = self.task_prefs["task_prefs"][
            f"reward_size_{task_id}"
        ]  # reward size is ul
        self.pump_time = (
            load_pump_calibration()
        )  # pump time equaling delivery of 1 ul in ms
        self.pump_duration = self.reward_size * self.pump_time  # ms
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.pump = self.droid_settings["pin_map"]["OUT"]["pump"]
        GPIO.setup(self.pump, GPIO.OUT)
        self.pump_time_after_audio = self.task_prefs["task_prefs"][
            "pump_time_after_audio"
        ]  # in seconds

        # dynamic ITI depending of day of habituation, to reach trial number for 1 ml (334 trials with 3 ul)
        # trial length = pump_time_after_audio + ITI
        sess_duration = time_limit * 60  # session duration in sec
        trial_num = round(1000 / self.reward_size)  # 1000 ul/reward size
        trial_duration = sess_duration / trial_num
        iti_duration = trial_duration - self.pump_time_after_audio

        self.iti = [
            iti_duration - (iti_duration / 2),
            iti_duration + (iti_duration / 2),
        ]  # mean of ITI will be iti_duration

        # data logging
        self.trial_data_fn = exp_dir.joinpath(f"{get_today()}_trial_data.csv")
        self.tone_cloud_fn = exp_dir.joinpath(f"{get_today()}_tone_cloud_data.csv")
        self.trial_num = 0
        self.trial_start = 0
        self.trial_id = 0
        self.tone_played = 0
        self.reward_time = 0
        self.seconds = 0
        self.curr_iti = 0

        # stop boolean - entered in terminal to terminate session
        self.stop = False
        self.ending_criteria = "manual"  # default ending criteria is "manual", gets overwritten if trial ends based on automatic criteria

    def get_trial(self):
        if task_id == "2afc":
            # randomly choose either high vs. low tone trial
            if random.random() < 0.5:
                self.trial_id = "high"
                self.tgt_octave = 2
            else:
                self.trial_id = "low"
                self.tgt_octave = 0
        else:
            self.trial_id = "middle"
            self.tgt_octave = 1
        return self.trial_id

    def create_tone_cloud(self, tgt_octave, stim_strength):
        # get random tone sequence to be played in cloud
        # tone sequence (irrespective of octave they are drawn from)
        tone_sequence_idx = [
            random.choice(range(np.shape(self.tones_arr[1])[0]))
            for i in range(self.num_tones)
        ]
        # draw actual tone_sequence from the respective octaves; prob. to draw from tgt vs. non-tgt octaves depends on stimulus strength
        tone_sequence = np.array(
            [
                self.tones_arr[weighted_octave_choice(tgt_octave, stim_strength)][idx]
                for idx in tone_sequence_idx
            ]
        )
        tone_sequence = [
            pitch_to_frequency(pitch) for pitch in tone_sequence
        ]  # convert the tones (pitches) to frequencies
        tone_cloud_duration = (
            self.fs * self.cloud_duration
        )  # in samples  # duration of tone_cloud
        tone_cloud = np.zeros(
            [int(tone_cloud_duration), len(tone_sequence)]
        )  # pre-allocate
        k = 0
        # save tone cloud
        pd.DataFrame(tone_sequence).T.to_csv(
            self.tone_cloud_fn, index=False, header=False, mode="a"
        )
        # iterate over each spot in tone_cloud matrix and insert tone at correct time_point
        for i, tone in enumerate(tone_sequence):
            tone_cloud[k : k + int(self.fs * self.tone_duration), i] = create_tone(
                self.fs, tone, self.tone_duration, self.tone_amplitude
            )
            k += int(
                tone_cloud_duration
                / (((self.tone_duration - 1 / self.tone_fs) * 100) + self.num_tones)
            )
        tone_cloud = tone_cloud.sum(axis=1) // len(
            tone_sequence
        )  # 2  # create tone_cloud signal to be played
        tone_cloud = tone_cloud.reshape(-1, 1)
        tone_cloud = self.scaler.fit_transform(tone_cloud)
        tone_cloud = tone_cloud.astype(np.int16)
        return tone_cloud

    def callback(self, outdata, frames, time, status):
        # callback function for audio stream
        if self.cancel_audio:
            raise sd.CallbackStop()
        outdata[:] = np.column_stack((self.cloud, self.cloud))  # two channels

    def trigger_reward(self):
        # function to open pump for defined duration and log this data
        # GPIO.setmode(GPIO.BCM)
        GPIO.output(self.pump, GPIO.HIGH)
        self.reward_time = 1
        self.data_logger()
        time.sleep(self.pump_duration / 1000)
        self.pump_logger()
        GPIO.output(self.pump, GPIO.LOW)
        self.reward_time = 0

    def data_logger(self):
        # always add one line to csv file upon event with timestamp for sync
        with open(self.trial_data_fn, "a") as log:
            log.write(
                "{0},{1},{2},{3},{4},{5},{6}\n".format(
                    time.time(),
                    str(self.trial_num),
                    str(self.trial_start),
                    str(self.trial_id),
                    str(self.tone_played),
                    str(self.reward_time),
                    str(self.curr_iti),
                )
            )  # todo: 0: time_stamp, 1: trial_num, 2: trial_start, 3: trial_type:, 4: tone_played, 5: tone_duration, 6: reward_given, 7: inter-trial-intervall

    def pump_logger(self):
        # log pump data to calculate total volume given and number of trials etc.
        # only log data for correct trials, when reward was given
        with open(self.pump_log, "a") as log:
            log.write(
                "{0},{1}\n".format(time.time(), str(self.pump_duration))
            )  #  todo: 0: time_stamp, 1: pump_duration

    def check_trial_end(self):
        if time.time() > time_out:  # max length reach
            mess = "time limit reached, enter 'stop' and take out animal"
            print(mess)
            self.ending_criteria = "max_time"
            self.stop = True

    def habituation(self):

        self.trial_start = 1
        self.trial_num += 1
        self.trial_id = self.get_trial()
        self.data_logger()
        self.trial_start = 0
        self.cloud = self.create_tone_cloud(self.tgt_octave, self.stim_strength)
        self.timeout = time.time() + self.pump_time_after_audio
        with sd.OutputStream(
            samplerate=self.fs,
            blocksize=len(self.cloud),
            channels=2,
            dtype="int16",
            latency="low",
            callback=self.callback,
        ):
            while True:
                if (
                    time.time() > self.timeout
                ):  # omission trials: no response in response window
                    self.cancel_audio = True
                    self.trigger_reward()
                    break

        self.cancel_audio = False
        self.curr_iti = random.uniform(self.iti[0], self.iti[1])
        time.sleep(self.curr_iti)  # inter-trial-interval
        self.data_logger()
        print("\ntrial number: ", self.trial_num, end="")
        self.check_trial_end()

    def run(self):
        while not self.stop:
            # Loop this infinitely until stop
            self.habituation()


task = None
exp_dir_create = False
droid = socket.gethostname()
# get the animal_id and check of data directory exists

animal_id = input("enter the mouse ID:")

experimenter = input("who is running the experiment?")

hour_format = "%H:%M:%S"
start_time = datetime.now().strftime(hour_format)
start_time_diff = (
    time.time()
)  # for calculating timeout, was to lazy to figure out, how to do it with datetime moduel..
task_id = get_habi_task()
habi_day, time_limit = (
    habi_time_limit()
)  # time_limit in min after which the script automatically stops depending on day of habi
time_out = start_time_diff + (time_limit * 60)  # in seconds
# comment these lines if you don't want to get questions asked
# sync_bool = start_option('sync_pulse')
# camera_bool = start_option('camera_trigger') # for bb8 comment this line too (for now) todo: check if you want ot change this

while True:
    command = input("Enter 'start' to begin:")
    if command == "start":
        if not exp_dir_create:
            animal_dir = check_dir(animal_id)
            exp_dir = make_exp_dir(animal_dir)
            exp_dir_create = True
        task = Habituation()
        task.start()

    if command == "stop":
        ending_criteria = task.ending_criteria
        task.stop = True
        # GPIO.cleanup()
        end_time = datetime.now().strftime(
            hour_format
        )  # not the real endtime, but the time of entering "stop"
        store_meta_data(
            animal_id,
            droid,
            start_time,
            end_time,
            exp_dir,
            task,
            False,
            False,
            procedure="habituation_auditory_tasks",
            habi_day=habi_day,
            experimenter=experimenter,
        )
        store_pref_data(exp_dir, procedure="habituation_auditory_tasks")
        task.join()

        print("ending_criteria: " + ending_criteria)
        sys.exit()

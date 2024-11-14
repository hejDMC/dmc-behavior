import numpy as np
import threading
from sklearn import preprocessing
import time
import random
import RPi.GPIO as GPIO
import pandas as pd
from utils.encoder import Encoder
from utils.sync_pulse import Sync_Pulse
from utils.utils import (get_today, check_first_day, get_stage, load_droid_setting, load_task_prefs,
                         load_pump_calibration, weighted_octave_choice, pitch_to_frequency, create_tone)


# Base class for common elements in auditory tasks
class BaseAuditoryTask(threading.Thread):
    def __init__(self, procedure, animal_dir):
        threading.Thread.__init__(self)
        self.droid_settings = load_droid_setting()
        self.task_prefs = load_task_prefs(procedure)
        self.first_day = check_first_day(animal_dir, procedure)
        self.stage = get_stage(animal_dir, procedure, self.first_day)
        self.animal_dir = animal_dir
        self.exp_dir = None  # This can be set externally
        self.stage_advance = False
        self.stop = False

        # Components used by all tasks
        self.stimulus_manager = StimulusManager(self.task_prefs, self.droid_settings)
        self.reward_system = RewardSystem(self.droid_settings, self.task_prefs)
        self.logger = Logger(animal_dir, self.exp_dir)

        # Set GPIO mode
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

    def run(self):
        while not self.stop:
            self.execute_task()

    def execute_task(self):
        raise NotImplementedError("This method should be implemented by subclasses.")

    def stage_checker(self):
        raise NotImplementedError("This method should be implemented by subclasses.")


# Stimulus Manager class to manage tone clouds and stimulus-related methods
class StimulusManager:
    def __init__(self, task_prefs, droid_settings):
        self.task_prefs = task_prefs
        self.droid_settings = droid_settings
        self.fs = droid_settings['base_params']['tone_sampling_rate']
        self.scaler = preprocessing.MinMaxScaler(feature_range=(task_prefs['task_prefs']['cloud_range'][0],
                                                                task_prefs['task_prefs']['cloud_range'][1]))
        self.tones_arr = self.generate_tones()

    def generate_tones(self):
        # Create the tone clouds for different octaves
        low_octave = np.linspace(self.task_prefs['task_prefs']['low_octave'][0],
                                 self.task_prefs['task_prefs']['low_octave'][1],
                                 self.task_prefs['task_prefs']['low_octave'][2])
        middle_octave = np.linspace(self.task_prefs['task_prefs']['middle_octave'][0],
                                    self.task_prefs['task_prefs']['middle_octave'][1],
                                    self.task_prefs['task_prefs']['middle_octave'][2])
        high_octave = np.linspace(self.task_prefs['task_prefs']['high_octave'][0],
                                  self.task_prefs['task_prefs']['high_octave'][1],
                                  self.task_prefs['task_prefs']['high_octave'][2])
        return np.vstack([low_octave, middle_octave, high_octave])

    def create_tone_cloud(self, tgt_octave, stim_strength):
        # Generate a tone cloud from target octave and stimulation strength
        tone_sequence_idx = [random.choice(range(np.shape(self.tones_arr[1])[0])) for _ in
                             range(self.task_prefs['task_prefs']['num_tones'])]
        tone_sequence = np.array(
            [self.tones_arr[weighted_octave_choice(tgt_octave, stim_strength)][idx] for idx in tone_sequence_idx])
        tone_sequence = [pitch_to_frequency(pitch) for pitch in tone_sequence]
        tone_cloud_duration = self.fs * self.task_prefs['task_prefs']['cloud_duration']
        tone_cloud = np.zeros([int(tone_cloud_duration), len(tone_sequence)])
        k = 0
        for i, tone in enumerate(tone_sequence):
            tone_cloud[k:k + int(self.fs * self.task_prefs['task_prefs']['tone_duration']), i] = create_tone(self.fs,
                                                                                                             tone,
                                                                                                             self.task_prefs[
                                                                                                                 'task_prefs'][
                                                                                                                 'tone_duration'],
                                                                                                             self.task_prefs[
                                                                                                                 'task_prefs'][
                                                                                                                 'tone_amplitude'])
            k += int(tone_cloud_duration / (((self.task_prefs['task_prefs']['tone_duration'] - 1 /
                                              self.task_prefs['task_prefs']['tone_fs']) * 100) + len(tone_sequence)))
        tone_cloud = tone_cloud.sum(axis=1) // len(tone_sequence)
        tone_cloud = tone_cloud.reshape(-1, 1)
        return self.scaler.fit_transform(tone_cloud).astype(np.int16)


# Reward System class for managing reward dispensing
class RewardSystem:
    def __init__(self, droid_settings, task_prefs):
        self.droid_settings = droid_settings
        self.task_prefs = task_prefs
        self.pump_time = load_pump_calibration()
        self.pump_min_max = [p * self.pump_time for p in self.task_prefs['task_prefs']['reward_size']]
        self.pump_duration = self.pump_min_max[0]
        self.pump = self.droid_settings['pin_map']['OUT']['pump']
        GPIO.setup(self.pump, GPIO.OUT)

    def trigger_reward(self):
        GPIO.output(self.pump, GPIO.HIGH)
        time.sleep(self.pump_duration / 1000)
        GPIO.output(self.pump, GPIO.LOW)


# Logger class for logging experimental data
class Logger:
    def __init__(self, animal_dir, exp_dir):
        self.animal_dir = animal_dir
        self.exp_dir = exp_dir
        self.trial_data_fn = exp_dir.joinpath(f'{get_today()}_trial_data.csv')
        self.pump_log = exp_dir.joinpath(f'{get_today()}_pump_data.csv')

    def log_trial_data(self, trial_info):
        with open(self.trial_data_fn, "a") as log:
            log.write(trial_info + "\n")

    def log_pump_data(self, pump_duration):
        with open(self.pump_log, "a") as log:
            log.write(f"{time.time()},{pump_duration}\n")


# Example of a Task Specific Class using the Base Class
class Auditory2AFC(BaseAuditoryTask):
    def __init__(self, procedure, animal_dir):
        super().__init__(procedure, animal_dir)
        self.turning_goal = self.droid_settings['base_params']['turning_goal']
        self.encoder_data = Encoder(self.droid_settings['pin_map']['IN']['encoder_left'],
                                    self.droid_settings['pin_map']['IN']['encoder_right'])

    def execute_task(self):
        # Example implementation for 2AFC task
        trial_id = random.choice(['high', 'low'])
        if trial_id == 'high':
            cloud = self.stimulus_manager.create_tone_cloud(tgt_octave=2, stim_strength=80)
        else:
            cloud = self.stimulus_manager.create_tone_cloud(tgt_octave=0, stim_strength=80)
        # ... More logic for the specific trial

    def stage_checker(self):
        # Logic for checking stage progression
        if self.trial_stat[0] > 300:
            self.stage_advance = True
            print(f">>>>>  FINISHED STAGE {self.stage} !!! <<<<<")

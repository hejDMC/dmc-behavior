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
# todo utils as a class too

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
        self.reward_system = RewardSystem(self.animal_dir, self.droid_settings, self.task_prefs, self.first_day,
                                          self.stage)
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
    # todo have something here for pullup or pulldown
    def __init__(self, animal_dir, droid_settings, task_prefs, first_day, stage):
        self.animal_dir = animal_dir
        self.droid_settings = droid_settings
        self.task_prefs = task_prefs
        self.first_day = first_day
        self.stage = stage
        self.pump_time = load_pump_calibration()
        self.pump_min_max = [p * self.pump_time for p in self.task_prefs['task_prefs']['reward_size']]
        # self.pump_duration = self.pump_min_max[0]
        self.pump_duration = self.get_pump_duration()
        self.pump = self.droid_settings['pin_map']['OUT']['pump']
        GPIO.setup(self.pump, GPIO.OUT)

    def get_pump_duration(self) -> int:
        # Early return for first day and stage 0 scenarios
        if self.first_day or self.stage == 0:
            return self._get_max_pump_duration()

        # Load previous pump data
        pump_data = self._load_previous_pump_data()

        # If no previous data exists, return max pump duration
        if pump_data.empty:
            print('No previous records of pump duration found, defaulting to max')
            return self._get_max_pump_duration()

        # Determine pump duration based on previous data
        pump_duration = self._calculate_pump_duration_from_data(pump_data)
        print(f"pump_duration: {pump_duration}")
        return pump_duration

    def _get_max_pump_duration(self) -> int:
        """Return the maximum allowed pump duration."""
        return self.pump_min_max[0]

    def _get_min_pump_duration(self) -> int:
        """Return the minimum allowed pump duration."""
        return self.pump_min_max[1]

    def _load_previous_pump_data(self) -> pd.DataFrame:
        """Load previous pump duration data from CSV files in the last experimental directory."""
        pump_data = pd.DataFrame()
        pump_data_header = ["time", "pump_duration"]

        try:
            # Get the latest experimental day directory
            last_exp_day = sorted([day for day in self.animal_dir.iterdir() if day.is_dir()])[-1]
            last_exp_list = sorted([exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()])

            # Load pump data from each experiment directory
            for exp_dir in last_exp_list:
                pump_data_fn = exp_dir.joinpath(f'{exp_dir.parts[-2]}_pump_data.csv')
                if pump_data_fn.exists():
                    temp_df = pd.read_csv(pump_data_fn, names=pump_data_header)
                    pump_data = pd.concat((pump_data, temp_df), ignore_index=True)

        except IndexError:
            # Handle case where no directories are found
            print('No experimental directories found')

        return pump_data

    def _calculate_pump_duration_from_data(self, pump_data: pd.DataFrame) -> int:
        """Calculate the pump duration based on previous pump data."""
        if pump_data['pump_duration'].max() == pump_data['pump_duration'].min():
            return self._adjust_pump_duration(pump_data)
        else:
            # Keep reward volume constant if there's a bias correction
            return pump_data['pump_duration'].min()

    def _adjust_pump_duration(self, pump_data: pd.DataFrame) -> int:
        """Adjust the pump duration based on reward amount criteria."""
        amount_reward = pump_data['pump_duration'].sum() / self.pump_time
        prev_pump_duration = pump_data['pump_duration'].min()

        # Adjust pump duration based on reward criteria
        if amount_reward >= 1000:
            pump_duration = prev_pump_duration - (self.pump_time / 10)  # Decrease by 0.1 ul = 5 ms
        else:
            pump_duration = prev_pump_duration + (self.pump_time / 10)  # Increase by 0.1 ul = 5 ms

        # Clamp the pump duration between min and max values
        pump_duration = min(max(pump_duration, self._get_min_pump_duration()), self._get_max_pump_duration())
        return pump_duration

    def trigger_reward(self, curr_pump_duration):
        # todo call pump log
        GPIO.output(self.pump, GPIO.HIGH)
        time.sleep(curr_pump_duration / 1000)
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

    def adjust_pump_duration(self):
        if self.decision_var == self.bias_correction and self.bias_counter <= self.bias_counter_max:  # if the animal choose anti-bias side, give more reward
            curr_pump_duration = int(self.pump_duration * 2)
            self.bias_counter += 1  # only reward first x trials with higher volume
        else:
            curr_pump_duration = int(self.pump_duration)
        return curr_pump_duration
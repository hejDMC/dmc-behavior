import numpy as np
import threading
from sklearn import preprocessing
import time
import random
import RPi.GPIO as GPIO
import pandas as pd
from utils.encoder import Encoder
from utils.sync_pulse import Sync_Pulse
from data_io import DataIO
from logger import Logger
from stimulus_manager import StimulusManager
from reward_system import RewardSystem

# Base class for common elements in auditory tasks
class BaseAuditoryTask(threading.Thread):
    def __init__(self, animal_dir, task_type):
        threading.Thread.__init__(self)

        self.animal_dir = animal_dir
        self.task_type = task_type

        # todo: load path_manager?
        self.data_io = DataIO(self.animal_dir.parents[1], self.task_type)

        self.droid_settings = self.data_io.load_droid_setting()
        self.task_prefs = self.data_io.load_task_prefs()
        self.first_day = self.check_first_day()
        self.stage = self.get_stage()

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

    def check_first_day(self) -> bool:
        """
        Check if it is the first day of training for the animal.

        Returns:
            bool: True if today is considered the first day of training, otherwise False.
        """
        # Set threshold for what constitutes enough data to determine the training phase.
        MIN_ENTRIES_FOR_TRAINING = 3  # Example of giving '2' a meaningful name

        # Count the number of items in the animal directory
        num_entries = sum(1 for _ in self.animal_dir.iterdir())

        # If there are fewer than the required number of entries, default to first day
        if num_entries < MIN_ENTRIES_FOR_TRAINING:
            print("No habituation data or insufficient data found.")
            print("Defaulting to first_day=True")
            return True

        # Try to load metadata and determine the procedure type
        try:
            meta_data = self.data_io.load_meta_data()
            if meta_data.get('procedure', '').startswith('habituation'):
                return True  # First day of training if the last day was still habituation
            else:
                return False
        except (FileNotFoundError, KeyError, ValueError) as e:
            # Handle potential errors (e.g., file not found, JSON decoding error, missing keys)
            print(f"Error loading metadata: {e}")
            print("Defaulting to first_day=True due to missing or corrupt metadata")
            return True

    def get_stage(self) -> int:
        """
        Get the current stage of training for the animal.

        Returns:
            int: The current stage of training.
        """
        # Default to stage 0 if it's the first day
        if self.first_day:
            print("Stage: 0")
            return 0

        # Load metadata to determine the current stage
        try:
            meta_data = self.data_io.load_meta_data()
            curr_stage = meta_data.get('curr_stage', 0)  # Default to 0 if 'curr_stage' is missing
            stage_advance = meta_data.get('stage_advance', False)  # Default to False if 'stage_advance' is missing

            # Determine the current stage based on metadata
            if not stage_advance:
                stage = curr_stage
            else:
                stage = curr_stage + 1

        except (FileNotFoundError, KeyError, ValueError) as e:
            # Handle any errors in loading metadata
            print(f"Error loading metadata: {e}")
            print("Defaulting to stage 0")
            stage = 0

        print(f"Stage: {stage}")
        return stage

    def run(self):
        while not self.stop:
            self.execute_task()

    def execute_task(self):
        raise NotImplementedError("This method should be implemented by subclasses.")

    def stage_checker(self):
        raise NotImplementedError("This method should be implemented by subclasses.")





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
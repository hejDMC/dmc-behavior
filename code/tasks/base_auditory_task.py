
import threading, time
import random

import RPi.GPIO as GPIO

import numpy as np
import sounddevice as sd

from managers.utils.encoder import Encoder
from managers.logger import Logger
from managers.stimulus_manager import StimulusManager
from managers.reward_system import RewardSystem

# Base class for common elements in auditory tasks
class BaseAuditoryTask(threading.Thread):
    ENCODER_TO_DEGREE = 1024/360
    STAGE_0_TURNING_GOAL_ADJUST = 2
    def __init__(self, data_io, exp_dir, task_type):
        threading.Thread.__init__(self)
        self.data_io = data_io
        self.animal_dir = self.data_io.path_manager.check_dir()
        self.task_type = task_type

        self.droid_settings = self.data_io.load_droid_setting()
        self.task_prefs = self.data_io.load_task_prefs()
        self.first_day = self.check_first_day()
        self.stage = self.get_stage()
        self.stage_advance = False

        self.exp_dir = exp_dir

        # disengagement boolean
        self.disengage = False
        self.stop = False
        self.ending_criteria = "manual"

        # Components used by all tasks
        self.stimulus_manager = StimulusManager(self.task_prefs, self.droid_settings, self.data_io, exp_dir)

        self.reward_system = RewardSystem(self.data_io, self.task_type, self.droid_settings, self.task_prefs, self.first_day,
                                          self.stage)

        self.stim_strength = self.task_prefs['task_prefs']['stim_strength']
        self.cloud = []
        self.cloud_bool = False
        self.cancel_audio = False
        # punishment sound info
        self.punish_sound = self.task_prefs['task_prefs']['punishment_sound']
        self.punish_duration = self.task_prefs['task_prefs']['punishment_sound_duration']
        self.punish_amplitude = self.task_prefs['task_prefs']['punishment_sound_amplitude']

        # other task params
        self.target_position = None
        self.wheel_start_position = None
        self.iti = self.task_prefs['task_prefs']['inter_trial_interval']
        self.response_window = self.task_prefs['task_prefs']['response_window']

        # set encoder parameters and initialize pins (GPIO numbers!)
        self.encoder_data = Encoder(self.droid_settings['pin_map']['IN']['encoder_left'],
                                    self.droid_settings['pin_map']['IN']['encoder_right'])
        self.turning_goal = self.ENCODER_TO_DEGREE * self.task_prefs['encoder_specs']['target_degrees']  # threshold in degrees of wheel turn to count as 'choice' - converted into absolute values of 1024 encoder range
        if self.stage == 0:
            self.turning_goal = int(self.turning_goal / self.STAGE_0_TURNING_GOAL_ADJUST)

        # quiet window parameters
        self.quiet_window = self.task_prefs['task_prefs']['quiet_window']  # quiet window -> mouse needs to hold wheel still for x time, before new trial starts [0] baseline [1] exponential, as in IBL task
        self.quite_jitter = round(self.ENCODER_TO_DEGREE * self.task_prefs['encoder_specs']['quite_jitter'])  # jitter of allowed movements (input from json in degree; then converted into encoder range)
        self.animal_quiet = True


        self.logger = Logger(self.data_io, self.exp_dir)

        # Set GPIO mode
        # GPIO.setwarnings(False)
        # GPIO.setmode(GPIO.BCM)

        # data logging
        self.trial_data_fn = exp_dir.joinpath(f'{self.data_io.path_manager.get_today()}_trial_data.csv')
        self.tone_cloud_fn = exp_dir.joinpath(f'{self.data_io.path_manager.get_today()}_tone_cloud_data.csv')
        self.trial_num = 0
        self.trial_stat = [0, 0, 0]  # number of [correct, incorrect, omission] trials
        self.trial_start = 0
        self.trial_id = 0

        self.tone_played = 0
        self.decision_var = 0
        self.choice = 0
        self.reward_time = 0
        self.curr_iti = 0



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

    def get_target_cloud(self):
        """
        Determine the current stimulus strength based on the stage, and create the corresponding tone cloud.

        Returns:
            The generated tone cloud.
        """
        if self.task_type == 'auditory_2afc':
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
            tgt_octave = 2 if self.trial_id == 'high' else 0

            # Create the tone cloud
            self.cloud = self.stimulus_manager.create_tone_cloud(tgt_octave, self.curr_stim_strength)

            return self.cloud
        else:
            curr_stim_strength = self.stim_strength[0]
            if self.task_type == 'auditory_gonogo':
                tgt_octave = 2 if self.trial_id == 'high' else 0
            else:
                tgt_octave = 1
            self.cloud = self.stimulus_manager.create_tone_cloud(tgt_octave, curr_stim_strength)

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

    def play_tone(self, tone, duration, amplitude):
        audio = self.stimulus_manager.create_tone(int(tone), duration, amplitude)
        # print(str(tone))
        sd.play(audio, self.stimulus_manager.fs, blocking=True)

    def callback(self, outdata, frames, time, status):
        # callback function for audio stream
        if self.cancel_audio:
            raise sd.CallbackStop()
        outdata[:] = np.column_stack((self.cloud, self.cloud))  # two channels

    def check_disengage(self, criteria_variable):
        if self.task_type == 'auditory_2afc':
            sess_median = pd.DataFrame(criteria_variable).median()  # median of reaction times of session
            roll_median = pd.DataFrame(criteria_variable).rolling(20).median()  # rolling median (window=20) of reaction times
            if (sess_median[0]*4) < roll_median.iloc[-1][0]:  # check if last roll_median is > 4x the session median todo check if this makes sense, or rather 3x
                self.disengage = True  # set disengage bool to True
            elif roll_median.iloc[-1][0] >= self.response_window:
                self.disengage = True
            else:
                self.disengage = False  # can be reversed (for now..)
        else:
            if np.sum(criteria_variable[-20:]) < 4:  # value of 4 corresponds to 4x moved_wheel responses
                self.disengage = True  # set disengage bool to True
            else:
                self.disengage = False  # can be reversed (for now..)
        return self.disengage

    def run(self):
        while not self.stop:
            self.execute_task()

    def execute_task(self):
        raise NotImplementedError("This method should be implemented by subclasses.")

    def stage_checker(self):
        raise NotImplementedError("This method should be implemented by subclasses.")






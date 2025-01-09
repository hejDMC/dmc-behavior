
import threading
import RPi.GPIO as GPIO
from utils.encoder import Encoder
from logger import Logger
from stimulus_manager import StimulusManager
from reward_system import RewardSystem

# Base class for common elements in auditory tasks
class BaseAuditoryTask(threading.Thread):
    ENCODER_TO_DEGREE = 1024/360
    STAGE_0_TURNING_GOAL_ADJUST = 2
    def __init__(self, data_io, exp_dir, task_type):
        threading.Thread.__init__(self)
        self.data_io = data_io
        self.animal_dir = self.data_io.path_manager.get_animal_dir()
        self.task_type = task_type

        self.droid_settings = self.data_io.load_droid_setting()
        self.task_prefs = self.data_io.load_task_prefs()
        self.first_day = self.check_first_day()
        self.stage = self.get_stage()
        self.stage_advance = False

        self.exp_dir = exp_dir

        self.stop = False
        self.ending_criteria = "manual"

        # Components used by all tasks
        self.stimulus_manager = StimulusManager(self.task_prefs, self.droid_settings)

        self.reward_system = RewardSystem(self.animal_dir, self.task_type, self.droid_settings, self.task_prefs, self.first_day,
                                          self.stage)
        self.pump_duration = self.reward_system.pump_duration

        self.stim_strength = self.task_prefs['task_prefs']['stim_strength']
        self.cloud = []
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
        self.encoder_left = self.droid_settings['pin_map']['IN']['encoder_left']  # pin of left encoder (green wire)
        self.encoder_right = self.droid_settings['pin_map']['IN']['encoder_right']  # pin of right encoder (gray wire)
        self.encoder_data = Encoder(self.encoder_left, self.encoder_right)
        self.turning_goal = self.ENCODER_TO_DEGREE * self.task_prefs['encoder_specs']['target_degrees']  # threshold in degrees of wheel turn to count as 'choice' - converted into absolute values of 1024 encoder range
        if self.stage == 0:
            self.turning_goal = int(self.turning_goal / self.STAGE_0_TURNING_GOAL_ADJUST)

        # quiet window parameters
        self.quiet_window = self.task_prefs['task_prefs']['quiet_window']  # quiet window -> mouse needs to hold wheel still for x time, before new trial starts [0] baseline [1] exponential, as in IBL task
        self.quite_jitter = round(self.ENCODER_TO_DEGREE * self.task_prefs['encoder_specs']['quite_jitter'])  # jitter of allowed movements (input from json in degree; then converted into encoder range)
        self.animal_quiet = True


        self.logger = Logger(self.animal_dir, self.exp_dir)

        # Set GPIO mode
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

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



    def run(self):
        while not self.stop:
            self.execute_task()

    def execute_task(self):
        raise NotImplementedError("This method should be implemented by subclasses.")

    def stage_checker(self):
        raise NotImplementedError("This method should be implemented by subclasses.")






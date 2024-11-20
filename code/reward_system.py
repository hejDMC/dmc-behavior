import time
import pandas as pd
import RPi.GPIO as GPIO

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
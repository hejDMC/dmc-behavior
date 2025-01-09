import json
from pathlib import Path


class DataIO:
    DROID_SETTINGS = 'droid_settings'
    def __init__(self, path_manager, task_type: str):
        """
        Initialize with a base directory and task type.
        Parameters:
            base_dir (Path): todo: change
            task_type (str): The type of task for this handler.
            animal_id (str): ID of the animal.
        """
        self.path_manager = path_manager
        self.task_type = task_type
        self.animal_dir = self.path_manager.check_dir()


    def load_droid_setting(self) -> dict:
        """Load droid settings from a JSON file."""
        droid_prefs_path = self.path_manager.base_dir.joinpath(self.DROID_SETTINGS, 'droid_prefs.json')
        if droid_prefs_path.exists():
            with open(droid_prefs_path, 'r') as f:
                return json.load(f)
        else:
            print(f"Warning: {droid_prefs_path} not found.")
            return {}

    def load_task_prefs(self) -> dict:
        """Load task preferences for a given task type."""
        task_prefs_path = self.path_manager.base_dir.joinpath(self.DROID_SETTINGS, f'{self.task_type}_prefs.json')
        if task_prefs_path.exists():
            with open(task_prefs_path, 'r') as f:
                return json.load(f)
        else:
            print(f"Warning: {task_prefs_path} not found.")
            return {}

    def load_pump_calibration(self) -> int:
        """Load the most recent pump calibration value."""
        pump_cali_dir = self.path_manager.base_dir.joinpath('data', 'pump_calibration')  # directory with stored pump calibration data
        try:
            pump_cali_fn = sorted([f for f in pump_cali_dir.glob('*.json')])[-1]  # load last, most recent file
            with open(pump_cali_fn, 'r') as fn:
                pump_dict = json.load(fn)
            pump_time = [v for v in pump_dict.values()][0]
        except IndexError:
            print("no pump calibration data found! a default value of 50 ms equaling the delivery 1 ul will be used. "
                  "perform pump calibration to use correct values.")
            pump_time = 50
        return pump_time

    def load_response_matrix(self, in_task: bool = False) -> tuple:
        """Load the response matrix for a given animal ID."""

        response_matrix_path = self.animal_dir.joinpath(f"{self.animal_dir.stem}_response_matrix.json")
        pre_reversal = True
        if response_matrix_path.exists():
            with open(response_matrix_path, 'r') as f:
                response_matrix = json.load(f)
            if pre_reversal:
                response_matrix = response_matrix['pre_reversal']
            else:
                response_matrix = response_matrix['post_reversal']
            return response_matrix, pre_reversal
        else:
            print(f"Warning: Response matrix for animal {self.animal_dir.stem} not found.")
            return {}, pre_reversal


    def load_meta_data(self) -> dict:
        # load meta data from last day
        last_exp_day = sorted([day for day in self.animal_dir.iterdir() if day.is_dir()])[-1]
        last_exp_id = sorted([exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()])[-1]
        try:
            meta_data_file = [f for f in last_exp_id.glob('*_meta-data.json')][0]
            with open(meta_data_file) as fn:
                meta_data = json.load(fn)
        except IndexError:
            print(f'WARNING - no meta_data file found on {last_exp_day.parts[-1]} -- trying to load previous day')
            last_exp_day = sorted([day for day in self.animal_dir.iterdir() if day.is_dir()])[-2]
            last_exp_id = sorted([exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()])[-1]
            try:
                meta_data_file = [f for f in last_exp_id.glob('*_meta-data.json')][0]
                with open(meta_data_file) as fn:
                    meta_data = json.load(fn)
            except IndexError:
                print("no meta data on two successive days! using default meta data:")
                task_prefs = self.load_task_prefs()
                meta_data = {
                    "animal_id": self.animal_dir.parts[-1],
                    "droid": "dummy",
                    "procedure": self.task_type,
                    "# trials": 0,
                    "trial_statistics": [
                        0,
                        0,
                        0
                    ],
                    "pump_duration": task_prefs['task_prefs']['pump_duration'][0],
                    "bias_correction": False,
                    "ITI_range": task_prefs['task_prefs']['inter_trial_interval'],
                    "pre_reversal": True,
                    "ending_criteria": "disengagement",
                    "curr_stage": 0,
                    "stage_advance": False
                }
        return meta_data


    def store_pref_data(self, exp_dir: Path) -> None:
        """Store preference data for the session."""
        droid_prefs = self.load_droid_setting()
        task_prefs = self.load_task_prefs()
        save_path = exp_dir.joinpath(f'droid_and_task_prefs.json')
        with open(save_path, 'w') as f:
            json.dump({"droid_prefs": droid_prefs, "task_prefs": task_prefs}, f, indent=4)

    def store_meta_data(self, droid, start_time, end_time, exp_dir, task_obj, sync_bool, camera_bool,
                    ending_criteria=None, procedure="not specified", pre_reversal="not specified",
                    habi_day=None, experimenter='not specified'):

        """Store metadata for the session in a JSON file."""
        meta_data = {
            "animal_id": self.animal_dir.stem,
            "droid": droid,
            "experimenter": experimenter,
            "procedure": procedure,
            "date": self.path_manager.get_today(),
            "start": start_time,
            "end": end_time,
            "2p_sync_record": sync_bool,
            "camera_data": camera_bool,
            "# trials": getattr(task_obj, "trial_num", "not specified"),
            "pump_duration": int(getattr(task_obj, "pump_duration", 0)),
            "ITI_range": getattr(task_obj, "iti", "not specified"),
        }

        # Update metadata based on procedure type
        if procedure == "habituation_auditory_tasks":
            meta_data.update({
                "habi_day": habi_day,
            })
        elif procedure == 'auditory_2afc':
            meta_data.update({
                "trial_statistics": getattr(task_obj, "trial_stat", "not specified"),
                "bias_correction": getattr(task_obj, "bias_correction", "not specified"),
                "pre_reversal": pre_reversal,
                "ending_criteria": ending_criteria,
                "curr_stage": getattr(task_obj, "stage", "not specified"),
                "stage_advance": getattr(task_obj, "stage_advance", "not specified")
            })
        elif procedure == 'auditory_gonogo':
            meta_data.update({
                "trial_statistics": getattr(task_obj, "trial_stat", "not specified"),
                "pre_reversal": pre_reversal,
                "reversal_advance": False,  # todo: implement logic for this based on performance criteria
                "ending_criteria": ending_criteria,
                "curr_stage": getattr(task_obj, "stage", "not specified"),
                "stage_advance": getattr(task_obj, "stage_advance", "not specified")
            })
        else:
            # General case for other procedures
            meta_data.update({
                "trial_statistics": getattr(task_obj, "trial_stat", "not specified"),
                "ending_criteria": ending_criteria,
                "curr_stage": getattr(task_obj, "stage", "not specified"),
                "stage_advance": getattr(task_obj, "stage_advance", "not specified")
            })

        meta_data_path = exp_dir.joinpath( f'{self.path_manager.get_today()}_{self.animal_dir.stem}_meta-data.json')
        with open(meta_data_path, 'w') as f:
            json.dump(meta_data, f, indent=4)

    def load_trial_header(self):
        """
        Dummy function to load headers for trial data files for tasks
        :param task_id: str
        :return: trial_header: list
        """
        if '2afc' in self.task_type:
            trial_header = ["time", "trial_num", "trial_start", "trial_type", "stim_strength", "tone_onset",
                            "decision", "choice", "reward_time", "inter_trial_intervall", "block"]
        else:  # detection and gonogo
            trial_header = ["time", "trial_num", "trial_start", "trial_type", "tone_onset", "decision", "choice",
                            "left_right", "reward_time", "inter_trial_intervall"]
        return trial_header
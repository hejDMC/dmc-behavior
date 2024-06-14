
from pathlib import Path
import json
from shutil import copyfile
import pandas as pd
from utils import check_dir, get_today

def load_droid_setting():
    """
    Dummy function to load droid settings
    :return: droid_settings: dict
    """
    droid_dir = (Path(__file__).parent / '../../droid_settings').resolve()   # os.path.abspath(os.path.join(os.path.dirname(__file__), '../../droid_settings'))
    droid_file = droid_dir.joinpath('droid_prefs.json')

    with open(droid_file, 'r') as fn:
        droid_settings = json.load(fn)
    return droid_settings


def load_task_prefs(task_type):
    """
    Function to load task_prefs.json file
    :param task_type: str
    :return: task_prefs: dict
    """
    task_prefs_dir = (Path(__file__).parent / '../../droid_settings').resolve()  # os.path.abspath(os.path.join(os.path.dirname(__file__), '../../droid_settings'))
    task_prefs_file = task_prefs_dir.joinpath(f'{task_type}_prefs.json')

    with open(task_prefs_file, 'r') as fn:
        task_prefs = json.load(fn)
    return task_prefs


def load_pump_calibration():
    """
    Function to retrieve most recent pump calibration value. Important to set pump opening time correctly
    :return: pump_time: int
    """
    pump_cali_dir = (Path(__file__).parent / '../../data/pump_calibration').resolve()  # directory with stored pump calibration data
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

def load_response_matrix(animal_id, in_task=False):
    """
    Function to load response_matrix of animal defining auditory stim. to behavioral assignment
    :param animal_id: str
    :param in_task: bool
    :return: response_matrix: dict
    :return: pre_reversal: bool
    """

    animal_dir = check_dir(animal_id)
    # uncomment if wanting to include reversal after some criteria is reached, also requires some modifications in task files
    # if in_task:  # if in_task true, ask question of pre-or-post reversal
      #  pre_reversal = pre_post_reversal(animal_id)
    #else:
    #    pre_reversal = True  # for training always do pre-reversal
    pre_reversal = True
    resp_matrix_fn = animal_dir.joinpath(f'{animal_id}_response_matrix.json')
    with open(resp_matrix_fn) as json_file:
        response_matrix = json.load(json_file)

    if pre_reversal:
        print(">>>>>>>>   ANIMAL ON PRE-REVERSAL    <<<<<<<<<<<<")
        response_matrix = response_matrix['pre_reversal']
    else:
        print(">>>>>>>>   ANIMAL ON POST-REVERSAL    <<<<<<<<<<<<")
        response_matrix = response_matrix['post_reversal']

    return response_matrix, pre_reversal

def pre_post_reversal(animal_id):
    """
    Function to state if animal is pre or post reversal, not called unless parts in load_response_matrix() are uncommented,
    further adjustments in code necessary
    :param animal_id: str
    :return: pre_reversal: bool
    """
    # old manual option for entering reversal stage
    animal_dir = check_dir(animal_id)
    last_exp_day = sorted(animal_dir.iterdir())[-3]
    last_exp_id = sorted((animal_dir / last_exp_day).iterdir())[-1]
    exp_dir = animal_dir.joinpath(last_exp_day, last_exp_id)
    meta_data_file = exp_dir.joinpath(f'{last_exp_day}_{animal_id}_meta-data.json')
    if meta_data_file.exists():  # load meta data if it exists
        with open(meta_data_file) as fn:
            meta_data = json.load(fn)
            if not meta_data['procedure'].startswith('habituation'):  # when animal is in the training stage
                if not meta_data['pre_reversal']:  # check if it's already on reversal in the last session, then continue
                    pre_reversal = False
                else:  # if animal is still on preversal, check the boolean if it should be set on pre-reversal
                    if meta_data['reversal_advance']:
                        pre_reversal = False
                    else:
                        pre_reversal = True
            else:
                print("assuming first day of experiment, put animal on pre-reversal!")
                pre_reversal = True
    else:
        print("automatic assignment not possible, defaulting to manual reversal setting")
        p_r = input("are we pre-reversal? y/n:")
        while True:
            if p_r == 'y':
                pre_reversal = True
                break
            elif p_r == 'n':
                pre_reversal = False
                break
            else:
                print("please enter 'y' or 'n'")
            p_r = input("are we pre-reversal? y/n:")
    return pre_reversal

def load_meta_data(animal_dir, task_id):
    # load meta data from last day
    last_exp_day = sorted([day for day in animal_dir.iterdir() if day.is_dir()])[-1]
    last_exp_id = sorted([exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()])[-1]
    try:
        meta_data_file = [f for f in last_exp_id.glob('*_meta-data.json')][0]
        with open(meta_data_file) as fn:
            meta_data = json.load(fn)
    except IndexError:
        print(f'WARNING - no meta_data file found on {last_exp_day.parts[-1]} -- trying to load previous day')
        last_exp_day = sorted([day for day in animal_dir.iterdir() if day.is_dir()])[-2]
        last_exp_id = sorted([exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()])[-1]
        try:
            meta_data_file = [f for f in last_exp_id.glob('*_meta-data.json')][0]
            with open(meta_data_file) as fn:
                meta_data = json.load(fn)
        except IndexError:
            print("no meta data on two successive days! using default meta data:")
            task_prefs = load_task_prefs(task_id)
            meta_data = {
                "animal_id": animal_dir.parts[-1],
                "droid": "dummy",
                "procedure": task_id,
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

def store_reaction_times(exp_dir, task):  # todo delete?
    """
    Function to save reaction times of a session
    :param exp_dir: Path
    :param task:
    :return:
    """
    file_name = f'{get_today()}_reaction-times.csv'
    file_path = exp_dir.joinpath(file_name)
    df = pd.DataFrame(task.reaction_times[1:])
    df.to_csv(file_path)


def store_pref_data(exp_dir, procedure ="NaN"):
    """
    Store droid prefs for session
    :param exp_dir: Path
    :param procedure: str
    :return:
    """

    # copy the droid prefs file into the exp_dir
    droid_dir = (Path(__file__).parent / '../../droid_settings').resolve()   # os.path.abspath(os.path.join(os.path.dirname(__file__), '../droid_settings'))
    droid_prefs_file = droid_dir.joinpath('droid_prefs.json')
    exp_dir_droid = exp_dir.joinpath('droid_prefs.json')
    copyfile(str(droid_prefs_file), str(exp_dir_droid))
    # copy the task prefs too
    task_prefs_file = droid_dir.joinpath(f'{procedure}_prefs.json')
    exp_dir_task = exp_dir.joinpath(f'{procedure}_prefs.json')
    try:
        copyfile(str(task_prefs_file), str(exp_dir_task))
    except FileNotFoundError:
        print(f'{str(task_prefs_file)} -- TASK PREF FILE NOT FOUND!')
        pass

#todo hifi clouds habi stuff
def store_meta_data(animal_id, droid, start_time, end_time, exp_dir, task_obj, sync_bool, camera_bool,
                    ending_criteria = None, procedure ="not specified", pre_reversal = "not specified",
                    habi_day=None, experimenter='not specified'):
    # todo do some if loop or so depending on procedure type
    if procedure == "habituation_auditory_tasks":
        data_dict = {
            "animal_id": animal_id,
            "droid": droid,
            "experimenter": experimenter,
            "procedure": procedure,
            "habi_day": habi_day,
            "date": get_today(),
            "start": start_time,
            "end": end_time,
            "2p_sync_record": sync_bool,
            "camera_data": camera_bool,
            "# trials": task_obj.trial_num,
            "pump_duration": int(task_obj.pump_duration),
            "ITI_range": task_obj.iti
        }
    elif procedure == 'auditory_2afc':
        data_dict = {
            "animal_id": animal_id,
            "droid": droid,
            "experimenter": experimenter,
            "procedure": procedure,
            "date": get_today(),
            "start": start_time,
            "end": end_time,
            "2p_sync_record": sync_bool,
            "camera_data": camera_bool,
            "# trials": task_obj.trial_num,
            "trial_statistics": task_obj.trial_stat,
            "pump_duration": int(task_obj.pump_duration),
            "bias_correction": task_obj.bias_correction,
            "ITI_range": task_obj.iti,
            "pre_reversal": pre_reversal,
            "ending_criteria": ending_criteria,
            "curr_stage": task_obj.stage,
            "stage_advance": task_obj.stage_advance
        }
    elif procedure == 'auditory_gonogo':
        data_dict = {
            "animal_id": animal_id,
            "droid": droid,
            "experimenter": experimenter,
            "procedure": procedure,
            "date": get_today(),
            "start": start_time,
            "end": end_time,
            "2p_sync_record": sync_bool,
            "camera_data": camera_bool,
            "# trials": task_obj.trial_num,
            "trial_statistics": task_obj.trial_stat,
            "pump_duration": int(task_obj.pump_duration),
            "ITI_range": task_obj.iti,
            "pre_reversal": pre_reversal,
            "reversal_advance": False,  # todo this based on performance criteria
            # "reversal_criterium": task_obj.reversal_criterium,
            "ending_criteria": ending_criteria,
            "curr_stage": task_obj.stage,
            "stage_advance": task_obj.stage_advance
        }
    else:
        data_dict = {
            "animal_id": animal_id,
            "droid": droid,
            "experimenter": experimenter,
            "procedure": procedure,
            "date": get_today(),
            "start": start_time,
            "end": end_time,
            "2p_sync_record": sync_bool,
            "camera_data": camera_bool,
            "# trials": task_obj.trial_num,
            "trial_statistics": task_obj.trial_stat,
            "pump_duration": int(task_obj.pump_duration),
            "ITI_range": task_obj.iti,
            "ending_criteria": ending_criteria,
            "curr_stage": task_obj.stage,
            "stage_advance": task_obj.stage_advance
        }
    file_name = f'{get_today()}_{animal_id}_meta-data.json'
    file_path= exp_dir.joinpath(file_name)
    with open(file_path, "w") as outfile:
        json.dump(data_dict, outfile, indent=4)


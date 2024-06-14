"""
Helper functions for behavioral tasks

FJ
"""

import os
from pathlib import Path
from datetime import date, datetime
import pandas as pd
import asciichartpy as acp
import math
import json
from shutil import copyfile
# from utils.utilsIO import load_meta_data, load_pump_calibration


def check_dir(animal_id):
    """
    Function to check if directory for storing animal data exists, and create if it doesn't
    :param animal_id: str
    :return: animal_dir: Path
    """

    data_directory = (Path(__file__).parent / '../../data').resolve()  # os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../data'))
    animal_dir = data_directory.joinpath(animal_id)
    if animal_dir.exists():
        pass
    else:
        animal_dir.mkdir()
    return animal_dir


def make_exp_dir(animal_dir):
    """
    Create directory to store experimental data

    :param animal_dir: Path
    :return: exp_dir: Path
    """
    date_dir = animal_dir.joinpath(get_today())  # store data in folders per day
    exp_dir = date_dir.joinpath(get_hours())
    exp_dir.mkdir(parents=True)

    return exp_dir


def get_today():
    """
    Dummy function to get date in YYYYMMDD format
    :return: today: str
    """
    datetime_format = '%Y%m%d'
    today = date.today().strftime(datetime_format)
    return today


def get_hours():
    """
    Dummy function to get current timestamp in HHMMSS format
    :return: hrs: str
    """
    hour_format = "%H%M%S"
    now = datetime.now()
    hrs = now.strftime(hour_format)
    return hrs

def start_option(device):
    '''
    Function for setting options of whether to trigger camera frames/record pulses from 2p
    input: device (str) - name and function of device one wants to trigger/record
    :return: booleans for recording y/n
    '''
    if device == 'sync_pulse':
        question_str = "do you record sync pulses from the 2p? y/n:"
    elif device == 'camera_trigger':
        question_str = "do you want to trigger camera frames? y/n:"
    else:
        print("Error: device needs to be either 'sync_pulse' or 'camera_trigger'")
        return
    d_b = input(question_str)

    while True:
        if d_b == 'y':
            device_bool = True
            break
        elif d_b == 'n':
            device_bool = False
            break
        else:
            print("please enter 'y' or 'n'")
        d_b = input(question_str)
    return device_bool


def check_first_day(animal_dir, task_id):

    if len(animal_dir.iterdir()) > 2:
        meta_data = load_meta_data(animal_dir, task_id)
        if meta_data['procedure'].startswith('habituation'):
            first_day = True  # first day of training if last day was still habituation
        else:
            first_day = False
    else:
        print("No habituation data???")
        print("Defaulting to first_day=True")
        first_day = True
    return first_day

def get_stage(animal_dir, task_id, first_day):
    # load previous data and get the stage
    if not first_day:
        meta_data = load_meta_data(animal_dir, task_id)
        try:
            if not meta_data['stage_advance']:
                stage = meta_data['curr_stage']
            elif meta_data['stage_advance']:
                stage = meta_data['curr_stage'] + 1
        except KeyError:
            print("NO STAGE CRITERIA IN META DATA, DEFAULTING TO STAGE 0")
            stage = 0
    else:
        stage = 0
    print("Stage: "+str(stage))
    return stage

def load_trial_header(task_id):
    """
    Dummy function to load headers for trial data files for tasks
    :param task_id: str
    :return: trial_header: list
    """
    if task_id == '2afc':
        trial_header = ["time", "trial_num", "trial_start", "trial_type", "stim_strength", "tone_onset",
                             "decision", "choice", "reward_time", "inter_trial_intervall", "block"]
    else:  # detection and gonogo
        trial_header = ["time", "trial_num", "trial_start", "trial_type", "tone_onset", "decision", "choice",
                        "reward_time", "inter_trial_intervall"]
    return trial_header

def plot_behavior_terminal(exp_dir, task_id):
    """
    Function to plot behavioral performance of animal after session in terminal
    :param exp_dir: Path
    :param trial_data_header: list
    """
    # load the trial data
    trial_data_file = exp_dir.joinpath(f'{get_today()}_trial_data.csv')
    trial_data_header = load_trial_header(task_id)
    trial_data = pd.read_csv(trial_data_file, names=trial_data_header)
    trial_times = trial_data[trial_data['trial_start'] == 1].reset_index()
    # correct choices
    c = trial_times['choice'].copy()
    c[c != 'correct'] = 0
    c[c == 'correct'] = 100
    c_mean = c.rolling(10).mean().fillna(0)
    # incorrect
    i = trial_times['choice'].copy()
    i[i != 'incorrect'] = 0
    i[i == 'incorrect'] = 100
    i_mean = i.rolling(10).mean().fillna(0)
    # omission
    o = trial_times['choice'].copy()
    o[o != 'undecided'] = 0
    o[o == 'undecided'] = 100
    o_mean = o.rolling(10).mean().fillna(0)

    t_size = os.get_terminal_size().columns  # size of terminal to adjust for plotting
    scale_factor = math.ceil(len(c_mean) / t_size)
    plot_series = [c_mean[::scale_factor].to_list(), i_mean[::scale_factor].to_list(), o_mean[::scale_factor].to_list()]  # only plot every nth value, depending on terminal size, to avoid that plotting is messed up by breaking on columns
    config = {'height': 10, 'format': '{:8.0f}', 'colors': [acp.green, acp.red, acp.lightgray]}  # correct is green, incorrect is red, omission gray
    print(acp.plot(series=plot_series, cfg=config))

    # print also some basic performance info
    print(trial_times['choice'][1:].value_counts().to_string())
    print(trial_times['trial_type'][1:].value_counts().to_string())
    print(trial_times['decision'][1:].value_counts().to_string())

    # print the total consumed volume
    pump_data_header = ["time", "pump_duration"]
    pump_data_file = exp_dir.joinpath(f'{get_today()}_pump_data.csv')
    pump_data = pd.read_csv(pump_data_file, names=pump_data_header)
    pump_time = load_pump_calibration()
    amount_reward = pump_data['pump_duration'].sum() / pump_time
    print('Amount consumed total volume: ' + str(amount_reward))





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







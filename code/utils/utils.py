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
from .utilsIO import load_meta_data, load_pump_calibration


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







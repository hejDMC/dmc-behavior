"""
Helper functions for dmc-behavior tasks

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
import random
import numpy as np

# from utils.utilsIO import load_meta_data, load_pump_calibration

#%% general/random functions

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

def plot_behavior_terminal(data_io, exp_dir):
    """
    Function to plot behavioral performance of animal after session in terminal
    :param exp_dir: Path
    :param trial_data_header: list
    """
    # load the trial data
    trial_data_file = exp_dir.joinpath(f'{data_io.path_manager.get_today()}_trial_data.csv')
    trial_data_header = data_io.load_trial_header()
    df=pd.read_csv(trial_data_file)
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
    pump_data_file = exp_dir.joinpath(f'{data_io.path_manager.get_today()}_pump_data.csv')
    pump_data = pd.read_csv(pump_data_file, names=pump_data_header)
    pump_time = data_io.load_pump_calibration()
    amount_reward = pump_data['pump_duration'].sum() / pump_time
    print('Amount consumed total volume: ' + str(amount_reward))


#%% utils for habituation

def get_habi_task():
    p_r = input("2afc task (no assumes gonogo/detection)? y/n:")
    while True:
        if p_r == 'y':
            task = '2afc'
            break
        elif p_r == 'n':
            task = 'gonogo'
            break
        else:
            print("please enter 'y' or 'n'")
        p_r = input("2afc task (no assumes gonogo/detection)? y/n:")
    return task

def habi_time_limit():
    '''
    Function to set the day of habituation and return the time limit (day 1: 15 min; day 2: 30 min; day 3: 60 min)
    to automatically terminate the script
    :return: habi_day: int
    :return: time_limit: int
    '''

    question_str = "what day of habituation is it (1/2/3)?:"
    habi_day = int(input(question_str))
    while True:
        if habi_day == 1:
            time_limit = 15  # min
            break
        elif habi_day == 2:
            time_limit = 30  # min
            break
        elif habi_day == 3:
            time_limit = 45  # min
            break
        else:
            print("please enter only the int (1, 2 or 3)")
        habi_day = input(question_str)

    return habi_day, time_limit



#%% helpers for 2afc task












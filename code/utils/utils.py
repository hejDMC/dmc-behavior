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
from .psychofit import mle_fit_psycho, weibull, weibull50, erf_psycho, erf_psycho_2gammas
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







def plot_behavior_terminal(exp_dir, task_id):
    """
    Function to plot behavioral performance of animal after session in terminal
    :param exp_dir: Path
    :param trial_data_header: list
    """
    # load the trial data
    trial_data_file = exp_dir.joinpath(f'{get_today()}_trial_data.csv')
    trial_data_header = load_trial_header(task_id)
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
    pump_data_file = exp_dir.joinpath(f'{get_today()}_pump_data.csv')
    pump_data = pd.read_csv(pump_data_file, names=pump_data_header)
    pump_time = load_pump_calibration()
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

def get_bias_correction(animal_dir, first_day):
    # load previous data and check if animal displayed a strong bias towards on side (> 70 % of non-omission trials towards one side)
    if not first_day:  # if not the first day of training
        last_exp_day = sorted([day for day in animal_dir.iterdir() if day.is_dir()])[-1]
        last_exp_id = sorted([exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()])[-1]
        try:
            trial_data_file = [f for f in last_exp_id.glob('*_trial_data.csv')][0]
        except IndexError:
            print("no previous trial data found, no bias_correction")
            bias_correction = False
            return bias_correction

        trial_data_header = load_trial_header('2afc')
        trial_data = pd.read_csv(trial_data_file, names=trial_data_header)
        trial_times = trial_data[trial_data['trial_start'] == 1].reset_index()
        try:
            left_choices = trial_times['decision'].value_counts()['left']  # number of left choices
        except KeyError:
            left_choices = 0
        try:
            right_choices = trial_times['decision'].value_counts()['right']  # number of right choices
        except KeyError:
            right_choices = 0
        try:
            prop_left_choices = left_choices / (left_choices + right_choices)  # proportion of left choices
        except ZeroDivisionError:
            prop_left_choices = 0.5
        if prop_left_choices > 0.85:  # more than 85 % left choices
            bias_correction = 'right'  # so reward rightward trials
        elif prop_left_choices < 0.15:  # and vice versa
            bias_correction = 'left'
        else:
            bias_correction = False  # no bias
    else:
        bias_correction = False  # no bias when first day of training
    print("bias correction:" + str(bias_correction))
    return bias_correction

# def load_response_matrix(animal_dir):
#     animal_id = animal_dir.parts[-1]
#     response_matrix_fn = animal_dir.joinpath(animal_id + '_response_matrix.json')
#     with open(response_matrix_fn) as fn:
#         response_matrix = json.load(fn)
#
#     return response_matrix

def get_right_trials(response_matrix, c_rm=False):
    curr_rm = response_matrix['pre_reversal']  # todo, so far no reversal
    right_trials = list(curr_rm.keys())[list(curr_rm.values()).index('right')]
    if c_rm:
        return right_trials, curr_rm
    else:
        return right_trials


def create_trial_file(trial_data, trial_data_header, task_id, response_matrix):

    trial_times = trial_data[trial_data['trial_start'] == 1][
        trial_data_header[0:3]].reset_index().copy()  # get first columsn for trial start times etc
    # get other columns for statistics of that trial columns, not ITT for interval after trial (other columsn are input t+4 for start_idx
    idx = trial_data.index[trial_data['trial_start'] == 1].tolist()  # get indices of trial starts
    idx = idx[1:]  # delete the first value -> info for trial one is in idx=4
    idx.append(len(trial_data))  # add last entry from file
    idx = [i - 1 for i in idx]  # substract one to get to matching idx
    dummy_df = trial_data.iloc[idx][trial_data_header[3:]].reset_index(drop=True).copy()
    trial_times = pd.concat([trial_times, dummy_df], axis=1)
    if task_id == '2afc':
        right_trials = get_right_trials(response_matrix)
        trial_times['stim_strength'] = [int(stim) for stim in
                                        trial_times['stim_strength']]  # convert to integers from string
        trial_times.loc[trial_times['trial_type'] != right_trials, 'stim_strength'] = \
            trial_times.loc[trial_times['trial_type'] != right_trials, 'stim_strength'].apply(
                lambda x: 100 - x)
    # get time of trial start
    trial_times['tone_onset'] = trial_data[trial_data['tone_onset'] == 1]['time'].reset_index(drop=True).copy()
    # get time of reward delivery
    time_reward = []
    for i in [id-1 for id in idx]:  # -1 to get correct reward indices?
        if trial_data['choice'][i] == 'incorrect' or trial_data['decision'][i] == 'no_response':
            time_reward.append(0)
        else:
            time_reward.append(trial_data['time'][i])
    if trial_data['reward_time'].iloc[-2] == 0:
        time_reward.append(0)
    else:
        time_reward.append(trial_data['time'].iloc[-2])
    trial_times['reward_time'] = pd.DataFrame(time_reward)
    decision_idx = trial_data[trial_data['tone_onset'] == 1].index + 1
    trial_times['decision_time'] = trial_data['time'][decision_idx].reset_index(drop=True).copy()

    return trial_times

def load_trial_data(exp_dir, task_id, return_start_time = False, response_matrix = False):
    exp = exp_dir.parts[-2]
    trial_data_header = load_trial_header(task_id)
    trial_data_file = exp_dir.joinpath(exp + '_trial_data.csv')
    trial_data = pd.read_csv(trial_data_file, names=trial_data_header)

    start_time = trial_data['time'][0]
    trial_data['time'] = trial_data['time'] - start_time
    trial_times = create_trial_file(trial_data, trial_data_header, task_id, response_matrix)
    if return_start_time:
        return trial_times, start_time
    else:
        return trial_times


def get_performance_per_stim(trial_times, stim_list, block=0):
    """
    Function to calculate performance per stimulus class (i.e. per stim. strength), return % correct and number of
    trials per stimulus class
    :param trial_times: pd.DataFrame
    :param stim_list: list
    :param block: int
    :return: prob_right: list
    :return: num_trials: list
    """
    prob_right = []  # probability that mouse chooses right side
    num_trials = []  # number of trials for each stim level
    for stim in stim_list:
        temp_trial_times = trial_times[trial_times['block'] == block].copy()
        stim_perf = temp_trial_times[temp_trial_times['stim_strength'] == stim]['decision'].value_counts()
        if stim_perf.empty:  # no values as stim not in training stage
            prob_right.append(math.nan)
        else:
            try:
                prob_right.append(stim_perf['right'] / (stim_perf['right'] + stim_perf['left']))
                num_trials.append(stim_perf['right'] + stim_perf['left'])
            except KeyError:
                for s in stim_perf.keys():
                    if s == 'left':
                        prob_right.append(0.0)
                        num_trials.append(stim_perf['left'])
                    elif s == 'right':
                        prob_right.append(1.0)
                        num_trials.append(stim_perf['right'])

    return prob_right, num_trials


def check_stage_4_advance(animal_dir):
    """
    stage checker to advance to stage 5 (biased block design)
        - last three sessions > 400 trials, respectively
        - > 90 % on *both* 100 % trials, respectively
        - fit of joint psychometric curve with pars[0] < 5, pars[1] < 20 (??), pars[2]/[3] < 0.1
    """
    animal_id = animal_dir.parts[-1]
    response_matrix = load_response_matrix(animal_id)
    stim_list = [0, 15, 30, 40, 60, 70, 85, 100]
    p_model = 'erf_psycho_2gammas'
    dispatcher = {
        'weibull': weibull,
        'weibull50': weibull50,
        'erf_psycho': erf_psycho,
        'erf_psycho_2gammas': erf_psycho_2gammas
    }
    # get list of last three experiments
    exp_list = sorted(animal_dir.iterdir())[-4:-1]
    cnt = 0
    cnt_stage = 0
    trial_data = pd.DataFrame()
    for exp in exp_list:
        exp_path = sorted(exp.iterdir())[-1]  # there should be only one time point in the folder
        meta_file = [m for m in exp_path.glob('*_meta-data.json')][0]
        with open(meta_file) as fn:
            meta_data = json.load(fn)
        if meta_data["curr_stage"] == 4:  # needs to be on stage 4 for at least 3 sessions
            cnt_stage += 1
        n_trials = meta_data["# trials"]

        trial_times = load_trial_data(exp_path, '2afc', response_matrix=response_matrix)
        prob_right, num_trials = get_performance_per_stim(trial_times, stim_list)
        if n_trials > 300 and prob_right[0] < 0.2 and prob_right[-1] > 0.8:
            # if more than 300 trials and more than 80 % correct on both easy trials, add to counter
            cnt += 1
            trial_data = pd.concat((trial_data, trial_times))
    if cnt == 3 and cnt_stage == 3:
        print("trial number and easy trial performance good")
        trial_data = trial_data.reset_index(drop=True)
        prob_right, num_trials = get_performance_per_stim(trial_data, stim_list)
        pars, L = mle_fit_psycho(
            np.vstack([np.array(stim_list), np.array(num_trials), np.array(prob_right)]),  # 'erf_psycho_2gammas',
            P_model=p_model,  # weibull # Gauss error function
            nfits=10
        )
        # bias_val = dispatcher[p_model](pars, 50)  # get the 50 % value to estimate bias == ideally should be 50 for no bias
        # if 0.4 < bias_val < 0.6:
        (bias, slope, gamma1, gamma2) = pars
        if abs(bias-50) < 16 and slope < 19 and gamma1 < 0.2 and gamma2 < 0.2:
            stage_advance = True
            print(">>>>>  FINISHED STAGE 4 -- FINAL STAGE REACHED !!! <<<<<<<<<")
        else:
           stage_advance = False
    return stage_advance


def check_ready_for_experiment(animal_dir):
    """
    stage checker to advance to "ready for experiment status"
        - last three sessions > 400 trials
        - > 90 % on *all* 100 % trials (irrespective of blocks)
        - fit of joint psychometric curve with for both blocks: pars[2]/[3] < 0.1
        - bias shift: pars[0] diff between blocks > 5 ???
    """
    animal_id = animal_dir.parts[-1]
    response_matrix = load_response_matrix(animal_id)
    stim_list = [0, 15, 30, 40, 60, 70, 85, 100]
    p_model = 'erf_psycho_2gammas'
    dispatcher = {
        'weibull': weibull,
        'weibull50': weibull50,
        'erf_psycho': erf_psycho,
        'erf_psycho_2gammas': erf_psycho_2gammas
    }
    # get list of last three experiments
    exp_list = sorted(animal_dir.iterdir())[-4:-1]
    cnt_t_num = 0
    cnt_perf = 0
    cnt_stage = 0
    trial_data = pd.DataFrame()
    right_trials = []
    for exp in exp_list:
        exp_path = sorted(exp.iterdir())[-1]  # there should be only one time point in the folder
        meta_file = [m for m in exp_path.glob('*_meta-data.json')][0]
        with open(meta_file) as fn:
            meta_data = json.load(fn)
        if meta_data["curr_stage"] == 5:  # needs to be on stage 4 for at least 3 sessions
            cnt_stage += 1
        n_trials = meta_data["# trials"]

        trial_times = load_trial_data(exp_path, '2afc', response_matrix=response_matrix)
        if n_trials > 300:
            # if more than 400 trials and more than 90 % correct on both easy trials, add to counter
            cnt_t_num += 1
            trial_data = pd.concat((trial_data, trial_times))
        for block in [-1, 1]:
            prob_right, num_trials = get_performance_per_stim(trial_times, stim_list, block=block)
            if prob_right[0] < 0.2 and prob_right[-1] > 0.8:
                cnt_perf += 1
    if cnt_t_num == 3 and cnt_perf == 6 and cnt_stage == 3:
        print("trial number and easy trial performance good")
        trial_data = trial_data.reset_index(drop=True)
        bias_stats = {
            'bias_low': 0,
            'gamma1_low': 100,
            'gamma2_low': 100,
            'bias_high': 0,
            'gamma1_high': 100,
            'gamma2_high': 100
        }
        for block in [-1, 1]:
            prob_right, num_trials = get_performance_per_stim(trial_data, stim_list, block=block)
            pars, L = mle_fit_psycho(
                np.vstack([np.array(stim_list), np.array(num_trials), np.array(prob_right)]),
                # 'erf_psycho_2gammas',
                P_model=p_model,  # weibull # Gauss error function
                nfits=10
            )
            if block == -1:
                bias_stats['bias_low'] = pars[0]
                bias_stats['gamma1_low'] = pars[2]
                bias_stats['gamma2_low'] = pars[3]
                # bias_low = dispatcher[p_model](pars, np.arange(0, 100, 1))
            else:
                bias_stats['bias_high'] = pars[0]
                bias_stats['gamma1_high'] = pars[2]
                bias_stats['gamma2_high'] = pars[3]
                # bias_high = dispatcher[p_model](pars, np.arange(0, 100, 1))
        if right_trials == 'low':
            # right vs left block
            bias_shift = bias_stats['bias_low'] - bias_stats['bias_high']
            # bias_shift = [a - b for a, b in zip(bias_low, bias_high)]
        else:
            bias_shift = bias_stats['bias_high'] - bias_stats['bias_low']
            # bias_shift = [a - b for a, b in zip(bias_high, bias_low)]
        # if bias_shift[49] > 0.10:
        if bias_shift > 5 and (bias_stats['gamma1_low'] and bias_stats['gamma2_low'] and
                               bias_stats['gamma1_high'] and bias_stats['gamma2_high']) < 0.2:
            print("bias statistic good!")
            print(" >>>   ANIMAL READY FOR EXPERIMENT <<<<  ")
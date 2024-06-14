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
import random
import numpy as np
from .psychofit import mle_fit_psycho, weibull, weibull50, erf_psycho, erf_psycho_2gammas
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






def pitch_to_frequency(pitch):
    """
    Convert pitch to frequency
    :param pitch: int
    :return: frequency: float
    """
    middle_frequency = 261.625565  # middle C == C5
    frequency = 2 ** (int(pitch) / 12) * middle_frequency
    return frequency

def weighted_octave_choice(tgt_octave, stim_strength):
    """
    Function to select tones for tone clouds from tgt_octave depending on stim strength
    :param tgt_octave: int
    :param stim_strength: int
    :return: oct_id: int
    """
    # stim_strength is the prob. for tone on tgt_octave, (100-stim_strength) is prob. for non tgt stimuli, so divided by two as there are two 'off-target octaves"

    weight_matrix = [0, 0, 0] # initialize the weight matrix
    for i, w in enumerate(weight_matrix):
        if i == tgt_octave:
            weight_matrix[i] = stim_strength  # weighted prob. for tgt_octave is stim_strength
        else:
            weight_matrix[i] = int((100 - stim_strength) / 2)  # inverse/2 for other two octaves
    oct_id = random.choices(population=[0, 1, 2], weights=weight_matrix)  # draw oct. for current tone
    return oct_id[0]

def create_tone(fs, frequency, tone_duration, amplitude):
    """
     Function to create tones; adapted from: https://github.com/int-brain-lab/iblrig/blob/master/iblrig/sound.py
    --> using ramping of to avoid onset artefacts
    :param fs: int
    :param frequency:
    :param tone_duration:
    :param amplitude:
    :return:
    """


    fade = 0.1  # as percentage of tone_duration --> 10 %
    fade_duration = tone_duration * fade  # sec
    #
    tvec = np.linspace(0, tone_duration, int(tone_duration * fs))
    tone = amplitude * np.sin(2 * np.pi * frequency * tvec)  # tone vec
    #
    len_fade = int(fade_duration * fs)
    fade_io = np.hanning(len_fade * 2)
    fadein = fade_io[:len_fade]
    fadeout = fade_io[len_fade:]
    win = np.ones(len(tvec))
    win[:len_fade] = fadein
    win[-len_fade:] = fadeout
    #
    tone = tone * win
    ttl = np.ones(len(tone)) * 0.99
    one_ms = round(fs / 1000) * 10
    ttl[one_ms:] = 0
    #
    if frequency == -1:
        tone = amplitude * np.random.rand(tone.size)
    #
    sound = np.array(tone)
    audio = sound * (2 ** 15 - 1) / np.max(np.abs(sound))
    audio = audio.astype(np.int16)
    return audio





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
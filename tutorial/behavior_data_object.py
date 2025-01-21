import os, json
import pandas as pd
import numpy as np


class BehaviorData:
    def __init__(self, data_directory) -> None:
        self._data_directory = data_directory

    @property
    def where(self):
        return self._data_directory

    @property
    def twoafc(self):
        return TaskWrapper(os.path.join(self.where, '2afc'))

    @property
    def detection(self):
        return TaskWrapper(os.path.join(self.where, 'detection'))

    @property
    def gonogo(self):
        return TaskWrapper(os.path.join(self.where, 'gonogo'))


class TaskWrapper:
    def __init__(self, task_directory) -> None:
        self._task_directory = task_directory
        for animal in os.listdir(self._task_directory):
            if os.path.isdir(os.path.join(self._task_directory, animal)):
                setattr(self,
                        '_' + animal,
                        AnimalWrapper(os.path.join(self._task_directory, animal)))

    def list_animals(self):
        return os.listdir(self._task_directory)

    @property
    def task(self):
        return os.path.basename(self._task_directory)


class AnimalWrapper:
    def __init__(self, animal_directory) -> None:
        self._animal_directory = animal_directory
        self._id = os.path.basename(animal_directory)
        for session in os.listdir(self._animal_directory):
            if os.path.isdir(os.path.join(self._animal_directory, session)):
                setattr(self,
                        '_' + session,
                        SessionWrapper(os.path.join(self._animal_directory, session)))

    @property
    def id(self):
        return self._id

    def list_sessions(self):
        sessions = []
        for session in os.listdir(self._animal_directory):
            if session.endswith('.json'):
                pass
            elif session.endswith('.hdf5'):
                pass
            else:
                sessions.append(session)
        return sessions

    def list_stages(self):
        stages = {}
        for session in self.list_sessions():
            if getattr(self, '_' + session).meta_data['procedure'].startswith('habituation'):
                print('Habituation session:', session, ' has no stage data.')
            else:
                stages[session] = dict(curr_stage=getattr(self, '_' + session).meta_data['curr_stage'])
        return stages


class SessionWrapper:
    def __init__(self, session_directory) -> None:
        self._session_directory = session_directory
        self._session = os.path.basename(session_directory)
        self._trial_data_wrapper = TrialDataWrapper(self)
        self._rotary_data_wrapper = RotaryDataWrapper(self)
        self._sync_data_wrapper = SyncDataWrapper(self)
        self._camera_data_wrapper = CameraDataWrapper(self)

    @property
    def trial(self):
        return self._trial_data_wrapper

    @property
    def rotary(self):
        return self._rotary_data_wrapper

    @property
    def sync_pulse(self):
        return self._sync_data_wrapper

    @property
    def camera(self):
        return self._camera_data_wrapper

    @property
    def session(self):
        return self._session

    def list_time(self):
        return os.listdir(self._session_directory)

    @property
    def start_time(self):
        # ignore .DS_Store file
        if self.list_time()[0] == '.DS_Store':
            return self.list_time()[1]
        else:
            return self.list_time()[0]

    @property
    def rotary_data(self):
        return self._rotary_data_wrapper.all

    @property
    def trial_data(self):
        return self._trial_data_wrapper.all

    @property
    def meta_data(self):
        path_meta_data = None
        for f in os.listdir(os.path.join(self._session_directory, self.start_time)):
            if f.endswith('meta-data.json'):
                path_meta_data = os.path.join(self._session_directory, self.start_time, f)
                break
            else:
                pass
        if path_meta_data is None:
            print('No meta data found for', self.session)
            return None
        else:
            with open(path_meta_data, 'r') as file:
                meta_data = json.load(file)
            return meta_data


class TrialDataWrapper:
    def __init__(self, session_wrapper) -> None:
        path_trial_data = os.path.join(session_wrapper._session_directory,
                                       session_wrapper.start_time,
                                       session_wrapper.session + '_trial_data.csv')
        self.all = None
        if os.path.isfile(path_trial_data):
            header_dict = {'detection': ["time", "trial_num", "trial_start",
                                         "trial_type", "tone_onset", "decision",
                                         "choice", "left_right", "reward_time",
                                         "inter_trial_interval"],
                           '2afc': ["time", "trial_num", "trial_start",
                                    "trial_type", "stim_strength", "tone_onset",
                                    "decision", "choice", "reward_time",
                                    "inter_trial_interval", "block"],
                           'gonogo': ["time", "trial_num", "trial_start",
                                      "trial_type", "tone_onset", "decision",
                                      "choice", "left_right", "reward_time",
                                      "inter_trial_interval"]}
            trial_header = header_dict[os.path.basename(
                os.path.dirname(
                    os.path.dirname(session_wrapper._session_directory)))]
            self.all = pd.read_csv(path_trial_data, names=trial_header)
        else:
            print('No trial data found for', session_wrapper.session)

        if self.all is not None:
            trial_num = self.all['trial_num'].unique()
            self.complete = []
            # remove 0
            trial_num = trial_num[trial_num != 0]
            for tn in trial_num:
                setattr(self, '_' + str(tn),
                        SingleTrialWrapper(self.all, tn))
                # add to complete collection
                self.complete.append(getattr(self, '_' + str(tn)))

        else:
            pass

    # decision options
    @property
    def moved_wheel(self):  # detection outcome (1/2)
        if hasattr(self, 'moved_wheel_collection'):
            return self.moved_wheel_collection
        else:
            moved_wheel_trials = self.all.loc[self.all['decision'] == 'moved_wheel', 'trial_num'].unique()
            self.moved_wheel_collection = []
            for i in moved_wheel_trials:
                self.moved_wheel_collection.append(getattr(self, '_' + str(i)))
            return self.moved_wheel_collection

    @property
    def no_response(self):  # detection outcome (2/2)
        if hasattr(self, 'no_response_collection'):
            return self.no_response_collection
        else:
            no_response_trials = self.all.loc[self.all['decision'] == 'no_response', 'trial_num'].unique()
            self.no_response_collection = []
            for i in no_response_trials:
                self.no_response_collection.append(getattr(self, '_' + str(i)))
            return self.no_response_collection

    @property
    def hit(self):  # gonogo outcome (1/4)
        if hasattr(self, 'hit_collection'):
            return self.hit_collection
        else:
            hit_trials = self.all.loc[self.all['reward_time'] == 1, 'trial_num'].unique()
            self.hit_collection = []
            for i in hit_trials:
                self.hit_collection.append(getattr(self, '_' + str(i)))
            return self.hit_collection

    @property  # gonogo outcome (2/4)
    def false_alarm(self):
        if hasattr(self, 'false_alarm_collection'):
            return self.false_alarm_collection
        else:
            self.false_alarm_collection = []
            for i in self.moved_wheel:
                if i in self.hit:
                    pass
                else:
                    self.false_alarm_collection.append(i)
            return self.false_alarm_collection

    @property  # gonogo outcome (3/4)
    def miss(self):
        if hasattr(self, 'miss_collection'):
            return self.miss_collection
        else:
            self.miss_collection = []
            for i in self.no_response:
                if i.all.choice.values[-1] == 'incorrect':
                    self.miss_collection.append(i)
            return self.miss_collection

    @property  # gonogo outcome (4/4)
    def correct_rejection(self):
        if hasattr(self, 'correct_rejection_collection'):
            return self.correct_rejection_collection
        else:
            self.correct_rejection_collection = []
            for i in self.no_response:
                if i in self.miss:
                    pass
                else:
                    self.correct_rejection_collection.append(i)
            return self.correct_rejection_collection

    @property
    def correct(self):  # 2afc outcome (1/3)
        if hasattr(self, 'correct_collection'):
            return self.correct_collection
        else:
            correct_trials = self.all.loc[self.all['choice'] == 'correct', 'trial_num'].unique()
            self.correct_collection = []
            for i in correct_trials:
                self.correct_collection.append(getattr(self, '_' + str(i)))
            return self.correct_collection

    @property
    def incorrect(self):  # 2afc outcome (2/3)
        if hasattr(self, 'incorrect_collection'):
            return self.incorrect_collection
        else:
            incorrect_trials = self.all.loc[self.all['choice'] == 'incorrect', 'trial_num'].unique()
            self.incorrect_collection = []
            for i in incorrect_trials:
                self.incorrect_collection.append(getattr(self, '_' + str(i)))
            return self.incorrect_collection

    @property
    def omission(self):  # 2afc outcome (2/3)
        if hasattr(self, 'omission_collection'):
            return self.omission_collection
        else:
            omission_trials = self.all.loc[self.all['choice'] == 'omission', 'trial_num'].unique()
            self.omission_collection = []
            for i in omission_trials:
                self.omission_collection.append(getattr(self, '_' + str(i)))
            return self.omission_collection


class TimeDataWrapper:
    def __init__(self, session_wrapper, data_type) -> None:
        path_time_data = os.path.join(session_wrapper._session_directory,
                                      session_wrapper.start_time,
                                      session_wrapper.session + f'_{data_type}_data.csv')
        self.all = None
        if os.path.isfile(path_time_data):
            # read csv file as dataframe
            self.all = pd.read_csv(path_time_data, names=['timestamp', 'value'])

    def get_between(self, timestamp_0, timestamp_1):
        """
        Get rotary data between two timestamps, both start and end are inclusive.
        """
        return self.all[(self.all['timestamp'] >= timestamp_0) & (self.all['timestamp'] <= timestamp_1)]


class SyncDataWrapper(TimeDataWrapper):
    def __init__(self, session_wrapper) -> None:
        super().__init__(session_wrapper, 'sync_pulse')
        if self.all is not None:
            # self.all = self.all[self.all['value'].diff() == 1]
            self.all = self.all[self.all['value'] == 1]

class CameraDataWrapper(TimeDataWrapper):
    def __init__(self, session_wrapper) -> None:
        super().__init__(session_wrapper, 'camera_pulse')
        if self.all is not None:
            self.all = self.all[self.all['value'] == 1]

class RotaryDataWrapper(TimeDataWrapper):
    DEGREE = 360
    PPR = 1024

    def __init__(self, session_wrapper) -> None:
        super().__init__(session_wrapper, 'rotary')
        if self.all is not None:
            self.all['degree'] = self.all['value'] * self.DEGREE / self.PPR  # convert position (1024 PPR) to degree

class SingleTrialWrapper:
    def __init__(self, full_trial_df, trial_num) -> None:
        trial_boundary = np.where(full_trial_df['trial_num'] == trial_num)[0]
        trial_start = trial_boundary[0] - 1  # add one row before
        trial_end = trial_boundary[-1]  # remove one row after
        self._single_trial_df = full_trial_df.iloc[trial_start:trial_end, :].copy()
        self.trial_num = trial_num

    @property
    def trial_start(self):
        return self._single_trial_df[self._single_trial_df['trial_start'] == 1].time.values[0]

    @property
    def tone_onset(self):
        # some trials do not have tone_onset == 1 row
        return self._single_trial_df[self._single_trial_df['tone_onset'] == 1].time.values[0]

    @property
    def reward_time(self):
        return self._single_trial_df[self._single_trial_df['reward_time'] == 1].time.values[0]

    @property
    def trial_end(self):
        return self._single_trial_df['time'].values[-1]

    @property
    def all(self):
        return self._single_trial_df

    def __repr__(self) -> str:
        return "<SingleTrialObject {} at {}>".format('_' + str(self.trial_num), hex(id(self)))


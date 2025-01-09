'''
Habituation script for head-fixed mice performing auditory tasks

Aim:
    Habituate animals to setup and being head-fixed. Animals are head-fixed for increasing durations (day 1 = 15 min;
    day 2 = 30 min; day = 45 min). During head-fixation, animals are presented the 'easy' tones and X ul reward (10%
    sucrose) is provided. During habituation the wheel position is fixed.


'''

#%% import modules
import sounddevice as sd
import time
import random
from base_auditory_task import BaseAuditoryTask

#%%
class Habituation(BaseAuditoryTask):

    SECONDS = 60
    MICROLITERS = 1000

    STIM_STRENGTH = 100
    PUMP_TIME_ADJUST = 1
    def __init__(self, data_io, exp_dir, procedure, habi_params):
        super().__init__(data_io, exp_dir, procedure)
        self.task_id, habi_day, time_limit = habi_params
        sess_duration = time_limit * self.SECONDS
        self.timeout = time.time() + sess_duration
        reward_size = self.task_prefs[f'reward_size_{self.task_id}']
        trial_duration = sess_duration / round(self.MICROLITERS/reward_size)
        self.pump_time_after_audio = self.task_prefs['task_prefs']['pump_time_after_audio']
        iti_duration = trial_duration - self.pump_time_after_audio
        self.iti = [iti_duration - (iti_duration / 2), iti_duration + (iti_duration / 2)] # mean of ITI will be iti_duration

    def get_trial(self):
        if self.task_id == '2afc':
            # randomly choose either high vs. low tone trial
            if random.random() < 0.5:
                self.trial_id = 'high'
                self.tgt_octave = 2
            else:
                self.trial_id = 'low'
                self.tgt_octave = 0
        else:
            self.trial_id = 'middle'
            self.tgt_octave = 1
        return self.trial_id

    def get_log_data(self):
        return "{0},{1},{2},{3},{4},{5},{6}\n".format(time.time(), str(self.trial_num), str(self.trial_start),
                                                      str(self.trial_id), str(self.tone_played), str(self.reward_time),
                                                      str(self.curr_iti))  # todo: 0: time_stamp, 1: trial_num, 2: trial_start, 3: trial_type:, 4: tone_played, 5: tone_duration, 6: reward_given, 7: inter-trial-intervall


    def check_trial_end(self):
        if time.time() > self.timeout:  # max length reach
            mess = "time limit reached, enter 'stop' and take out animal"
            print(mess)
            self.ending_criteria = "max_time"
            self.stop = True

    def execute_task(self):
        self.trial_start = 1
        self.trial_num += 1
        self.trial_id = self.get_trial()
        self.logger.log_trial_data(self.get_log_data())
        self.trial_start = 0
        self.cloud = self.stimulus_manager.create_tone_cloud(self.tgt_octave, self.STIM_STRENGTH)

        timeout = time.time() + self.pump_time_after_audio
        with sd.OutputStream(samplerate=self.stimulus_manager.fs, blocksize=len(self.cloud), channels=2, dtype='int16',
                             latency='low', callback=self.callback):
            while True:
                if time.time() > timeout:  # omission trials: no response in response window
                    self.cancel_audio = True
                    self.reward_system.trigger_reward(self.logger, self.PUMP_TIME_ADJUST)
                    break
        self.cancel_audio = False
        self.curr_iti = random.uniform(self.iti[0], self.iti[1])
        time.sleep(self.curr_iti)  # inter-trial-interval
        self.logger.log_trial_data(self.get_log_data())
        print("\ntrial number: ", self.trial_num, end="")
        self.check_trial_end()

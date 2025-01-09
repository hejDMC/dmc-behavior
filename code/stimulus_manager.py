import random
import numpy as np
import pandas as pd
from sklearn import preprocessing

# Stimulus Manager class to manage tone clouds and stimulus-related methods
class StimulusManager:
    def __init__(self, task_prefs, droid_settings, data_io, exp_dir):
        self.task_prefs = task_prefs
        self.droid_settings = droid_settings
        self.fs = droid_settings['base_params']['tone_sampling_rate']
        self.tone_fs = task_prefs['task_prefs']['tone_fs']
        self.tone_duration = self.task_prefs['task_prefs']['tone_duration']
        self.tone_amplitude = self.task_prefs['task_prefs']['tone_amplitude']
        self.scaler = preprocessing.MinMaxScaler(feature_range=(task_prefs['task_prefs']['cloud_range'][0],
                                                                task_prefs['task_prefs']['cloud_range'][1]))
        self.tones_arr = self.generate_tones()
        self.cloud_duration = self.task_prefs['task_prefs']['cloud_duration']
        self.num_tones = int(self.cloud_duration * 100 - (self.tone_duration - 1 / self.tone_fs) * 100)
        self.tone_cloud_fn = exp_dir.joinpath(f'{data_io.path_manager.get_today()}_tone_cloud_data.csv')
        # todo option for tones vs tone clouds

    def pitch_to_frequency(self, pitch):
        """
        Convert pitch to frequency
        :param pitch: int
        :return: frequency: float
        """
        middle_frequency = 261.625565  # middle C == C5
        frequency = 2 ** (int(pitch) / 12) * middle_frequency
        return frequency

    def weighted_octave_choice(self, tgt_octave, stim_strength):
        """
        Function to select tones for tone clouds from tgt_octave depending on stim strength
        :param tgt_octave: int
        :param stim_strength: int
        :return: oct_id: int
        """
        # stim_strength is the prob. for tone on tgt_octave, (100-stim_strength) is prob. for non tgt stimuli, so divided by two as there are two 'off-target octaves"

        weight_matrix = [0, 0, 0]  # initialize the weight matrix
        for i, w in enumerate(weight_matrix):
            if i == tgt_octave:
                weight_matrix[i] = stim_strength  # weighted prob. for tgt_octave is stim_strength
            else:
                weight_matrix[i] = int((100 - stim_strength) / 2)  # inverse/2 for other two octaves
        oct_id = random.choices(population=[0, 1, 2], weights=weight_matrix)  # draw oct. for current tone
        return oct_id[0]

    def create_tone(self, fs, frequency, tone_duration, amplitude):
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

    def generate_tones(self):
        # Create the tone clouds for different octaves
        low_octave = np.linspace(self.task_prefs['task_prefs']['low_octave'][0],
                                 self.task_prefs['task_prefs']['low_octave'][1],
                                 self.task_prefs['task_prefs']['low_octave'][2])
        middle_octave = np.linspace(self.task_prefs['task_prefs']['middle_octave'][0],
                                    self.task_prefs['task_prefs']['middle_octave'][1],
                                    self.task_prefs['task_prefs']['middle_octave'][2])
        high_octave = np.linspace(self.task_prefs['task_prefs']['high_octave'][0],
                                  self.task_prefs['task_prefs']['high_octave'][1],
                                  self.task_prefs['task_prefs']['high_octave'][2])
        return np.vstack([low_octave, middle_octave, high_octave])

    def create_tone_cloud(self, tgt_octave, stim_strength):
        # Generate a tone cloud from target octave and stimulation strength
        print("in func")
        tone_sequence_idx = [random.choice(range(np.shape(self.tones_arr[1])[0])) for _ in
                             range(self.num_tones)]
        print("pre weighted octave")
        tone_sequence = np.array(
            [self.tones_arr[self.weighted_octave_choice(tgt_octave, stim_strength)][idx] for idx in tone_sequence_idx])
        print("pre weighted octave")
        tone_sequence = [self.pitch_to_frequency(pitch) for pitch in tone_sequence]
        tone_cloud_duration = self.fs * self.cloud_duration
        tone_cloud = np.zeros([int(tone_cloud_duration), len(tone_sequence)])
        k = 0
        pd.DataFrame(tone_sequence).T.to_csv(self.tone_cloud_fn, index=False, header=False, mode='a')
        for i, tone in enumerate(tone_sequence):
            tone_cloud[k:k + int(self.fs * self.tone_duration), i] = self.create_tone(self.fs, tone, self.tone_duration,
                                                                                      self.tone_amplitude)
            k += int(tone_cloud_duration / (((self.tone_duration - 1 /
                                              self.tone_fs) * 100) + len(tone_sequence)))
        tone_cloud = tone_cloud.sum(axis=1) // len(tone_sequence)
        tone_cloud = tone_cloud.reshape(-1, 1)
        return self.scaler.fit_transform(tone_cloud).astype(np.int16)

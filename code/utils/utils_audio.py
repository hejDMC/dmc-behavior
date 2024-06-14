import random
import numpy as np

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
"""
Auditory two-alternative forced choice task with tone clouds

Aim:
    Animals are trained to perform an auditory two-alternative forced choice task
     by presenting either a high or a low tone clouds, the animals are then asked to move the wheel in the
     correct direction

    In correct trials, a water reward is given (depending on overall performance between 3ul - 1.5 ul)
    In incorrect trials, a white noise is played
    In ommision trials, a white noise is played

    Tones clouds are either comprised of either high, low or intermediate tones.
    Depending of task stage, the difficulties differ. On easy trials the tones clouds are comprised to 100 % of tones
    from the target frequency range (either high or low), increasing difficulties sample more tones of the two
    non-target octaves (ratios are 85/15, 70/30 and 60/40).

    From Coen et al., 2021: the turning threshold for a decision was 30 degrees in wheel turning.

"""

import random
import time

import numpy as np
import sounddevice as sd
from tasks.auditory_2afc_helpers import BiasCorrectionHandler, StageChecker
from tasks.base_auditory_task import BaseAuditoryTask


# %%
class Auditory2AFC(BaseAuditoryTask):
    DECISION_SD = 0.5
    MIN_TRIAL_DEBIAS = 10

    TIME_LIMIT = 90
    TIME_LIMIT_LOW_TRIALS = 45
    LOW_TRIAL_NUM = 350
    SECONDS = 60

    MIN_CORRECT_HISTORY = 3
    DEBIASING_STAGE_THRESHOLD = 4

    NO_BIAS_PROB = 0.5
    HIGH_PROB_STAGE_5_BLOCK_NEG = 0.2
    HIGH_PROB_STAGE_5_BLOCK_POS = 0.8
    NO_BIAS_TRIALS_STAGE_5 = 90

    def __init__(self, data_io, exp_dir, procedure):
        super().__init__(data_io, exp_dir, procedure)

        start_time = time.time()
        self.time_out = start_time + self.TIME_LIMIT * self.SECONDS
        self.time_out_low_trials = (
            start_time + self.TIME_LIMIT_LOW_TRIALS * self.SECONDS
        )

        self.response_matrix, self.pre_reversal = data_io.load_response_matrix()
        self.turning_goal = self.task_prefs["encoder_specs"]["target_degrees"]

        self.bc_handler = BiasCorrectionHandler(
            self.data_io, self.first_day, self.stage
        )
        self.bias_correction = self.bc_handler.get_bias_correction()
        self.bias_counter = 0  # bias counter to avoid that animals develop a bias to higher rewarded side
        self.bias_counter_max = self.task_prefs["task_prefs"]["bias_counter_max"]

        self.curr_stim_strength = False  # to be decided eacht trial

        self.correct_hist = (
            []
        )  # history of correct trials for block structure in stage 0
        self.last_trial = 0
        self.decision_history = (
            []
        )  # list of choices 1 for right, -1 for left, 0 for undecided, average of 0 indicates no bias
        self.reaction_times = []

        self.block = 0  # only in stage 5
        self.block_length = 0
        self.block_counter = 0

    def get_trial(self):
        """
        Determine the trial type (high or low tone) based on the current stage and trial number.
        Returns:
            str: The trial ID ('high' or 'low').
        """

        if self.stage < 5:
            self.trial_id = "high" if random.random() < self.NO_BIAS_PROB else "low"

        elif self.stage == 5:
            if self.trial_num <= self.NO_BIAS_TRIALS_STAGE_5:
                if self.trial_num == self.NO_BIAS_TRIALS_STAGE_5:
                    self.get_block()  # Set up the block after first 90 trials
                self.trial_id = "high" if random.random() < self.NO_BIAS_PROB else "low"
            else:
                high_prob = (
                    self.HIGH_PROB_STAGE_5_BLOCK_NEG
                    if self.block == -1
                    else self.HIGH_PROB_STAGE_5_BLOCK_POS
                )
                self.trial_id = "high" if random.random() < high_prob else "low"

                self.block_counter += 1
                print(f"Block counter: {self.block_counter}")
                if self.block_counter >= self.block_length:
                    self.get_block()  # change block when block length is reached

        else:
            raise ValueError(
                f"Unexpected stage value: {self.stage}. Only stages 0-5 are implemented."
            )

        return self.trial_id

    def get_trial_id(self):
        """
        Determine the trial ID based on the current stage, correct history, and trial outcomes.
        Returns:
            str: The trial ID ('high' or 'low').
        """

        if self.stage == 0:
            if len(self.correct_hist) < self.MIN_CORRECT_HISTORY:
                self.trial_id = self.last_trial
            else:
                corr_sum = np.sum(self.correct_hist[-self.MIN_CORRECT_HISTORY :])
                if (
                    corr_sum == self.MIN_CORRECT_HISTORY
                ):  # If the last three trials were all correct, switch trial
                    self.correct_hist = []  # Reset history
                    self.trial_id = "low" if self.last_trial == "high" else "high"
                else:
                    self.trial_id = self.last_trial

        elif 0 < self.stage < self.DEBIASING_STAGE_THRESHOLD:
            if self.choice == "incorrect" and self.trial_num > self.MIN_TRIAL_DEBIAS:
                self.trial_id = self.debias()
                print("call debias")
            else:
                self.trial_id = self.get_trial()

        else:
            self.trial_id = self.get_trial()

        return self.trial_id

    def debias(self):
        # should only be calculated after incorrect trials
        # function for debiasing --> calculate the mean response over the last 10 trials, if animal only goes in one direction, present tones only on other side
        # open trial data file and read the last 10 trials and calculate the average
        hist_list = self.decision_history[-self.MIN_TRIAL_DEBIAS :]
        hist_mean = np.mean(hist_list)
        debias_val = random.gauss(hist_mean, self.DECISION_SD)
        bias_side = "right" if debias_val > 0 else "left"
        tone = list(self.response_matrix.keys())[
            list(self.response_matrix.values()).index(bias_side)
        ]
        self.trial_id = "low" if tone == "high" else "high"

        return self.trial_id

    def calculate_decision(self):  #  , wheel_position, turning_goal):

        # continously stream the wheel_position --> if it crosses threshold (30 degree) mark choice as left/right; otherwise it's "undecided"
        # right turns are positive and left turns are negative --> depends on how you wire the encoder
        current_position = self.encoder_data.getValue()
        # self.rotary_logger(self.current_position)
        wheel_position = current_position - self.wheel_start_position
        if wheel_position > self.turning_goal:
            self.decision_var = "right"
        elif wheel_position < -self.turning_goal:
            self.decision_var = "left"
        else:
            self.decision_var = "undecided"
        time.sleep(0.001)  # 1 ms sleep, otherwise some threading issue occur
        return self.decision_var

    def choice_evaluation(self):  # , trial_id):

        self.decision_var = self.calculate_decision()
        if self.decision_var == "undecided":
            self.choice = "undecided"
            # pass
        elif self.decision_var == self.target_position:
            self.choice = "correct"
        else:
            self.choice = "incorrect"
        return self.decision_var, self.choice

    def check_trial_end(self):
        if time.time() > self.time_out:  # max length reach
            mess = (
                "90 min passed -- time limit reached, enter 'stop' and take out animal"
            )
            print(mess)
            self.ending_criteria = "max_time"
            self.stop = True
        elif (
            time.time() > self.time_out_low_trials
            and self.trial_num < self.LOW_TRIAL_NUM
        ):  # low trial number in first 45 min
            mess = "low number of trials, enter 'stop' and take out animal"
            print(mess)
            self.ending_criteria = "low_trial_num"

            self.stop = True
        # check disengagement
        if (
            time.time() > self.time_out_low_trials
            and self.trial_num > self.LOW_TRIAL_NUM
        ):
            self.disengage = self.check_disengage(self.reaction_times)
            if self.disengage:  # disengagement after > 45 min
                mess = "animal is disengaged, please enter 'stop' and take out animal"
                print(mess)
                self.ending_criteria = "disengagement"
                self.stop = True

    def check_stage(self):
        self.stage_checker = StageChecker(
            self.data_io,
            self.stage,
            self.trial_stat,
            self.trial_num,
            self.decision_history,
            self.correct_hist,
            self.animal_dir,
        )
        self.stage_advance = self.stage_checker.check_stage()

    def adjust_pump_duration(self):
        if (
            self.decision_var == self.bias_correction
            and self.bias_counter <= self.bias_counter_max
        ):  # if the animal choose anti-bias side, give more reward
            pump_time_adjust = 2
            self.bias_counter += 1  # only reward first x trials with higher volume
        else:
            pump_time_adjust = 1
        return pump_time_adjust

    def get_block(self):

        if self.block == 0:  # first block to be decided
            self.block = random.choice([-1, 1])
            self.block_length = random.randrange(30, 70)
            self.block_counter = 0
        else:
            if self.block == -1:
                self.block = 1
            else:
                self.block = -1
            self.block_length = random.randrange(30, 70)
            self.block_counter = 0
            print(self.block_length)

    def get_log_data(self):
        return "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10}\n".format(
            time.time(),
            str(self.trial_num),
            str(self.trial_start),
            str(self.trial_id),
            str(self.curr_stim_strength),
            str(self.tone_played),
            str(self.decision_var),
            str(self.choice),
            str(self.reward_time),
            str(self.curr_iti),
            str(self.block),
        )  # todo: 0: time_stamp, 1: trial_num, 2: trial_start, 3: trial_type:, 4: tone_played, 5: decision_variable, 6: choice_variable, 7: reward_time, 8: inter-trial-intervall, 10: block

    def execute_task(self):
        self.trial_start = 1
        self.logger.log_trial_data(self.get_log_data())
        self.trial_start = 0
        if (
            self.trial_num == 0
        ):  # for first trial of session, randomly choose "last" trial, only for init of task
            self.last_trial = self.get_trial()

        self.trial_id = (
            self.get_trial_id()
        )  # I put this hear as computing the cloud takes some 250 ms
        self.cloud_bool = False

        while True:
            self.animal_quiet, self.cloud = (
                self.check_quiet_window()
            )  # call the QW checker function, stay in function as long animal holds wheel still, otherwise return and call function again
            if (
                self.animal_quiet
            ):  # if animal is quiet for quiet window length, ini new trial, otherwise stay in loop
                trial_start = time.time()
                self.animal_quiet = False
                break

        self.target_position = self.response_matrix[self.trial_id]
        timeout = (
            time.time() + self.response_window
        )  # start a timer at the size of the response window
        self.trial_num += 1

        with sd.OutputStream(
            samplerate=self.stimulus_manager.fs,
            blocksize=len(self.cloud),
            channels=2,
            dtype="int16",
            latency="low",
            callback=self.callback,
        ):
            time.sleep(
                self.stimulus_manager.cloud_duration * 2
            )  # to avoid zero shot trials, stream buffers 2x the cloud duration before tone onset
            self.tone_played = 1
            self.logger.log_trial_data(self.get_log_data())
            self.tone_played = 0
            self.wheel_start_position = self.encoder_data.getValue()
            while True:
                self.decision_var, self.choice = self.choice_evaluation()
                if self.choice == "correct":  # if choice was correct
                    self.cancel_audio = True
                    self.trial_stat[0] += 1
                    self.logger.log_trial_data(self.get_log_data())
                    self.reaction_times.append(time.time() - trial_start)
                    self.reward_time = 1
                    pump_time_adjust = self.adjust_pump_duration()
                    self.logger.log_trial_data(self.get_log_data())
                    self.reward_system.trigger_reward(self.logger, pump_time_adjust)
                    self.reward_time = 0
                    if self.target_position == "right":
                        self.decision_history.append(1)
                    else:
                        self.decision_history.append(-1)
                    self.correct_hist.append(1)
                    break
                elif self.choice == "incorrect":  # if choice was incorrect
                    self.cancel_audio = True
                    self.trial_stat[1] += 1
                    self.logger.log_trial_data(self.get_log_data())
                    self.reaction_times.append(time.time() - trial_start)
                    if self.target_position == "right":
                        self.decision_history.append(-1)
                    else:
                        self.decision_history.append(1)
                    self.correct_hist.append(0)
                    break
                elif (
                    time.time() > timeout
                ):  # omission trials: no response in response window
                    self.cancel_audio = True
                    self.trial_stat[2] += 1
                    self.logger.log_trial_data(self.get_log_data())
                    self.reaction_times.append(time.time() - trial_start)
                    self.decision_history.append(0)
                    self.correct_hist.append(0)
                    break
        if self.choice == "correct":
            self.curr_iti = self.iti[0]
        elif self.choice == "incorrect":
            self.play_tone(
                self.punish_sound, self.punish_duration, self.punish_amplitude
            )
            self.curr_iti = (
                self.iti[1] * 2
            )  # if incorrect, add 3 sec punishment timeout
        else:
            self.play_tone(
                self.punish_sound, self.punish_duration, self.punish_amplitude
            )
            self.curr_iti = self.iti[1]  # if omission, add 1.5 sec punishment timeout

        self.last_trial = self.trial_id  # only for stage 0
        self.cancel_audio = False
        time.sleep(self.curr_iti)  # inter-trial-interval
        self.logger.log_trial_data(self.get_log_data())
        print(f"trial number: {self.trial_num} - correct trials: {self.trial_stat[0]}")
        self.check_trial_end()

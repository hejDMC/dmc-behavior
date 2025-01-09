import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from managers.utils.psychofit import (
    erf_psycho,
    erf_psycho_2gammas,
    mle_fit_psycho,
    weibull,
    weibull50,
)


class StageChecker:
    STAGE_0_CRITERIA = 300  # Criteria for advancing from stage 0 to stage 1
    STAGE_1_CRITERIA = 0.8  # Minimum accuracy to advance from stage 1
    STAGE_2_CRITERIA = 0.75  # Minimum accuracy to advance from stage 2
    STAGE_3_CRITERIA = 350  # Minimum number of trials to advance from stage 3
    STIM_LIST = [0, 15, 30, 40, 60, 70, 85, 100]
    TASK_TYPE = "2afc"
    P_MODEL = "erf_psycho_2gammas"
    # DISPATCHER = {
    #     'weibull': weibull,
    #     'weibull50': weibull50,
    #     'erf_psycho': erf_psycho,
    #     'erf_psycho_2gammas': erf_psycho_2gammas
    # }
    N_FITS = 10
    LATE_STAGE_NTRIALS = 300
    LATE_STAGE_LAPSE = [0.2, 0.8]
    LATE_STAGE_COUNT = 3
    STAGE_4_BIAS_CENTER = 50
    STAGE_4_BIAS_CRITERIUM = 16
    SLOPE_CRITERIUM = 19
    GAMMA_CRITERIUM = 0.2
    STAGE_5_BIAS_CRITERIUM = 5

    def __init__(
        self,
        data_io,
        stage,
        trial_stat,
        trial_num,
        decision_history,
        correct_hist,
        animal_dir: Path,
    ):
        """
        Initialize the StageChecker with relevant attributes.

        Parameters:
            stage (int): Current stage of the training.
            trial_stat (list): Trial statistics, e.g., correct trials count.
            trial_num (int): Total number of trials performed.
            decision_history (list): History of decisions made (e.g., -1 for left, 1 for right).
            correct_hist (list): History of correctness for each trial (e.g., 0 for incorrect, 1 for correct).
            animal_dir (str): Directory path for the animal data.
        """
        self.stage = stage
        self.trial_stat = trial_stat
        self.trial_num = trial_num
        self.decision_history = decision_history
        self.correct_hist = correct_hist
        self.animal_dir = animal_dir
        self.stage_advance = False
        self.data_io = data_io
        self.response_matrix = self.data_io.load_response_matrix()

    def check_stage(self):
        """Main function to check if the animal advances to the next stage."""
        if self.stage == 0:
            return self._check_advance_stage_0()
        elif self.stage == 1:
            return self._check_advance_stage_1()
        elif self.stage == 2:
            return self._check_advance_stage_2()
        elif self.stage == 3:
            return self._check_advance_stage_3()
        elif self.stage == 4:
            return self._check_advance_stage_4()
        elif self.stage == 5:
            return self._check_advance_stage_5()

    def _check_advance_stage_0(self):
        """Criteria to advance from stage 0 to stage 1: More than STAGE_0_CRITERIA correct trials."""
        if self.trial_stat[0] > self.STAGE_0_CRITERIA:
            self.stage_advance = True
            self._print_stage_complete(self.stage)
        return self.stage_advance

    def _check_advance_stage_1(self):
        """Criteria to advance from stage 1 to stage 2: 80% correct on both left and right sides."""
        right_trials, left_trials = self._get_trial_sides()
        if (
            np.mean(right_trials) >= self.STAGE_1_CRITERIA
            and np.mean(left_trials) >= self.STAGE_1_CRITERIA
        ):
            self.stage_advance = True
            self._print_stage_complete(self.stage)
        return self.stage_advance

    def _check_advance_stage_2(self):
        """Criteria to advance from stage 2 to stage 3: 75% correct on both left and right sides."""
        right_trials, left_trials = self._get_trial_sides()
        if (
            np.mean(right_trials) >= self.STAGE_2_CRITERIA
            and np.mean(left_trials) >= self.STAGE_2_CRITERIA
        ):
            self.stage_advance = True
            self._print_stage_complete(self.stage)
        return self.stage_advance

    def _check_advance_stage_3(self):
        """Criteria to advance from stage 3 to stage 4: More than STAGE_3_CRITERIA trials completed."""
        if self.trial_num > self.STAGE_3_CRITERIA:
            self.stage_advance = True
            self._print_stage_complete(self.stage)
        return self.stage_advance

    def _check_advance_stage_4(self) -> bool:
        """Criteria to advance from stage 4 to stage 5: Custom logic for stage 4."""
        return self._check_stage_4_advance()

    def _check_advance_stage_5(self):
        """Criteria for determining readiness for experimentation at stage 5."""
        return self._check_ready_for_experiment()

    def _get_trial_sides(self):
        """Helper function to get right and left trials based on decision history."""
        right_trials = [
            c for d, c in zip(self.decision_history, self.correct_hist) if d == 1
        ]
        left_trials = [
            c for d, c in zip(self.decision_history, self.correct_hist) if d == -1
        ]
        return right_trials, left_trials

    def _print_stage_complete(self, stage):
        """Print a message indicating that the stage is complete."""
        print(f">>>>>  FINISHED STAGE {stage} !!! <<<<<<<<<")

    def _check_stage_4_advance(self):
        """
        stage checker to advance to stage 5 (biased block design)
            - last three sessions > 400 trials, respectively
            - > 90 % on *both* 100 % trials, respectively
            - fit of joint psychometric curve with pars[0] < 5, pars[1] < 20 (??), pars[2]/[3] < 0.1
        """

        # get list of last three experiments
        exp_list = sorted(self.animal_dir.iterdir())[-4:-1]
        cnt = 0
        cnt_stage = 0
        trial_data = pd.DataFrame()
        for exp in exp_list:
            exp_path = sorted(exp.iterdir())[
                -1
            ]  # there should be only one time point in the folder
            meta_file = [m for m in exp_path.glob("*_meta-data.json")][0]
            with open(meta_file) as fn:
                meta_data = json.load(fn)
            if (
                meta_data["curr_stage"] == 4
            ):  # needs to be on stage 4 for at least 3 sessions
                cnt_stage += 1
            n_trials = meta_data["# trials"]

            trial_times = self._load_trial_data(exp_path)
            prob_right, num_trials = self._get_performance_per_stim(trial_times)
            if (
                n_trials > self.LATE_STAGE_NTRIALS
                and prob_right[0] < self.LATE_STAGE_LAPSE[0]
                and prob_right[-1] > self.LATE_STAGE_LAPSE[1]
            ):
                # if more than 300 trials and more than 80 % correct on both easy trials, add to counter
                cnt += 1
                trial_data = pd.concat((trial_data, trial_times))
        if cnt == self.LATE_STAGE_COUNT and cnt_stage == self.LATE_STAGE_COUNT:
            print("trial number and easy trial performance good")
            trial_data = trial_data.reset_index(drop=True)
            prob_right, num_trials = self._get_performance_per_stim(trial_data)
            pars, L = mle_fit_psycho(
                np.vstack(
                    [
                        np.array(self.STIM_LIST),
                        np.array(num_trials),
                        np.array(prob_right),
                    ]
                ),  # 'erf_psycho_2gammas',
                P_model=self.P_MODEL,  # weibull # Gauss error function
                nfits=self.N_FITS,
            )

            (bias, slope, gamma1, gamma2) = pars
            if (
                abs(bias - self.STAGE_4_BIAS_CENTER) < self.STAGE_4_BIAS_CRITERIUM
                and slope < self.SLOPE_CRITERIUM
                and gamma1 < self.GAMMA_CRITERIUM
                and gamma2 < self.GAMMA_CRITERIUM
            ):
                self.stage_advance = True
                print(">>>>>  FINISHED STAGE 4 -- FINAL STAGE REACHED !!! <<<<<<<<<")
            else:
                self.stage_advance = False
        return self.stage_advance

    def _check_ready_for_experiment(self, animal_dir):
        """
        stage checker to advance to "ready for experiment status"
            - last three sessions > 400 trials
            - > 90 % on *all* 100 % trials (irrespective of blocks)
            - fit of joint psychometric curve with for both blocks: pars[2]/[3] < 0.1
            - bias shift: pars[0] diff between blocks > 5 ???
        """

        # get list of last three experiments
        exp_list = sorted(animal_dir.iterdir())[-4:-1]
        cnt_t_num = 0
        cnt_perf = 0
        cnt_stage = 0
        trial_data = pd.DataFrame()
        right_trials = []
        for exp in exp_list:
            exp_path = sorted(exp.iterdir())[
                -1
            ]  # there should be only one time point in the folder
            meta_file = [m for m in exp_path.glob("*_meta-data.json")][0]
            with open(meta_file) as fn:
                meta_data = json.load(fn)
            if (
                meta_data["curr_stage"] == 5
            ):  # needs to be on stage 4 for at least 3 sessions
                cnt_stage += 1
            n_trials = meta_data["# trials"]

            trial_times = self._load_trial_data(exp_path)
            if n_trials > self.LATE_STAGE_NTRIALS:
                # if more than 400 trials and more than 90 % correct on both easy trials, add to counter
                cnt_t_num += 1
                trial_data = pd.concat((trial_data, trial_times))
            for block in [-1, 1]:
                prob_right, num_trials = self._get_performance_per_stim(
                    trial_times, block=block
                )
                if (
                    prob_right[0] < self.LATE_STAGE_LAPSE[0]
                    and prob_right[-1] > self.LATE_STAGE_LAPSE[1]
                ):
                    cnt_perf += 0.5
        if (
            cnt_t_num == self.LATE_STAGE_COUNT
            and cnt_perf == self.LATE_STAGE_COUNT
            and cnt_stage == self.LATE_STAGE_COUNT
        ):
            print("trial number and easy trial performance good")
            trial_data = trial_data.reset_index(drop=True)
            bias_stats = {
                "bias_low": 0,
                "gamma1_low": 100,
                "gamma2_low": 100,
                "bias_high": 0,
                "gamma1_high": 100,
                "gamma2_high": 100,
            }
            for block in [-1, 1]:
                prob_right, num_trials = self._get_performance_per_stim(
                    trial_data, block=block
                )
                pars, L = mle_fit_psycho(
                    np.vstack(
                        [
                            np.array(self.STIM_LIST),
                            np.array(num_trials),
                            np.array(prob_right),
                        ]
                    ),
                    # 'erf_psycho_2gammas',
                    P_model=self.P_MODEL,  # weibull # Gauss error function
                    nfits=self.N_FITS,
                )
                if block == -1:
                    bias_stats["bias_low"] = pars[0]
                    bias_stats["gamma1_low"] = pars[2]
                    bias_stats["gamma2_low"] = pars[3]
                    # bias_low = dispatcher[p_model](pars, np.arange(0, 100, 1))
                else:
                    bias_stats["bias_high"] = pars[0]
                    bias_stats["gamma1_high"] = pars[2]
                    bias_stats["gamma2_high"] = pars[3]
                    # bias_high = dispatcher[p_model](pars, np.arange(0, 100, 1))
            if right_trials == "low":
                # right vs left block
                bias_shift = bias_stats["bias_low"] - bias_stats["bias_high"]
                # bias_shift = [a - b for a, b in zip(bias_low, bias_high)]
            else:
                bias_shift = bias_stats["bias_high"] - bias_stats["bias_low"]
                # bias_shift = [a - b for a, b in zip(bias_high, bias_low)]
            # if bias_shift[49] > 0.10:
            if (
                bias_shift > self.STAGE_5_BIAS_CRITERIUM
                and (
                    bias_stats["gamma1_low"]
                    and bias_stats["gamma2_low"]
                    and bias_stats["gamma1_high"]
                    and bias_stats["gamma2_high"]
                )
                < self.GAMMA_CRITERIUM
            ):
                print("bias statistic good!")
                print(" >>>   ANIMAL READY FOR EXPERIMENT <<<<  ")
        return self.stage_advance

    def _load_trial_data(self, exp_dir, return_start_time=False):
        exp = exp_dir.parts[-2]
        trial_data_file = exp_dir.joinpath(exp + "_trial_data.csv")
        trial_data_header = self.data_io.load_trial_header()
        trial_data = pd.read_csv(trial_data_file, names=trial_data_header)

        start_time = trial_data["time"][0]
        trial_data["time"] = trial_data["time"] - start_time
        trial_times = self._create_trial_file(trial_data, trial_data_header)
        if return_start_time:
            return trial_times, start_time
        else:
            return trial_times

    def _create_trial_file(self, trial_data, trial_data_header):

        trial_times = (
            trial_data[trial_data["trial_start"] == 1][trial_data_header[0:3]]
            .reset_index()
            .copy()
        )  # get first columsn for trial start times etc
        # get other columns for statistics of that trial columns, not ITT for interval after trial (other columsn are input t+4 for start_idx
        idx = trial_data.index[
            trial_data["trial_start"] == 1
        ].tolist()  # get indices of trial starts
        idx = idx[1:]  # delete the first value -> info for trial one is in idx=4
        idx.append(len(trial_data))  # add last entry from file
        idx = [i - 1 for i in idx]  # substract one to get to matching idx
        dummy_df = (
            trial_data.iloc[idx][trial_data_header[3:]].reset_index(drop=True).copy()
        )
        trial_times = pd.concat([trial_times, dummy_df], axis=1)
        if self.TASK_TYPE == "2afc":
            right_trials = self._get_right_trials()
            trial_times["stim_strength"] = [
                int(stim) for stim in trial_times["stim_strength"]
            ]  # convert to integers from string
            trial_times.loc[
                trial_times["trial_type"] != right_trials, "stim_strength"
            ] = trial_times.loc[
                trial_times["trial_type"] != right_trials, "stim_strength"
            ].apply(
                lambda x: 100 - x
            )
        # get time of trial start
        trial_times["tone_onset"] = (
            trial_data[trial_data["tone_onset"] == 1]["time"]
            .reset_index(drop=True)
            .copy()
        )
        # get time of reward delivery
        time_reward = []
        for i in [id - 1 for id in idx]:  # -1 to get correct reward indices?
            if (
                trial_data["choice"][i] == "incorrect"
                or trial_data["decision"][i] == "no_response"
            ):
                time_reward.append(0)
            else:
                time_reward.append(trial_data["time"][i])
        if trial_data["reward_time"].iloc[-2] == 0:
            time_reward.append(0)
        else:
            time_reward.append(trial_data["time"].iloc[-2])
        trial_times["reward_time"] = pd.DataFrame(time_reward)
        decision_idx = trial_data[trial_data["tone_onset"] == 1].index + 1
        trial_times["decision_time"] = (
            trial_data["time"][decision_idx].reset_index(drop=True).copy()
        )

        return trial_times

    def _get_right_trials(self, c_rm=False):
        curr_rm = self.response_matrix["pre_reversal"]
        right_trials = list(curr_rm.keys())[list(curr_rm.values()).index("right")]
        if c_rm:
            return right_trials, curr_rm
        else:
            return right_trials

    def _get_performance_per_stim(self, trial_times, block=0):
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
        for stim in self.STIM_LIST:
            temp_trial_times = trial_times[trial_times["block"] == block].copy()
            stim_perf = temp_trial_times[temp_trial_times["stim_strength"] == stim][
                "decision"
            ].value_counts()
            if stim_perf.empty:  # no values as stim not in training stage
                prob_right.append(math.nan)
            else:
                try:
                    prob_right.append(
                        stim_perf["right"] / (stim_perf["right"] + stim_perf["left"])
                    )
                    num_trials.append(stim_perf["right"] + stim_perf["left"])
                except KeyError:
                    for s in stim_perf.keys():
                        if s == "left":
                            prob_right.append(0.0)
                            num_trials.append(stim_perf["left"])
                        elif s == "right":
                            prob_right.append(1.0)
                            num_trials.append(stim_perf["right"])

        return prob_right, num_trials


class BiasCorrectionHandler:
    LEFT_THRESHOLD = 0.85
    RIGHT_THRESHOLD = 0.15
    DEFAULT_BIAS = 0.5
    TASK_TYPE = "2afc"

    def __init__(self, data_io, first_day: bool, stage: int):
        """
        Initialize the BiasCorrectionHandler with the required parameters.

        Parameters:
            animal_dir (Path): Path to the animal's data directory.
            first_day (bool): Flag indicating if it is the first day of training.
        """
        self.animal_dir = data_io.animal_dir
        self.first_day = first_day
        self.bias_correction = False
        self.stage = stage

    def get_bias_correction(self) -> str:
        """
        Determine if bias correction is needed for an animal based on the previous session's data.

        Returns:
            str: Direction for bias correction ('left', 'right', or False).
        """
        if self.first_day:
            return self._handle_first_day()

        if self.stage <= 1:
            return self._handle_stage1()

        last_exp_id = self._get_last_experiment_directory()
        if not last_exp_id:
            return self._handle_no_data()

        trial_data = self._load_trial_data(last_exp_id)
        if trial_data is None:
            return self._handle_no_data()

        self.bias_correction = self._calculate_bias(trial_data)
        print(f"bias correction: {self.bias_correction}")
        return self.bias_correction

    def _get_last_experiment_directory(self) -> Path:
        """Get the directory of the last experiment for the animal."""
        try:
            last_exp_day = sorted(
                [day for day in self.animal_dir.iterdir() if day.is_dir()]
            )[-1]
            last_exp_id = sorted(
                [exp_id for exp_id in last_exp_day.iterdir() if exp_id.is_dir()]
            )[-1]
            return last_exp_id
        except IndexError:
            return None

    def _load_trial_data(self, last_exp_id: Path) -> pd.DataFrame:
        """Load trial data from the last experimental session."""
        try:
            trial_data_file = next(last_exp_id.glob("*_trial_data.csv"))
            trial_data_header = self.data_io.load_trial_header()
            trial_data = pd.read_csv(trial_data_file, names=trial_data_header)
            return trial_data[trial_data["trial_start"] == 1].reset_index()
        except (IndexError, StopIteration, FileNotFoundError):
            return None

    def _calculate_bias(self, trial_data: pd.DataFrame) -> str:
        """Calculate if there is a bias in the animal's choices."""
        left_choices = trial_data["decision"].value_counts().get("left", 0)
        right_choices = trial_data["decision"].value_counts().get("right", 0)
        total_choices = left_choices + right_choices
        prop_left_choices = (
            left_choices / total_choices if total_choices > 0 else self.DEFAULT_BIAS
        )

        if prop_left_choices > self.LEFT_THRESHOLD:
            return "right"
        elif prop_left_choices < self.RIGHT_THRESHOLD:
            return "left"
        return False

    def _handle_first_day(self) -> bool:
        """Handle the case for the first day of training."""
        print("bias correction: False")
        return False

    def _handle_no_data(self) -> bool:
        """Handle the case where no data is available."""
        print("No previous trial data found, no bias_correction")
        print("bias correction: False")
        return False

    def _handle_stage1(self) -> bool:
        return False

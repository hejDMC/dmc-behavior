import time

# Logger class for logging experimental data
class Logger:
    def __init__(self, animal_dir, exp_dir):
        self.animal_dir = animal_dir
        self.exp_dir = exp_dir
        self.trial_data_fn = exp_dir.joinpath(f'{get_today()}_trial_data.csv')
        self.pump_log = exp_dir.joinpath(f'{get_today()}_pump_data.csv')

    def log_trial_data(self, trial_info):
        with open(self.trial_data_fn, "a") as log:
            log.write(trial_info + "\n")

    def log_pump_data(self, pump_duration):
        with open(self.pump_log, "a") as log:
            log.write(f"{time.time()},{pump_duration}\n")
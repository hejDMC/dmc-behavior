import socket
import sys
from datetime import datetime
from pathlib import Path

from tasks.habituation_auditory_tasks import Habituation
from tasks.managers.data_io import DataIO
from tasks.managers.path_manager import PathManager
from tasks.managers.utils.utils import get_habi_task, habi_time_limit

task, exp_dir = None, None
droid = socket.gethostname()
task_type = "habituation_auditory_tasks"

animal_id = input("enter the mouse ID:")

experimenter = input("who is running the experiment?")

path_manager = PathManager((Path(__file__).parent / "..").resolve(), animal_id)
data_io = DataIO(path_manager, task_type)

habi_params = [get_habi_task(), *habi_time_limit()]  # task_id, habi_day, time_limit

hour_format = "%H:%M:%S"
start_time = datetime.now().strftime(hour_format)

while True:
    command = input("Enter 'start' to begin:")
    if command == "start":
        if not exp_dir:
            animal_dir = path_manager.check_dir()
            exp_dir = path_manager.make_exp_dir()
        task = Habituation(data_io, exp_dir, task_type, habi_params)
        task.start()

    if command == "stop":
        ending_criteria = task.ending_criteria
        task.stop = True
        end_time = datetime.now().strftime(
            hour_format
        )  # not the real endtime, but the time of entering "stop"
        data_io.store_meta_data(
            droid,
            start_time,
            end_time,
            exp_dir,
            task,
            None,
            None,
            ending_criteria=ending_criteria,
            procedure=task_type,
            pre_reversal=task.pre_reversal,
            experimenter=experimenter,
        )
        # store_reaction_times(exp_dir, task)
        data_io.store_pref_data(exp_dir)
        task.join()

        print("ending_criteria: " + ending_criteria)
        sys.exit()

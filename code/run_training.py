import sys, socket
from datetime import datetime
from pathlib import Path

from tasks.managers.path_manager import PathManager
from tasks.managers.data_io import DataIO
from tasks.managers.reader_writers import RotaryRecorder, SyncRecorder, TriggerPulse
from tasks.managers.utils.utils import plot_behavior_terminal

task, sync_rec, camera, rotary, exp_dir = None, None, None, None, None
droid = socket.gethostname()
# comment these lines if you don't want to get questions asked
# if droid == "bb8":
#     sync_bool = start_option('sync_pulse')
#     camera_bool = start_option('camera_trigger') # for bb8 comment this line too (for now) todo: check if you want ot change this


task_list = ['2afc', 'gonogo', 'detection']
task_dict = {
    'auditory_2afc': 'Auditory2AFC',
    'auditory_gonogo': 'AuditoryGoNoGo',
    'auditory_detection': 'AuditoryDetection'
}

# get the animal id and load the response matrix
animal_id = input("enter the mouse ID:")

input_task = input("enter the task:")
while True:
    if input_task in task_list:
        task_type = f'auditory_{input_task}'
        task_class_name = task_dict[task_type]
        break
    else:
        print("please enter one of the following names:")
        print(*task_list, sep=', ')
    task = input("enter the task:")

module = __import__(f"tasks.{task_type}", fromlist=[task_class_name])
TaskClass = getattr(module, task_class_name)
print(f"Successfully loaded {task_class_name} task.")

experimenter = input("who is running the experiment?")

hour_format = "%H:%M:%S"
start_time = datetime.now().strftime(hour_format)

path_manager = PathManager((Path(__file__).parent / '..').resolve(), animal_id)
data_io = DataIO(path_manager, task_type)


# booleans to set if you want to trigger camera/record sync pulses from 2p
sync_bool = False
camera_bool = False

while True:
    command = input("Enter 'start' to begin:")
    if command == "start":
        if not exp_dir:
            animal_dir = path_manager.check_dir()
            exp_dir = path_manager.make_exp_dir()
        task = TaskClass(data_io, exp_dir, task_type)
        rotary = RotaryRecorder(path_manager, exp_dir, task_type)
        if sync_bool:
            sync_rec = SyncRecorder(path_manager, exp_dir, task_type)
        if camera_bool:
            camera = TriggerPulse(path_manager, exp_dir, task_type)
        task.start()
        rotary.start()
        if sync_bool:
            sync_rec.start()
        if camera_bool:
            camera.start()

    if command == "stop":
        ending_criteria = task.ending_criteria
        task.check_stage()
        task.stop = True
        rotary.stop = True
        if sync_bool:
            sync_rec.stop = True
        if camera_bool:
            camera.stop = True
        # GPIO.cleanup()
        end_time = datetime.now().strftime(hour_format) # not the real endtime, but the time of entering "stop"
        data_io.store_meta_data(droid, start_time, end_time, exp_dir, task, sync_bool, camera_bool,
                        ending_criteria=ending_criteria, procedure=task_type, pre_reversal=task.pre_reversal,
                        experimenter=experimenter)
        # store_reaction_times(exp_dir, task)
        data_io.store_pref_data(exp_dir)
        task.join()
        rotary.join()
        if sync_bool:
            sync_rec.join()
        if camera_bool:
            camera.join()
        plot_behavior_terminal(data_io, exp_dir)  # plot behavior in terminal
        print("ending_criteria: " + ending_criteria)
        sys.exit()
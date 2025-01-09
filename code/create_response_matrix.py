"""
File to create response matrix for animals
Randomized assignment of animals to either first start high tone-turn wheel left/right and vice versa for low tones


"""
import os
import random
import json
from pathlib import Path

from tasks.managers.path_manager import PathManager
from tasks.managers.data_io import DataIO


# get the animal id
animal_id = input("enter the animal ID:")

task_list = ['2afc', 'gonogo', 'detection']
task = input("enter the task:")
path_manager = PathManager((Path(__file__).parent / '..').resolve(), animal_id)
data_io = DataIO(path_manager, task)
while True:
    if task in task_list:
        break
    else:
        print("please enter one of the following names:")
        print(*task_list, sep=', ')
    task = input("enter the task:")
# random assignment of either high/low - left/right combination
response_dict = {
    '2afc': ['left', 'right'],
    'gonogo': ['moved_wheel', 'no_response'],
    'detection': ['moved_wheel', 'no_response']
}

resp = response_dict[task]
if random.random() < 0.5:
    response_matrix = {
        'pre_reversal': {
            'high': resp[0],
            'low': resp[1]
        },
        'post_reversal': {
            'high': resp[1],
            'low': resp[0]
        }
    }
else:
    response_matrix = {
        'pre_reversal': {
            'high': resp[1],
            'low': resp[0]
        },
        'post_reversal':{
            'high': resp[0],
            'low': resp[1]
        }
    }

# store this response matrix as .json file in the data-directory of the animal
file_name = animal_id + "_response_matrix.json"
file_path= os.path.join(data_io.path_manager.check_dir(), file_name)
with open(file_path, "w") as outfile:
    json.dump(response_matrix, outfile, indent=4)


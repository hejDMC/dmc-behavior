"""
DMC-Behavior tutorial for loading/analyzing data

Example data is found in the .tutorial_data folder for one dummy animal and one example session
Here the a BehaviorData object is used to load the data

"""
#%%
import sys
sys.path.append('./tutorial')
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from behavior_data_object import BehaviorData

#%%
base_dir = Path('/home/felix/Desktop/tutorial')
data = BehaviorData(base_dir)  # initualize behavior data object
task_data = data.detection  # load data for task 'detection'

#%% plot performance for one session (similar to Figure 2D)

animal_id = '_det-001'
sess_id = '_20250113'
sess_data = getattr(getattr(task_data, animal_id), sess_id).trial.complete
outcome_data = np.zeros(len(sess_data), dtype=int)
hit_trials = [h.trial_num for h in getattr(getattr(task_data, animal_id), sess_id).trial.moved_wheel]
outcome_data[hit_trials] = 1
rolling_mean = np.convolve(outcome_data, np.ones(10)/10, mode='valid')
padding = np.full(10 - 1, np.nan)  # Create an array of NaN with length (window_size - 1)
pad_rolling_mean = np.concatenate((padding, rolling_mean))
fig, ax = plt.subplots()
sns.lineplot(ax=ax, x=np.arange(len(pad_rolling_mean)), y=pad_rolling_mean, color='forestgreen', lw=2, clip_on=False)
yticks = [0, 0.25, 0.5, 0.75, 1.0]
ax.set_yticks(yticks)
ax.set_ylim(0, 1)
ax.set_yticklabels([f'{int(y*100)}' for y in yticks], fontsize=12)
ax.set_ylabel('Correct choices [%]', fontsize=14)
ax.tick_params(axis='x', labelsize=12)
ax.set_xlabel('Trial number', fontsize=14)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.show()

#%% to access rotary/sync_pulse/camera data
# rotary_data = getattr(getattr(task_data, animal_id), sess_id).rotary.all
# sync_data = getattr(getattr(task_data, animal_id), sess_id).sync_pulse.all
# camera_data = getattr(getattr(task_data, animal_id), sess_id).camera.all


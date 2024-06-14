# *DMC Behavior Platform* - day-to-day operation guide

## Start up (optional if the Raspberry Pi was not turned off between days)
- open a terminal on the computer you use to control the setups and SSH into the Raspberry Pi:
```
ssh pi@<ip address>
```
- if you are unsure about the IP address, you can ping it (see [here](https://www.raspberrypi.com/documentation/computers/remote-access.html#ip-address) for more info)
```
ping raspberrypi.local
```
- you should now see the Raspberry Pi command prompt:
```
pi@<nameofpi> ~ $
```
- cd into the *DMC-Behavior* directory, activate the venv and set GPIO pin 4 to high (just to be sure...):
```
cd 2p-behavior
source ./venv/bin/activate
raspi-gpio set 4 op dh
```

## Start the experiment
### Create the response matrix (only once at the beginning of the training)
- a *response matrix* is unique file for each mouse linking stimuli to responses. E.g. for the auditory 2AFC task animals it needs to be set to which side (left/right) animals need turn the wheel when either high or low tone clouds are presented to obtain rewards for correct choices.
- for creating the `response_matrix` file, run the following script (or use the alias if one was created previously, see the *DMC-Behavior-Platform_Software-installation* guide):
```
python code/create-response-matrix.py
```
- you will be prompted to enter the *animal_id* of the animal in question (confirm by pressing `Enter`) and the task the animal is going to perform (confirm by pressing `Enter`) the animal will be randomly assigned to a group (e.g. high tone clouds-right turn/low tone clouds-left turns or vice versa for the auditory 2AFC taks):
```
enter the mouse ID: <animal_id>
enter the task: <task>
```
- now a folder with the name of the *animal_id* in the `data` directory is created containing the `<animal_id>_response_matrix.json` file is created
- you can check this by typing:
```
ls data/<animal_id>
```

### Run a training protocol:
#### Habituation
- in general, training an animal on a complex behavioral task is performed in different stages (see the ms for details on the respective behaviors)
- firstly, animals need to be habituated to being head-fixed, the auditory stimuli used and need learn to consume liquid rewards
- for this, we run the `habituation` script by either running the script directly or use the alias if one was created previously (see the *DMC-Behavior-Platform_Software-installation* guide):
```
python code/habituation_auditory_tasks>.py
```
- you will be prompted to enter the *animal_id*, name of the experimenter, the task and day of the habituation (confirm by pressing `Enter`):
```
enter the mouse ID:<animal_id>
who is running the experiment?<name-experimenter>
2afc task (no assumes gonogo/detection)? y/n: <y/n>
what day of habituation is it (1/2/3)?:<day-of-habituation>
```
- after you entered all required information, the habituation protocol will commence and automatically terminate once the time limit is reached
- all behavioral data is stored in a subfolder (day-of-experiment/Time-of-experiment) in the *animal_id* folder in the `data` directory:
```
data/<animal_id>/<YYYYMMDD>/<HHMMSS>
```

#### Training
- after the habituation procedure is completed, the actual training can begin (training progression in staged protocols will be tracked automatically)
- for this, run the `training` script by either running the script directly or use the alias if one was created previously (see the *DMC-Behavior-Platform_Software-installation* guide):
```
python code/<training-script>.py
```
- you will be prompted to enter the *animal_id* and name of the experimenter (confirm by pressing `Enter`):
```
enter the mouse ID:<animal_id>
who is running the experiment?<name-experimenter>
```
- if the information is correct and you are ready to commence, enter `start` and press `Enter`:
```
Enter 'start' to begin: start
```
- the training will begin and terminate automatically if the time limit or disengagement criteria specified in the script are reached
- if you want to terminate the script manually, type `stop` in the console and press `Enter`
- during training, some basic performance information will be printed in the console, after termination of the training general performance information alongside a visualization of the performance will be printed in the terminal
- as for the `habituation`, all behavioral data is stored in a subfolder (Day-of-experimet/Time-of-experiment) in the *animal_id* folder in the `data` directory:
```
data/<animal_id>/<YYYYMMDD>/<HHMMSS>
```
- the general structure of data storage is the following:
```
data
│
└───animal_id-1
│   │
│   └───date_of_experiment-(YYYYMMDD)
│       │
│       └───individual_experiment-1-(HHMMSS)
│           │   meta-data.json
│           │   droid_prefs.json
│           │   task_prefs.json
│           │   rotary_data.csv
│           │   trial_data.csv
│           │   ...
│   
└───animal_id-2
    │   ...
```
- the `meta-data.json` provides general info on the current sessions (including central parameters like the tones used as well as on the duration of the session etc.). The `droid_prefs.json` file provides info on the pin mapping etc. and is just copied here for completeness (the file is more used by the experimental scripts to read out central parameters like sampling rates and pin mapping). The `task_prefs.json` file contains the task specific parameters (e.g. ITI, response window etc.) that were used for the present task (these differ e.g. between experimental stages). The `.csv` files contain the actual behavioral data that are used to reconstruct to the animals' performance later on. Which files are present depends on the task used (e.g. no rotary data during habituation as the wheel is fixed) or if e.g. 2P imaging was performed (no 2P sync data otherwise). The `trial_data.csv` contains the most detailed, timestamped information on what was done when.  


### Data transfer
- all behavioral data is locally stored on the SSD of the Raspberry Pi, for transferring data it is highly recommended to use a FTP client (e.g. [FileZilla](https://filezilla-project.org))
- you can also transfer the data using SSH/SCP with the following command:
```
scp -r pi@<ip address>:/home/pi/dmc-behavior/data/<animal_id> <destination/to/copy/data/to>
```

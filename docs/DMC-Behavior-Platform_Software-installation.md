# *DMC Behavior Platform* - software installation guide

## Hardware setup
- assemble the behavior rig as described in the **DMC-Behavior-Platform_Hardware-assembly.md** guide
- Install the [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on the computer you use to connect to the setups and flash the microSD card with the Raspberry Pi OS (tested version: Buster (10, Desktop)).
- During installation select a *name* for your Pi, a *password* and *enable SSH*
- Insert the flashed microSD card into the Raspberry Pi and boot the Pi (= connect it to power)

## SSH into the Raspberry Pi
- open a command terminal on the computer you use to control the setups
- SSH into the Raspberry Pi by:
```
ssh pi@<ip address>
```
- if you are unsure about the IP address, you can ping it (see [here](https://www.raspberrypi.com/documentation/computers/remote-access.html#ip-address) for more info) and subsequently SSH into the Raspberry Pi by the command above:
```
ping raspberrypi.local
```
- you should now see the Raspberry Pi command prompt:
```
pi@<nameofpi> ~ $
```

## Install the HifiBerry Amp2
- check if PulseAudio is installed (on the default newer Raspi OS versions it is) by entering:
```
pulseaudio --version
```
- if the output in the terminal shows a version, this message indicates it isinstalled and that we need to remove it, if not just go ahead. PulseAudio is uninstalled by (commands need to be executed individually): 
```
sudo apt-get remove pulseaudio
sudo apt autoremove
sudo /etc/init.d/alsa-utils reset
sudo reboot now
```
- after reboot, SSH into the Pi again (as above)
- for the HifiBerry Amp2 installation, the guide was taken from this [website](http://www.waailap.nl/instruction/215/setup-hifiberry-amp2.html)
- open the boot config file:
```
sudo nano /boot/config.txt
```
- find this line and comment it (by placing a hash (#) in front of the line):
```
dtparam=audio=on
```
- add this line to the config file:
```
dtoverlay=hifiberry-dacplus
```
- then create the following file using this command:
```
sudo nano /etc/asound.conf
```
- and add this content:
```
pcm.!default {
    type hw card 0
}
ctl.!default {
    type hw card 0
}
```  

- make sure no `asound.conf` file is in the home directory (i.e. the directory you are in at the moment). For listing all files in your current directory enter:
```
ls -a
```  
- no `asound.conf` file should be listed. If you see a file of that name remove it by entering:
```
rm asound.conf
```
- reboot the Pi and SSH into it (see above) after it has booted again:
```
sudo reboot now
```
- enter the following command to list the soundcards:
```
aplay -l
```
- the output should only show one card and look like this:

```
**** List of PLAYBACK Hardware Devices ****
card 0: sndrpihifiberry [snd_rpi_hifiberry_dacplus], device 0: HiFiBerry DAC+ HiFi pcm512x-hifi-0 [HiFiBerry DAC+ HiFi pcm512x-hifi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```
- it now should be possible to check and set the output volume from the *Hifiberry* using the following commands: 
```
amixer sget Digital
amixer sset Digital 60%
```
- if you get the error that you don't have *Digital* but only the *Master*, this is due to the PulseAudio package. Try uninstalling it again. [Here](https://www.hifiberry.com/blog/using-amixer/) is also a blog post with some additional info on how to set the Digital audio.
- for testing the output, you can install *mplayer* and try to play this music file (should be some guitar music; taken from the installation guide referred to above):
```
sudo apt-get install mplayer
mplayer http://www.waailap.nl/upload/test.mp3
```

- if you don't hear anything, it might be that the GPIO4 pin of the Raspberry Pi is set to low (this mutes the Hifiberry) and run the music file again:
`raspi-gpio set 4 op dh`  

## Install the *DMC-Behavior* software

- download the code from the github repo
```
git clone https://github.com/hejDMC/dmc-behavior
```
- cd into the folder you just downloaded
```
cd dmc-behavior
```
- create a venv to install the required packages:
```
python3.7 -m venv ./venv
```
- activate the environment and install the required packages
```
source ./venv/bin/activate
pip install -r docs/requirements.txt
```
- the data will be stored in this directory in a folder called data, create this folder now:
```
mkdir data
```

## Perform pump calibration
- *in general, it is recommended to perform a calibration of the pumps routinely*
- pump calibration describes a procedure to estimate how much liquid reward is delivered are a given opening time of the pump
- pump calibration needs to be performed before running any task, otherwise a default pump opening time is used
- for pump calibration, pumps are opened for x ms repeated n times. the amount of liquid A needs to be collected and measured (e.g. using a scale or syringes), afterwards by dividing A/n, we calculate the amount of reward that is delivered for a pump opening time x. As an example, you open the pump for x=150 ms for n=100 times and collected an amount of liquid of A=300 ul, resulting in 300/100 = 3ul for a pump opening time of 150 ms. the pump calibration script will prompt you to enter the pump opening time for 1 ul, so enter `50` (=150 ms/ 3 ul). you can repeat the calibration procedure with other pump times to verify that the time of pump opening is linear to the amount of liquid distributed. **currently, the `dmc-behavior` platform assumes this linear relationship and does not work otherwise without adjusted the code**
- to run the pump calibration enter:
```
python code/utils/pump_calibration.py
```

## Create aliases for your behavioral paradigm (optional, recommended)
### Background
- the scripts for running distinct behavioral paradigms (e.g. an auditory 2AFC task) are located in the `code` folder and run by a terminal command, e.g.:
```
python code/<name-of-the-script>.py
```
- to make your life easier, you can create aliases in the `.bashrc` file in the home directory of the Pi which allows you to run the command above by just entering the alias:
```
<alias-of-script>
```
- to manually create an alias, cd into the home directory:
```
cd ~
```
- open the `.bashrc` file:
```
nano .bashrc
```
- and add an alias at a suitable location:
```
alias <alias-of-script>='python code/<name-of-the-script>.py'
```
- save the changes by pressing `CTRL+S` and close the file by pressing `CTRL+X`
- source the `.bashrc` so the changes take effect (will automatically happen if you reboot the Pi):
```
source .bashrc
```
- an example could look like this:
```
alias rm='python code/create_response_matrix.py'
alias habi='python code/habituation_auditory_tasks.py'
alias 2afc='python code/run_auditory_2afc.py'
```
- the first alias (`rm`) will run the script to create a response matrix for an animal, the second alias (`habi`) will run the script for habituation protocol for an animal and the last alias (`2afc`) will run the script for the auditory 2AFC task (see the *DMC-Behavior-Platform_Day-to-day-operation* guide for details)
## Known issues
- sometimes the `sounddevices` packages lacks the following packages, which can you can install by:
```
sudo apt-get install -y python3-dev libasound2-dev
sudo apt-get install libportaudio2
sudo apt-get install libasound-dev
```

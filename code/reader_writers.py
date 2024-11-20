import threading
import time
import RPi.GPIO as GPIO

class TriggerPulse(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.droid_settings = load_droid_setting()
        self.trigger_rate = self.droid_settings['base_params']['camera_trigger_rate']  # in Hz
        self.trigger_pin = self.droid_settings['pin_map']['OUT']['trigger_camera']
        self.trigger_state = 0
        self.fn = exp_dir.joinpath(f'{get_today()}_camera_pulse_data.csv')
        self.stop = False

    def write_camera_data(self):
        with open(self.fn, "a") as log:
            log.write("{0},{1}\n".format(time.time(), self.trigger_state))

    def pull_trigger(self):
        self.trigger_state = 1
        GPIO.setup(self.trigger_pin, GPIO.OUT)
        GPIO.output(self.trigger_pin, self.trigger_state)
        self.write_camera_data()
        self.trigger_state = 0
        GPIO.output(self.trigger_pin, self.trigger_state)
        self.write_camera_data()
        time.sleep(1/self.trigger_rate)

    def run(self):
        while not self.stop:
            # Loop this infinitely until stop
            self.pull_trigger()


class RotaryRecorder(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.droid_settings = load_droid_setting()
        self.rotary_rate = self.droid_settings['base_params']['rotary_rate']  # Hz for sampling
        self.animal_dir = animal_dir
        self.fn = exp_dir.joinpath(f'{get_today()}_rotary_data.csv')

        # get pin info from droid settings and initialize pins (GPIO numbers)
        # set encoder parameters and initialize pins (GPIO numbers!)
        self.encoder_left = self.droid_settings['pin_map']['IN']['encoder_left_rec']  # pin of left encoder (green wire)
        self.encoder_right = self.droid_settings['pin_map']['IN']['encoder_right_rec']  # pin of right encoder (gray wire)
        self.encoder_data = Encoder(self.encoder_left, self.encoder_right)
        # self.wheel_position = self.encoder_data.getValue()

        self.stop = False

    def write_sync_data(self):

        self.wheel_position = self.encoder_data.getValue()
        with open(self.fn, "a") as log:
            log.write("{0},{1}\n".format(time.time(), str(self.wheel_position)))  #  todo: 0: time_stamp, 1: 2p sync_pulse
            time.sleep(1/self.rotary_rate)

    def run(self):
        while not self.stop:
            # Loop this infinitely until stop
            self.write_sync_data()


class SyncRecorder(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.droid_settings = load_droid_setting()
        self.sync_rate = self.droid_settings['base_params']['2p_sync_rate']  # Hz for sampling, needs to be at least twice as high as 2p sync freq. (Nyquist)
        self.animal_dir = animal_dir
        self.fn = exp_dir.joinpath(f'{get_today()}_sync_pulse_data.csv')

        # get pin info from droid settings and initialize pins (GPIO numbers)
        self.sync_pin = self.droid_settings['pin_map']['IN']['microscope_sync']
        self.sync_pulse = Sync_Pulse(self.sync_pin)
        self.stop = False

    def write_sync_data(self):
        with open(self.fn, "a") as log:
            log.write("{0},{1}\n".format(time.time(), str(self.sync_pulse.get_value())))  #  todo: 0: time_stamp, 1: 2p sync_pulse
            time.sleep(1/self.sync_rate)

    def run(self):
        while not self.stop:
            # Loop this infinitely until stop
            self.write_sync_data()

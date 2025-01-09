import threading
import time

import RPi.GPIO as GPIO
from data_io import DataIO
from utils.encoder import Encoder
from utils.sync_pulse import Sync_Pulse


class BaseRecorder(threading.Thread):
    def __init__(self, path_manager, exp_dir, task_type, file_name_suffix, rate_key):
        super().__init__()
        data_io = DataIO(path_manager, task_type)
        self.droid_settings = data_io.load_droid_setting()
        self.rate = self.droid_settings["base_params"][rate_key]

        self.fn = exp_dir.joinpath(f"{path_manager.get_today()}_{file_name_suffix}.csv")
        self.stop = False

    def write_data(self, data):
        """Writes data to the file."""
        with open(self.fn, "a") as log:
            log.write(f"{time.time()},{data}\n")

    def run(self):
        while not self.stop:
            self.record()

    def record(self):
        """This method should be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement the record method.")


class TriggerPulse(BaseRecorder):
    def __init__(self, path_manager, exp_dir, task_type):
        super().__init__(
            path_manager,
            exp_dir,
            task_type,
            file_name_suffix="camera_pulse_data",
            rate_key="camera_trigger_rate",
        )
        self.trigger_pin = self.droid_settings["pin_map"]["OUT"]["trigger_camera"]
        self.trigger_state = 0
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trigger_pin, GPIO.OUT)

    def pull_trigger(self):
        self.trigger_state = 1
        GPIO.output(self.trigger_pin, self.trigger_state)
        self.write_data(self.trigger_state)
        self.trigger_state = 0
        GPIO.output(self.trigger_pin, self.trigger_state)
        self.write_data(self.trigger_state)
        time.sleep(1 / self.rate)

    def record(self):
        self.pull_trigger()


class RotaryRecorder(BaseRecorder):
    def __init__(self, path_manager, exp_dir, task_type):
        super().__init__(
            path_manager,
            exp_dir,
            task_type,
            file_name_suffix="rotary_data",
            rate_key="rotary_rate",
        )
        self.encoder_left = self.droid_settings["pin_map"]["IN"]["encoder_left_rec"]
        self.encoder_right = self.droid_settings["pin_map"]["IN"]["encoder_right_rec"]
        self.encoder_data = Encoder(self.encoder_left, self.encoder_right)

    def record(self):
        wheel_position = str(self.encoder_data.getValue())
        self.write_data(wheel_position)
        time.sleep(1 / self.rate)


class SyncRecorder(BaseRecorder):
    def __init__(self, path_manager, exp_dir, task_type):
        super().__init__(
            path_manager,
            exp_dir,
            task_type,
            file_name_suffix="sync_pulse_data",
            rate_key="2p_sync_rate",
        )
        self.sync_pin = self.droid_settings["pin_map"]["IN"]["microscope_sync"]
        self.sync_pulse = Sync_Pulse(self.sync_pin)

    def record(self):
        sync_value = str(self.sync_pulse.get_value())
        self.write_data(sync_value)
        time.sleep(1 / self.rate)


#
#
# class TriggerPulse(threading.Thread):
#     def __init__(self):
#         threading.Thread.__init__(self)
#         self.trigger_rate = self.droid_settings['base_params']['camera_trigger_rate']  # in Hz
#         self.trigger_pin = self.droid_settings['pin_map']['OUT']['trigger_camera']
#         self.trigger_state = 0
#
#
#     def write_camera_data(self):
#         with open(self.fn, "a") as log:
#             log.write("{0},{1}\n".format(time.time(), self.trigger_state))
#
#     def pull_trigger(self):
#         self.trigger_state = 1
#         GPIO.setup(self.trigger_pin, GPIO.OUT)
#         GPIO.output(self.trigger_pin, self.trigger_state)
#         self.write_camera_data()
#         self.trigger_state = 0
#         GPIO.output(self.trigger_pin, self.trigger_state)
#         self.write_camera_data()
#         time.sleep(1/self.trigger_rate)
#
#     def run(self):
#         while not self.stop:
#             # Loop this infinitely until stop
#             self.pull_trigger()
#
#
# class RotaryRecorder(threading.Thread):
#     def __init__(self):
#         threading.Thread.__init__(self)
#         self.rotary_rate = self.droid_settings['base_params']['rotary_rate']  # Hz for sampling
#
#         # get pin info from droid settings and initialize pins (GPIO numbers)
#         # set encoder parameters and initialize pins (GPIO numbers!)
#         self.encoder_left = self.droid_settings['pin_map']['IN']['encoder_left_rec']  # pin of left encoder (green wire)
#         self.encoder_right = self.droid_settings['pin_map']['IN']['encoder_right_rec']  # pin of right encoder (gray wire)
#         self.encoder_data = Encoder(self.encoder_left, self.encoder_right)
#         # self.wheel_position = self.encoder_data.getValue()
#
#         self.stop = False
#
#     def write_sync_data(self):
#
#         self.wheel_position = self.encoder_data.getValue()
#         with open(self.fn, "a") as log:
#             log.write("{0},{1}\n".format(time.time(), str(self.wheel_position)))  #  todo: 0: time_stamp, 1: 2p sync_pulse
#             time.sleep(1/self.rotary_rate)
#
#     def run(self):
#         while not self.stop:
#             # Loop this infinitely until stop
#             self.write_sync_data()
#
#
# class SyncRecorder(threading.Thread):
#     def __init__(self):
#         threading.Thread.__init__(self)
#         self.sync_rate = self.droid_settings['base_params']['2p_sync_rate']  # Hz for sampling, needs to be at least twice as high as 2p sync freq. (Nyquist)
#
#         # get pin info from droid settings and initialize pins (GPIO numbers)
#         self.sync_pin = self.droid_settings['pin_map']['IN']['microscope_sync']
#         self.sync_pulse = Sync_Pulse(self.sync_pin)
#         self.stop = False
#
#     def write_sync_data(self):
#         with open(self.fn, "a") as log:
#             log.write("{0},{1}\n".format(time.time(), str(self.sync_pulse.get_value())))  #  todo: 0: time_stamp, 1: 2p sync_pulse
#             time.sleep(1/self.sync_rate)
#
#     def run(self):
#         while not self.stop:
#             # Loop this infinitely until stop
#             self.write_sync_data()

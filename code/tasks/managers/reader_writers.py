import threading
import time
import csv

import RPi.GPIO as GPIO
from tasks.managers.data_io import DataIO
from tasks.managers.utils.encoder import Encoder
from tasks.managers.utils.sync_pulse import Sync_Pulse


class BaseRecorder(threading.Thread):
    def __init__(self, path_manager, exp_dir, task_type, file_name_suffix, rate_key):
        super().__init__()
        data_io = DataIO(path_manager, task_type)
        self.droid_settings = data_io.load_droid_setting()
        self.rate = self.droid_settings["base_params"][rate_key]

        self.fn = exp_dir.joinpath(f"{path_manager.get_today()}_{file_name_suffix}.csv")
        self.file = open(self.fn, mode='w', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(["timestamp", "value"])  # CSV header

        self.stop = False

    def write_data(self, data):
        """Writes data to the file."""
        # with open(self.fn, "a") as log:
        #     log.write(f"{time.time()},{data}\n")
        self.writer.writerow([time.time(), data])
        self.file.flush()  # Ensure data is written immediately

    def run(self):
        while not self.stop:
            self.record()
        self.file.close()

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
        self.write_data(self.trigger_state)  # todo move one line down
        GPIO.output(self.trigger_pin, self.trigger_state)
        time.sleep(1 / (self.rate / 2))
        self.trigger_state = 0
        GPIO.output(self.trigger_pin, self.trigger_state)
        self.write_data(self.trigger_state)
        time.sleep(1 / (self.rate / 2))

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

#
# class SyncRecorder(BaseRecorder):
#     def __init__(self, path_manager, exp_dir, task_type):
#         super().__init__(
#             path_manager,
#             exp_dir,
#             task_type,
#             file_name_suffix="sync_pulse_data",
#             rate_key="2p_sync_rate",
#         )
#         self.sync_pin = self.droid_settings["pin_map"]["IN"]["microscope_sync"]
#         self.sync_pulse = Sync_Pulse(self.sync_pin)
#         self.timer = time.time() + 60
#         self.file_counter = 0
#
#
#     def record(self):
#         if time.time() > self.timer:
#             self.file.close()
#             self.file_counter += 1
#             self.fn = self.fn.parent.joinpath(f"{self.fn.stem}_{self.file_counter}.csv")
#             self.file = open(self.fn, mode='w', newline='')
#             self.writer = csv.writer(self.file)
#             self.writer.writerow(["timestamp", "value"])
#             self.timer = time.time() + 60
#
#         sync_value = str(self.sync_pulse.get_value())
#         self.write_data(sync_value)
#         time.sleep(1 / self.rate)

#
# class SyncRecorder(BaseRecorder):
#     def __init__(self, path_manager, exp_dir, task_type):
#         super().__init__(
#             path_manager,
#             exp_dir,
#             task_type,
#             file_name_suffix="sync_pulse_data",
#             rate_key="2p_sync_rate",
#         )
#         self.sync_pin = self.droid_settings["pin_map"]["IN"]["microscope_sync"]
#         self.sync_pulse = Sync_Pulse(self.sync_pin)
#         self.sync_pulse_list = []
#         self.old_value = 0
#
#     def record(self):
#         sync_value = str(self.sync_pulse.get_value())
#         if sync_value != self.old_value:
#             self.sync_pulse_list.append([time.time(), sync_value])
#             # self.write_data(sync_value)
#         self.old_value = sync_value
#         if self.stop:
#             self.writer.writerows(self.sync_pulse_list)

class SyncRecorder(threading.Thread):
    def __init__(self, path_manager, exp_dir, task_type):
        super().__init__()
        data_io = DataIO(path_manager, task_type)
        self.droid_settings = data_io.load_droid_setting()
        self.fn = exp_dir.joinpath(f"{path_manager.get_today()}_sync_pulse_data.csv")
        self.running = False
        self.file = open(self.fn, mode='w', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(["Timestamp", "PinState"])  # CSV header
        self.sync_pulse_list = []

        self.stop = False

        self.sync_pin = self.droid_settings["pin_map"]["IN"]["microscope_sync"]
        GPIO.setup(self.sync_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        # self.sync_pulse = Sync_Pulse(self.sync_pin, callback=self._transition_occurred)

    def run(self):
        GPIO.add_event_detect(self.sync_pin, GPIO.RISING, callback=self._transition_occurred)
        while not self.stop:
            pass
        self.writer.writerows(self.sync_pulse_list)
        GPIO.remove_event_detect(self.sync_pin)  # Remove event detection
        self.file.close()

    def _transition_occurred(self, pin):
        if not self.stop:
            self.sync_pulse_list.append([time.time(), 1])
            # self.writer.writerow([time.time(), 1])
            # self.file.flush()  # Ensure data is written immediately


# class SyncRecorder(threading.Thread):
#     def __init__(self, path_manager, exp_dir, task_type):
#         super().__init__()
#         data_io = DataIO(path_manager, task_type)
#         self.droid_settings = data_io.load_droid_setting()
#         self.fn = exp_dir.joinpath(f"{path_manager.get_today()}_sync_pulse_data.csv")
#         self.sync_pin = self.droid_settings["pin_map"]["IN"]["microscope_sync"]
#         self.stop = False
#
#         self.sync_pin = self.sync_pin  # GPIO pin on raspi
#
#
#         # Initialize Sync_Pulse with a callback to write data on rising edge
#         self.sync_pulse = Sync_Pulse(self.sync_pin, callback=self.write_sync_data)
#
#     def write_sync_data(self):
#         """Writes data to the file only on rising edge."""
#         with open(self.fn, "a") as log:
#             log.write(f"{time.time()},1\n")
#
#     def run(self):
#         while not self.stop:
#             self.sync_pulse.transition_occurred()

#     def stop_recording(self):
#         self.stop = True
#         GPIO.cleanup()
# #
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

"""
Pump calibration: to estimate the amount of liquid dispensed by the pump per time

Enter the duration of pumping and the number of repeats
Collect the amount dispensed and calculate the average
Enter the duration for dispensing 1 ul liquid -- this will be used by the behavioral scripts

"""

import json
import socket
import time
from pathlib import Path

import RPi.GPIO as GPIO

from tasks.managers.data_io import DataIO
from tasks.managers.path_manager import PathManager

path_manager = PathManager((Path(__file__).parent / "..").resolve(), 'pump_calibration')
data_io = DataIO(path_manager, 'pump_calibration')

# get droid name
droid = socket.gethostname()
# get pump pin
droid_settings = data_io.load_droid_setting()
pump_pin = droid_settings["pin_map"]["OUT"]["pump"]

# enter pump duration and the number of repeats
print(">>>>>> PUMP CALIBRATION <<<<<<")
duration = int(input("enter the duration of pump opening(in ms):"))
number_repeats = int(input("enter the number of repeats:"))

# open the pump for duration of x for the number of repeats n
pin = pump_pin  # use GPIO number!!
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)  # change to GPIO number
GPIO.setup(pin, GPIO.OUT)
GPIO.output(pin, GPIO.LOW)  # pin low --> pump closed
for i in range(number_repeats):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(duration / 1000)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(0.5)

pump_time = int(
    input(
        "enter the duration of pump opening resulting in delivery of 1 ul reward (in ms):"
    )
)
pump_cali_dir = path_manager.check_dir()
pump_dict = {droid: pump_time}
pump_fn = pump_cali_dir.joinpath(f"{path_manager.get_today()}_pump_calibration.json")
with open(pump_fn, "w") as f:
    json.dump(pump_dict, f, indent=4)
print(f"pump calibration data saved to {str(pump_fn)}")
GPIO.cleanup()

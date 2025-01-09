"""
Class to monitor sync pulses, e.g. from 2P, camera or behavioral setups with raspberry pi

November 2021 - FJ
"""

import RPi.GPIO as GPIO


class Sync_Pulse:

    def __init__(self, sync_pin, callback=None):
        self.sync_pin = sync_pin  # GPIO pin on raspi
        self.value = 0  # start with 0 as beginning of trial pin should be low
        self.callback = callback  # optional, not integrated at the momement
        GPIO.setup(
            self.sync_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN
        )  # initialize pin as input pin
        GPIO.add_event_detect(
            self.sync_pin, GPIO.BOTH, callback=self.transition_occured
        )  # monitor transitions at pin (high/low)

    def transition_occured(self, channel):
        # once transition occurs high-low, low-high, change the value to either 0 or 1
        if self.value == 0:
            self.value = 1
        elif self.value == 1:
            self.value = 0
        if self.callback is not None:  # not integrated at the momement
            self.callback(self.value)

    def get_value(self):
        return self.value

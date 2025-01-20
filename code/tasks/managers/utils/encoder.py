# Class to monitor a rotary encoder and update a value.  You can either read the value when you need it, by calling getValue(), or
# you can configure a callback which will be called whenever the value changes.
# adapted from: https://github.com/nstansby/rpi-rotary-encoder-python

import pigpio


class Encoder:

    def __init__(self, leftPin, rightPin, callback=None):
        self.leftPin = leftPin
        self.rightPin = rightPin
        self.value = 0
        self.state = "00"
        self.direction = None
        self.callback = callback

        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise Exception("Could not connect to pigpio daemon.")

        self.pi.set_mode(self.leftPin, pigpio.INPUT)
        self.pi.set_pull_up_down(self.leftPin, pigpio.PUD_DOWN)
        self.pi.set_mode(self.rightPin, pigpio.INPUT)
        self.pi.set_pull_up_down(self.rightPin, pigpio.PUD_DOWN)

        # Add callbacks for both pins
        self.cb_left = self.pi.callback(self.leftPin, pigpio.EITHER_EDGE, self.transitionOccurred)
        self.cb_right = self.pi.callback(self.rightPin, pigpio.EITHER_EDGE, self.transitionOccurred)

    def transitionOccurred(self, channel):
        p1 = self.pi.read(self.leftPin)
        p2 = self.pi.read(self.rightPin)
        newState = f"{p1}{p2}"

        if self.state == "00":  # Resting position
            if newState == "01":  # Turned right 1
                self.direction = "R"
            elif newState == "10":  # Turned left 1
                self.direction = "L"

        elif self.state == "01":  # R1 or L3 position
            if newState == "11":  # Turned right 1
                self.direction = "R"
            elif newState == "00":  # Turned left 1
                if self.direction == "L":
                    self.value = self.value - 1
                    if self.callback is not None:
                        self.callback(self.value)

        elif self.state == "10":  # R3 or L1
            if newState == "11":  # Turned left 1
                self.direction = "L"
            elif newState == "00":  # Turned right 1
                if self.direction == "R":
                    self.value = self.value + 1
                    if self.callback is not None:
                        self.callback(self.value)

        else:  # self.state == "11"
            if newState == "01":  # Turned left 1
                self.direction = "L"
            elif newState == "10":  # Turned right 1
                self.direction = "R"
            elif (
                newState == "00"
            ):  # Skipped an intermediate 01 or 10 state, but if we know direction then a turn is complete
                if self.direction == "L":
                    self.value = self.value - 1
                    if self.callback is not None:
                        self.callback(self.value)
                elif self.direction == "R":
                    self.value = self.value + 1
                    if self.callback is not None:
                        self.callback(self.value)

        self.state = newState

    def getValue(self):
        return self.value

    def cleanup(self):
        # Cancel callbacks and stop pigpio instance
        self.cb_left.cancel()
        self.cb_right.cancel()
        self.pi.stop()
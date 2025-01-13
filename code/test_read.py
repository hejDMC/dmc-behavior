import RPi.GPIO as GPIO
import time

pin = 11


GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin,GPIO.IN)
time.sleep(0.5)
while True:
   print(GPIO.input(pin))

"""
import pigpio
import time

pi1 = pigpio.pi()
while True:
    print(pi1.read(18))  # use GPIO numbering
"""

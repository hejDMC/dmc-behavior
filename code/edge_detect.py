import RPi.GPIO as GPIO
import time

# Pin configuration
SYNC_PIN = 17  # Replace with your GPIO pin number

# Callback function to handle edge events
def edge_detected(channel):
    """Prints info when an edge event is detected."""
    timestamp = time.time()
    print(f"Rising edge detected on pin {channel} at {timestamp:.6f}")

# Setup GPIO
GPIO.setmode(GPIO.BCM)  # Use BCM numbering
GPIO.setup(SYNC_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Add event detection
GPIO.add_event_detect(SYNC_PIN, GPIO.RISING, callback=edge_detected)

print(f"Monitoring GPIO pin {SYNC_PIN} for rising edges. Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(0.01)
except KeyboardInterrupt:
    print("Exiting...")

# Cleanup GPIO on exit
GPIO.cleanup()
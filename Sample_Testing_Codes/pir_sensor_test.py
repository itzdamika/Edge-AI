import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
PIR_PIN = 17
GPIO.setup(PIR_PIN, GPIO.IN)

try:
    print("PIR Module Test (Press CTRL+C to exit)")
    time.sleep(2)
    while True:
        if GPIO.input(PIR_PIN):
            print("Motion detected!")
        else:
            print("No motion")
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting...")
finally:
    GPIO.cleanup()
import time
import board
import adafruit_dht

# Initialize the DHT22 sensor on GPIO27 (adjust this to your wiring)
dhtDevice = adafruit_dht.DHT22(board.D27)

while True:
    try:
        temperature = dhtDevice.temperature
        humidity = dhtDevice.humidity
        print("Temperature: {:.1f}°C  Humidity: {:.1f}%".format(temperature, humidity))
    except Exception as e:
        print("DHT22 error:", e)
    time.sleep(2)  # Wait 2 seconds between readings

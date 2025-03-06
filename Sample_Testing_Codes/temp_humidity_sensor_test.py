import adafruit_dht
import board

dht_device = adafruit_dht.DHT22(board.D4)
temperature = dhtDevice.temperature
humidity = dhtDevice.humidity
print("Temp: {:.1f} C, Humidity: {:.1f}%".format(temperature, humidity))
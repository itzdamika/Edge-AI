import board
import adafruit_ssd1306

oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
oled.fill(0)
oled.text('Hello OLED!', 0, 0, 1)
oled.show()
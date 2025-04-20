import busio
import digitalio
import board
from adafruit_mcp3xxx.mcp3008 import MCP3008
from adafruit_mcp3xxx.analog_in import AnalogIn

spi = busio.SPI(clock=..., MOSI=..., MISO=...) # define pins accordingly
mcp = MCP3008(spi, cs)
channel0 = AnalogIn(mcp, MCP.P0)

print('ADC Voltage:', channel0.voltage)
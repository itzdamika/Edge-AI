# convert_and_test.py

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, Dropout, Flatten, Dense, Reshape
import tflite_runtime.interpreter as tflite
import subprocess

# 1) Build a simple Conv1D model (no LSTM, no Flex ops)
LOOKBACK = 5
PREDICT_FORWARD = 5

model = Sequential([
    Conv1D(32, kernel_size=2, activation='relu', input_shape=(LOOKBACK, 1)),
    Dropout(0.2),
    Flatten(),
    Dense(64, activation='relu'),
    Dense(PREDICT_FORWARD),
    Reshape((PREDICT_FORWARD, 1))
])
model.compile(optimizer='adam', loss='mse')
print("✅ Model built.")

# 2) Convert to TFLite using only BUILTIN ops
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

out_path = "models/temperature_model_pi.tflite"
with open(out_path, "wb") as f:
    f.write(tflite_model)
print(f"✅ Wrote {out_path}")

# 3) Check for any stray FULLY_CONNECTED strings
ops = subprocess.check_output(
    ["strings", out_path, "|", "grep", "FULLY_CONNECTED"], 
    shell=True, text=True
).strip()
print("FULLY_CONNECTED present?", ops or "— none —")

# 4) Test loading it
try:
    interpreter = tflite.Interpreter(model_path=out_path)
    interpreter.allocate_tensors()
    print("✅ TFLite BUILTINS‑only model loaded successfully!")
except Exception as e:
    print("❌ Failed to load TFLite model:", e)

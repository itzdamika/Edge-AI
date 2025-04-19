# convert_and_test.py
import tensorflow as tf
from tensorflow.keras.models import load_model
import tflite_runtime.interpreter as tflite

# 1) Load your trained Keras model
model = load_model(
    "models/prediction_model_temp.h5",
    custom_objects={'mse': tf.keras.losses.MeanSquaredError()}
)
print("✅ Keras .h5 loaded")

# 2) Convert to TFLite using ONLY BUILTIN OPS
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

# 3) Overwrite the file your backend uses
out_path = "models/temperature_model_new.tflite"
with open(out_path, "wb") as f:
    f.write(tflite_model)
print(f"✅ Wrote {out_path}")

# 4) Double‑check no FULLY_CONNECTED v12 is present
import subprocess
ops = subprocess.check_output(
    ["strings", out_path, "|", "grep", "FULLY_CONNECTED"], 
    shell=True, text=True
).strip()
print("FULLY_CONNECTED found in flatbuffer?" , ops or "— none —")

# 5) Test loading it with tflite_runtime
try:
    interpreter = tflite.Interpreter(model_path=out_path)
    interpreter.allocate_tensors()
    print("✅ TFLite BUILTINS‑only model loaded successfully!")
except Exception as e:
    print("❌ Failed to load TFLite model:", e)

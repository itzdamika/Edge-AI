import tensorflow as tf
import numpy as np

# Create a minimal TFLite model
model = tf.keras.Sequential([
    tf.keras.layers.Flatten(input_shape=(5, 1)),
    tf.keras.layers.Dense(5)
])
model.compile(optimizer='adam', loss='mse')
model.save("test_model.h5")

# Convert to TFLite (BUILTINS only)
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
tflite_model = converter.convert()

with open("test_model.tflite", "wb") as f:
    f.write(tflite_model)

# Test loading it
interpreter = tf.lite.Interpreter(model_path="test_model.tflite")
interpreter.allocate_tensors()
print("✅ Minimal model loaded successfully.")

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, Dropout, Flatten, Dense, Reshape
from tensorflow.keras.callbacks import EarlyStopping
import tensorflow as tf
import os

df = pd.read_csv("hourly_interpolated_data.csv", parse_dates=["timestamp"])
temps = df["temperature_celsius"].values.reshape(-1, 1)

scaler = MinMaxScaler()
scaled = scaler.fit_transform(temps)

LOOKBACK, FORWARD = 5, 5
X, y = [], []
for i in range(len(scaled) - LOOKBACK - FORWARD + 1):
    X.append(scaled[i : i + LOOKBACK])
    y.append(scaled[i + LOOKBACK : i + LOOKBACK + FORWARD])
X = np.array(X)
y = np.array(y).reshape(-1, FORWARD, 1)

split = int(0.8 * len(X))
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

model = Sequential([
    Conv1D(32, kernel_size=2, activation="relu", input_shape=(LOOKBACK, 1)),
    Dropout(0.2),
    Flatten(),
    Dense(64, activation="relu"),
    Dense(FORWARD),
    Reshape((FORWARD, 1))
])
model.compile(optimizer="adam", loss="mse", metrics=["mae"])
model.summary()

es = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
model.fit(
    X_train, y_train,
    validation_data=(X_test, y_test),
    epochs=50,
    batch_size=32,
    callbacks=[es]
)

os.makedirs("models", exist_ok=True)
model.save("models/prediction_model_temp.h5")
print("✅ Saved Keras model to models/prediction_model_temp.h5")

converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

tflite_path = "models/temperature_model_pi.tflite"
with open(tflite_path, "wb") as f:
    f.write(tflite_model)
print(f"✅ Wrote TFLite model to {tflite_path}")

import subprocess
ops = subprocess.run(
    ["strings", tflite_path, "|", "grep", "FULLY_CONNECTED"],
    shell=True, capture_output=True, text=True
).stdout.strip()
print("FULLY_CONNECTED present?", ops or "— none —")

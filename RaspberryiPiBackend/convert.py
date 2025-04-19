# train_and_export.py

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, Dropout, Flatten, Dense, Reshape
from tensorflow.keras.callbacks import EarlyStopping
import tensorflow as tf
import os

# 1) Load your hourly data
df = pd.read_csv("hourly_interpolated_data.csv", parse_dates=["timestamp"])
temps = df["temperature_celsius"].values.reshape(-1, 1)

# 2) Scale to [0,1]
scaler = MinMaxScaler()
scaled = scaler.fit_transform(temps)

# 3) Build sliding windows: last 5 → next 5
LOOKBACK, FORWARD = 5, 5
X, y = [], []
for i in range(len(scaled) - LOOKBACK - FORWARD + 1):
    X.append(scaled[i : i + LOOKBACK])
    y.append(scaled[i + LOOKBACK : i + LOOKBACK + FORWARD])
X = np.array(X)            # shape (samples, 5, 1)
y = np.array(y).reshape(-1, FORWARD, 1)  # shape (samples, 5, 1)

# 4) Split 80/20
split = int(0.8 * len(X))
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

# 5) Define a Conv1D → Dense model (no LSTM!)
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

# 6) Train with early stopping
es = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
model.fit(
    X_train, y_train,
    validation_data=(X_test, y_test),
    epochs=50,
    batch_size=32,
    callbacks=[es]
)

# 7) Save Keras .h5
os.makedirs("models", exist_ok=True)
model.save("models/prediction_model_temp.h5")
print("✅ Saved Keras model to models/prediction_model_temp.h5")

# 8) Convert to TFLite using only BUILTIN ops (Pi‑compatible!)
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

tflite_path = "models/temperature_model_pi.tflite"
with open(tflite_path, "wb") as f:
    f.write(tflite_model)
print(f"✅ Wrote TFLite model to {tflite_path}")

# 9) (Optional) Quick check: no unsupported FULLY_CONNECTED v12 ops
import subprocess
ops = subprocess.run(
    ["strings", tflite_path, "|", "grep", "FULLY_CONNECTED"],
    shell=True, capture_output=True, text=True
).stdout.strip()
print("FULLY_CONNECTED present?", ops or "— none —")

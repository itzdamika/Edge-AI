import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

df = pd.read_csv("D:\EDGE AI\Edge-AI-1\Data\cleaned_telemetry_data.csv")

# Select only numerical columns for training
features = ["temp", "humidity", "co", "lpg", "smoke"]
data = df[features].values

# Normalize data using MinMaxScaler
scaler = MinMaxScaler()
data_scaled = scaler.fit_transform(data)

# Creating sequences
def create_sequences(data, time_steps=10):
    X, y = [], []
    for i in range(len(data) - time_steps):
        X.append(data[i:i+time_steps])
        y.append(data[i+time_steps][0])
    return np.array(X), np.array(y)

# Define time steps
TIME_STEPS = 10
X, y = create_sequences(data_scaled, TIME_STEPS)

# Splitting testing and training sets
split = int(0.8 * len(X))
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

# Implementing Architecture
model = Sequential([
    LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
    Dropout(0.2),
    LSTM(units=50, return_sequences=False),
    Dropout(0.2),
    Dense(units=25),
    Dense(units=1)
])

model.compile(optimizer="adam", loss="mean_squared_error")
model.summary()

model.fit(X_train, y_train, epochs=10, batch_size=32)

model.save("lstm_model.h5")

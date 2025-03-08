import pandas as pd
from sklearn.preprocessing import MinMaxScaler

df = pd.read_csv("iot_telemetry_data.csv")

# Check for missing values
print(df.isnull().sum())

# Fill or drop missing values
df = df.dropna()

# Convert timestamp column
df["ts"] = pd.to_datetime(df["ts"])
df = df.set_index("ts")

# Select only numerical columns for training
features = ["temp", "humidity", "co", "lpg", "smoke"]
data = df[features].values

# Normalize data using MinMaxScaler
scaler = MinMaxScaler()
data_scaled = scaler.fit_transform(data)

# Save the cleaned data to a new file
df[features] = data_scaled
df.to_csv("cleaned_telemetry_data.csv")

print(df.head())

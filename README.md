# SmartAura: Edge-to-Cloud Smart Home Automation

SmartAura is a comprehensive smart-home platform that integrates local edge intelligence on a Raspberry Pi with a React-based dashboard and Azure cloud services. It provides real-time environment monitoring, voice and face-recognition security, automated climate & lighting control, scheduling, predictive analytics, and full telemetry to Azure IoT Central.

---

## 📖 Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)

---

## 🌟 Features

### Raspberry Pi (Edge Device)
- **Local Sensor Monitoring**: Temperature, humidity, air quality, motion (10 s polling).
- **Face-Recognition Security**: MTCNN + Resnet embeddings to allow only known faces; alerts on unknown.
- **Occupancy & Comfort Automation**: Nighttime lighting (6 PM–6 AM), climate control based on temperature bands (> 28 °C, 24–28 °C, ≤ 24 °C).
- **Voice Assistant**: Wake-word (“hello assistant”), Azure-based intent classification, and local command execution.
- **Hourly Logging & Model Retraining**: Logs temperature each hour, retrains forecasting model at midnight on-device.
- **Live MJPEG Stream**: Serves camera feed over HTTP.
- **One-Off Scheduling**: Schedule AC & fan on/off at arbitrary times.
- **Local OLED & LED Indicators**: Onboard status display and red/green alerts.

### Edge Dashboard (React)
- **Authentication**: Admin/Guest roles via username/password.
- **Real-Time Monitoring**: Live cards for temperature, humidity, air quality.
- **Manual Controls**: Toggle light, AC, fan; adjust AC temp (16–32 °C) and fan speed (1–3).
- **One-Off Scheduling UI**: Select future start/end times with date pickers.
- **Temperature Forecast Chart**: Next-5-hour prediction via Chart.js.
- **Live Camera Embed**: One-click view of the MJPEG feed.
- **Logs & Downloads**: View and download system and voice logs as JSON.

### Azure Cloud
- **Azure IoT Central**: Telemetry ingestion and cloud dashboard.
- **Azure IoT Hub**: Secure device provisioning & messaging.
- **Azure OpenAI**: Intent classification & conversational responses.
- **Azure Cognitive Services**: Speech-to-text and text-to-speech.

---

## 🏗 Architecture

1. **Raspberry Pi Edge** runs FastAPI for sensors, control, scheduling, ML training & inference.
2. **React Dashboard** communicates via HTTP to the Pi and optionally views Azure IoT Central.
3. **Azure Cloud** receives telemetry through IoT Hub into IoT Central; provides LLM and speech services.

---

## 🔧 Prerequisites

- **Hardware**: Raspberry Pi 4 (or later), DHT22, air-quality sensor, PIR motion sensor, LEDs, SSD1306 OLED, webcam.
- **Software**:
  - Python 3.10+
  - Node.js 16+
  - Docker (optional for local React hosting)

---


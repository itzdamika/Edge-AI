/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-unused-vars */
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useAuthStore } from '../store/authStore';
import {
  Sun,
  Fan,
  Snowflake,
  MessageSquare,
  AlertTriangle,
  LogOut,
  Camera,
  Thermometer,
  Droplets,
  Wind,
  X,
  Download
} from 'lucide-react';
import toast from 'react-hot-toast';
import type { SensorData } from '../types';

// For the forecast chart
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title as ChartTitle,
  Tooltip,
  Legend
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ChartTitle,
  Tooltip,
  Legend
);

export default function Dashboard() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  const [showCamera, setShowCamera] = useState(false);
  const [liveSensors, setLiveSensors] = useState<SensorData | null>(null);

  // States for lights
  const [kitchenLight, setKitchenLight] = useState(false);
  const [livingRoomAc, setLivingRoomAc] = useState(false);
  const [bedroomFan, setBedroomFan] = useState(false);

  // States for AC Temperature and Fan Speed
  const [acTemp, setAcTemp] = useState<number>(24);
  const [fanSpeed, setFanSpeed] = useState<number>(1);

  // Logs
  const [systemLogs, setSystemLogs] = useState<any[]>([]);
  const [voiceLogs, setVoiceLogs] = useState<any[]>([]);

  // NEW: Forecast data
  const [forecastData, setForecastData] = useState<number[]>([]);

  // Poll sensor data
  useEffect(() => {
    const fetchLiveData = async () => {
      try {
        const res = await fetch("http://192.168.1.13:8000/sensors");
        const data = await res.json();
        setLiveSensors({
          temperature: data.temperature,
          humidity: data.humidity,
          airQuality: data.air_quality,
        });
      } catch (error) {
        console.error("Error fetching sensor data", error);
      }
    };
    fetchLiveData();
    const interval = setInterval(fetchLiveData, 5000);
    return () => clearInterval(interval);
  }, []);

  // Poll lights state
  useEffect(() => {
    const fetchLights = async () => {
      try {
        const res = await fetch("http://192.168.1.13:8000/lights");
        const data = await res.json();
        setKitchenLight(data.kitchen === "on");
        setLivingRoomAc(data.livingroom === "on");
        setBedroomFan(data.bedroom === "on");
        setAcTemp(data.ac_temp);
        setFanSpeed(data.fan_speed);
      } catch (error) {
        console.error("Error fetching lights state", error);
      }
    };
    fetchLights();
    const interval = setInterval(fetchLights, 3000); 
    return () => clearInterval(interval);
  }, []);

  // Poll system logs
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await fetch("http://192.168.1.13:8000/logs");
        const data = await res.json();
        setSystemLogs(data);
      } catch (error) {
        console.error("Error fetching logs", error);
      }
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  // Poll voice logs
  useEffect(() => {
    const fetchVoiceLogs = async () => {
      try {
        const res = await fetch("http://192.168.1.13:8000/voicelogs");
        const data = await res.json();
        setVoiceLogs(data);
      } catch (error) {
        console.error("Error fetching voice logs", error);
      }
    };
    fetchVoiceLogs();
    const interval = setInterval(fetchVoiceLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  // Poll forecast data
  useEffect(() => {
    const fetchForecast = async () => {
      try {
        const res = await fetch("http://192.168.1.13:8000/forecast");
        const data = await res.json();
        // data.forecast => array of 5 predicted temps
        setForecastData(data.forecast);
      } catch (error) {
        console.error("Error fetching forecast data", error);
      }
    };
    fetchForecast();
    const interval = setInterval(fetchForecast, 3600000); // fetch once an hour
    return () => clearInterval(interval);
  }, []);

  // Toggle function
  const toggleLight = async (light: string) => {
    let newState: boolean;
    let endpoint = "";
    if (light === "kitchen") {
      newState = !kitchenLight;
      endpoint = `http://192.168.1.13:8000/light/kitchen?state=${newState ? "on" : "off"}`;
    } else if (light === "livingroom") {
      newState = !livingRoomAc;
      endpoint = `http://192.168.1.13:8000/light/livingroom?state=${newState ? "on" : "off"}`;
    } else if (light === "bedroom") {
      newState = !bedroomFan;
      endpoint = `http://192.168.1.13:8000/light/bedroom?state=${newState ? "on" : "off"}`;
    } else {
      return;
    }
    try {
      const res = await fetch(endpoint);
      if (res.ok) {
        if (light === "kitchen") setKitchenLight(newState);
        else if (light === "livingroom") setLivingRoomAc(newState);
        else if (light === "bedroom") setBedroomFan(newState);
        if (light === "kitchen") toast.success(`Light toggled!`);
        else if (light === "livingroom") toast.success(`AC toggled!`);
        else if (light === "bedroom") toast.success(`Fan toggled!`);
      } else {
        if (light === "kitchen") toast.error(`Failed to control Light!`);
        else if (light === "livingroom") toast.error(`Failed to control AC!`);
        else if (light === "bedroom") toast.error(`Failed to control Fan!`);
      }
    } catch (error) {
      if (light === "kitchen") toast.error(`Error controlling Light!`);
      else if (light === "livingroom") toast.error(`Error controlling AC!`);
      else if (light === "bedroom") toast.error(`Error controlling Fan!`);
    }
  };

  // Download logs
  const downloadSystemLogs = async () => {
    try {
      const res = await fetch("http://192.168.1.13:8000/logs");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'system_logs.json';
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading system logs", error);
    }
  };

  const downloadVoiceLogs = async () => {
    try {
      const res = await fetch("http://192.168.1.13:8000/voicelogs");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'voice_logs.json';
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading voice logs", error);
    }
  };

  // Prepare chart data for forecast (5 points)
  const forecastChartData = {
    labels: ["+1h", "+2h", "+3h", "+4h", "+5h"],
    datasets: [
      {
        label: "Forecast (°C)",
        data: forecastData.map((temp) => Number(temp.toFixed(2))),
        borderColor: "rgba(75,192,192,1)",
        backgroundColor: "rgba(75,192,192,0.1)",
        tension: 0.3
      }
    ]
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-gray-300 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <header className="flex justify-between items-center mb-8">
          <motion.h1 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="text-3xl font-bold text-white"
          >
            SmartAura Dashboard
          </motion.h1>
          <div className="flex items-center gap-4">
            <span className="text-white">{user?.role}</span>
            <motion.button
              whileHover={{ scale: 1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => logout()}
              className="p-2 hover:bg-[#1F1F1F] rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5 text-red-400" />
            </motion.button>
          </div>
        </header>

        {/* Sensor Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[
            { icon: Thermometer, label: 'Room Temperature', value: `${liveSensors?.temperature ?? 0}°C`, color: 'text-orange-400' },
            { icon: Droplets, label: 'Humidity', value: `${liveSensors?.humidity ?? 0}%`, color: 'text-blue-400' },
            { icon: Wind, label: 'Air Quality', value: liveSensors?.airQuality ?? 'N/A', color: 'text-purple-400' }
          ].map((sensor, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
            >
              <div className="flex items-center gap-3">
                <sensor.icon className={`w-6 h-6 ${sensor.color}`} />
                <h3 className="text-lg font-semibold text-white">{sensor.label}</h3>
              </div>
              <p className="text-3xl font-bold mt-2">{sensor.value}</p>
            </motion.div>
          ))}
        </div>

        {/* Device Control Toggles */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Kitchen Light */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3">
              <Sun className="w-6 h-6 text-yellow-400" />
              <h3 className="text-lg font-semibold text-white">Main Light</h3>
            </div>
            <motion.button
              whileHover={{ scale: 1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => toggleLight("kitchen")}
              className={`text-3xl font-bold mt-2 w-full py-2 rounded-lg transition-colors ${
                kitchenLight
                  ? 'bg-[#4ADE80] text-[#0A0A0A] hover:bg-[#22C55E]'
                  : 'bg-[#1F1F1F] hover:bg-[#2D2D2D]'
              }`}
            >
              {kitchenLight ? "ON" : "OFF"}
            </motion.button>
          </motion.div>

          {/* Living Room AC */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3">
              <Snowflake className="w-6 h-6 text-cyan-400" />
              <h3 className="text-lg font-semibold text-white">Living Room AC</h3>
            </div>
            <motion.button
              whileHover={{ scale: 1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => toggleLight("livingroom")}
              className={`text-3xl font-bold mt-2 w-full py-2 rounded-lg transition-colors ${
                livingRoomAc
                  ? 'bg-[#4ADE80] text-[#0A0A0A] hover:bg-[#22C55E]'
                  : 'bg-[#1F1F1F] hover:bg-[#2D2D2D]'
              }`}
            >
              {livingRoomAc ? "ON" : "OFF"}
            </motion.button>
          </motion.div>

          {/* Bedroom Fan */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3">
              <Fan className="w-6 h-6 text-blue-400" />
              <h3 className="text-lg font-semibold text-white">Main Fan</h3>
            </div>
            <motion.button
              whileHover={{ scale: 1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => toggleLight("bedroom")}
              className={`text-3xl font-bold mt-2 w-full py-2 rounded-lg transition-colors ${
                bedroomFan
                  ? 'bg-[#4ADE80] text-[#0A0A0A] hover:bg-[#22C55E]'
                  : 'bg-[#1F1F1F] hover:bg-[#2D2D2D]'
              }`}
            >
              {bedroomFan ? "ON" : "OFF"}
            </motion.button>
          </motion.div>
        </div>

        {/* AC Temp & Fan Speed Sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* AC Temp Control */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3">
              <Thermometer className="w-6 h-6 text-orange-400" />
              <h3 className="text-lg font-semibold text-white">AC Temperature</h3>
            </div>
            <div className="mt-4 flex items-center">
              <input
                type="range"
                min="16"
                max="32"
                value={acTemp}
                onChange={e => setAcTemp(Number(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
              <span className="ml-4 text-white">{acTemp}°C</span>
            </div>
            <button
              onClick={async () => {
                try {
                  const res = await fetch(`http://192.168.1.13:8000/ac/temp?value=${acTemp}`);
                  if (res.ok) {
                    toast.success("AC temperature updated");
                  } else {
                    toast.error("Failed to update AC temperature");
                  }
                } catch (error) {
                  toast.error("Error updating AC temperature");
                }
              }}
              className="mt-2 bg-blue-500 px-4 py-2 rounded"
            >
              Set Temperature
            </button>
          </motion.div>

          {/* Fan Speed Control */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3">
              <Fan className="w-6 h-6 text-blue-400" />
              <h3 className="text-lg font-semibold text-white">Fan Speed</h3>
            </div>
            <div className="mt-4 flex items-center">
              <input
                type="range"
                min="1"
                max="3"
                value={fanSpeed}
                onChange={e => setFanSpeed(Number(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
              <span className="ml-4 text-white">Lvl {fanSpeed}</span>
            </div>
            <button
              onClick={async () => {
                try {
                  const res = await fetch(`http://192.168.1.13:8000/fan/speed?level=${fanSpeed}`);
                  if (res.ok) {
                    toast.success("Fan speed updated");
                  } else {
                    toast.error("Failed to update fan speed");
                  }
                } catch (error) {
                  toast.error("Error updating fan speed");
                }
              }}
              className="mt-2 bg-blue-500 px-4 py-2 rounded"
            >
              Set Speed
            </button>
          </motion.div>
        </div>

        {/* Forecast Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
        >
          <h3 className="text-lg font-semibold text-white mb-4">Next 5 Hours Forecast</h3>
          <div className="h-64">
            <Line
              data={forecastChartData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    display: true,
                  },
                },
                scales: {
                  y: {
                    title: {
                      display: true,
                      text: "°C",
                    },
                  },
                  x: {
                    title: {
                      display: true,
                      text: "Hours Ahead",
                    },
                  },
                },
              }}
            />
          </div>
        </motion.div>

        {/* Camera + System Logs */}
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Camera */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F] relative"
          >
            <div className="flex items-center gap-3 mb-4">
              <Camera className="w-6 h-6 text-pink-400" />
              <h2 className="text-xl font-semibold text-white">Security Camera</h2>
            </div>
            {!showCamera ? (
              <motion.button
                whileHover={{ scale: 1 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setShowCamera(true)}
                className="w-full py-20 flex items-center justify-center border-2 border-dashed border-[#1F1F1F] rounded-lg hover:border-pink-400 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Camera className="w-5 h-5 text-pink-400" />
                  Click to view live camera
                </span>
              </motion.button>
            ) : (
              <div className="relative">
                <motion.button
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  whileHover={{ scale: 1 }}
                  whileTap={{ scale: 0.9 }}
                  className="absolute top-2 right-2 p-2 bg-[#0A0A0A]/50 rounded-full hover:bg-[#0A0A0A]/70 transition-colors"
                  onClick={() => setShowCamera(false)}
                >
                  <X className="w-4 h-4" />
                </motion.button>
                <img
                  src="http://192.168.1.13:8000/video_feed"
                  alt="Live Camera Feed"
                  className="w-full rounded-lg"
                />
              </div>
            )}
          </motion.div>

          {/* System Logs + Download */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3 mb-4 justify-between">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-6 h-6 text-amber-400" />
                <h2 className="text-xl font-semibold text-white">System Logs</h2>
              </div>
              <button
                onClick={downloadSystemLogs}
                className="text-sm text-blue-500 hover:underline"
              >
                <Download/>
              </button>
            </div>
            <div className="space-y-4 max-h-48 overflow-y-auto pr-2">
              {systemLogs.map((log, i) => (
                <div key={i} className="text-sm">
                  <span className="text-gray-500 mr-2">
                    {new Date(log.timestamp * 1000).toLocaleTimeString()}
                  </span>
                  {log.message}
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Voice Logs + Download */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
        >
          <div className="flex items-center gap-3 mb-4 justify-between">
            <div className="flex items-center gap-3">
              <MessageSquare className="w-6 h-6 text-indigo-400" />
              <h2 className="text-xl font-semibold text-white">Voice Assistant</h2>
            </div>
            <button
              onClick={downloadVoiceLogs}
              className="text-sm text-blue-500 hover:underline"
            >
              <Download/>
            </button>
          </div>
          <div className="space-y-4 max-h-80 overflow-y-auto pr-2">
            {voiceLogs.map((log, i) => (
              <div key={i} className="text-sm">
                <div>
                  <span className="text-pink-400">User:</span> {log.user}
                </div>
                <div>
                  <span className="text-green-400">Assistant:</span> {log.assistant}
                </div>
                <hr className="my-1 border-gray-600" />
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

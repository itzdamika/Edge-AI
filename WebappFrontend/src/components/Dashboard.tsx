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
  X
} from 'lucide-react';
import toast from 'react-hot-toast';
import type { SensorData } from '../types';

export default function Dashboard() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  const [showCamera, setShowCamera] = useState(false);
  const [liveSensors, setLiveSensors] = useState<SensorData | null>(null);

  // local states for lights
  const [kitchenLight, setKitchenLight] = useState(false);
  const [livingRoomAc, setLivingRoomAc] = useState(false);
  const [bedroomFan, setBedroomFan] = useState(false);

  // logs
  const [systemLogs, setSystemLogs] = useState<any[]>([]);
  const [voiceLogs, setVoiceLogs] = useState<any[]>([]);

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

  // Poll light states
  useEffect(() => {
    const fetchLights = async () => {
      try {
        const res = await fetch("http://192.168.1.13:8000/lights");
        const data = await res.json();
        // data = { kitchen: "on"/"off", livingroom: "on"/"off", bedroom: "on"/"off" }
        setKitchenLight(data.kitchen === "on");
        setLivingRoomAc(data.livingroom === "on");
        setBedroomFan(data.bedroom === "on");
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

  // toggle function remains same
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
        // no need to manually set states, we do though for immediate UI
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

  // fallback for sensors
  const sensorValues = liveSensors || {
    temperature: 0,
    humidity: 0,
    airQuality: 0
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
            <span className="text-white">
              {user?.role}
            </span>
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
            { icon: Thermometer, label: 'Room Temperature', value: `${sensorValues.temperature}°C`, color: 'text-orange-400' },
            { icon: Droplets, label: 'Humidity', value: `${sensorValues.humidity}%`, color: 'text-blue-400' },
            { icon: Wind, label: 'Air Quality', value: sensorValues.airQuality, color: 'text-purple-400' }
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

        {/* Our minimal toggles for kitchen, livingroom, bedroom */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
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

        {/* The rest is same as your code... e.g. security camera, logs, voice assistant messages */}
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

          {/* System Logs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              <h2 className="text-xl font-semibold text-white">System Logs</h2>
            </div>
            <div className="space-y-4 max-h-48 overflow-y-auto pr-2">
              {systemLogs.map((log, i) => (
                <div key={i} className="text-sm">
                  <span className="text-gray-500 mr-2">
                    {new Date(log.timestamp*1000).toLocaleTimeString()}
                  </span>
                  {log.message}
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
        >
          <div className="flex items-center gap-3 mb-4">
            <MessageSquare className="w-6 h-6 text-indigo-400" />
            <h2 className="text-xl font-semibold text-white">Voice Assistant</h2>
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

/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useDeviceStore } from '../store/deviceStore';
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
  Power,
  Zap
} from 'lucide-react';
import toast from 'react-hot-toast';
import type { SensorData } from '../types';

const sensorData: SensorData = {
  temperature: 23,
  humidity: 45,
  airQuality: 92,
};

export default function Dashboard() {
  const { devices, fetchDevices, updateDevice } = useDeviceStore();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const [showCamera, setShowCamera] = useState(false);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  const handleDeviceToggle = async (deviceId: string, currentStatus: boolean) => {
    if (user?.role !== 'admin') {
      toast.error('Only admins can control devices');
      return;
    }
    
    try {
      await updateDevice(deviceId, { status: !currentStatus });
      toast.success('Device updated successfully');
    } catch (error) {
      toast.error('Failed to update device');
    }
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
              {user?.role.charAt(0).toUpperCase() + user?.role.slice(1)}
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

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[
            { icon: Thermometer, label: 'Room Temperature', value: `${sensorData.temperature}°C`, color: 'text-orange-400' },
            { icon: Droplets, label: 'Humidity', value: `${sensorData.humidity}%`, color: 'text-blue-400' },
            { icon: Wind, label: 'Air Quality', value: `${sensorData.airQuality}%`, color: 'text-purple-400' }
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

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {devices.map((device) => (
            <motion.div
              key={device.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
            >
              <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-3">
                  {device.type === 'light' && <Sun className="w-6 h-6 text-yellow-400" />}
                  {device.type === 'fan' && <Fan className="w-6 h-6 text-blue-400" />}
                  {device.type === 'ac' && <Snowflake className="w-6 h-6 text-cyan-400" />}
                  <h2 className="text-xl font-semibold text-white">{device.name}</h2>
                </div>
                <motion.button
                  whileHover={{ scale: 1 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => handleDeviceToggle(device.id, device.status)}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    device.status 
                      ? 'bg-[#4ADE80] text-[#0A0A0A] hover:bg-[#22C55E]' 
                      : 'bg-[#1F1F1F] hover:bg-[#2D2D2D]'
                  }`}
                >
                  {device.status ? 'ON' : 'OFF'}
                </motion.button>
              </div>

              {device.type === 'ac' && (
                <div className="mt-4">
                  <label className="block text-sm mb-2">Temperature</label>
                  <input
                    type="range"
                    min="16"
                    max="30"
                    value={device.temperature}
                    onChange={(e) => 
                      user?.role === 'admin' && 
                      updateDevice(device.id, { temperature: parseInt(e.target.value) })
                    }
                    disabled={user?.role !== 'admin'}
                    className="w-full accent-cyan-400"
                  />
                  <span className="text-lg">{device.temperature}°C</span>
                </div>
              )}

              {device.type === 'fan' && (
                <div className="mt-4">
                  <label className="block text-sm mb-2">Speed</label>
                  <div className="flex gap-2">
                    {[1, 2, 3].map((speed) => (
                      <motion.button
                        key={speed}
                        whileHover={{ scale: 1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={() => 
                          user?.role === 'admin' && 
                          updateDevice(device.id, { speed })
                        }
                        disabled={user?.role !== 'admin'}
                        className={`flex-1 py-2 rounded transition-colors ${
                          device.speed === speed 
                            ? 'bg-blue-400 text-[#0A0A0A] hover:bg-blue-500' 
                            : 'bg-[#1F1F1F] hover:bg-[#2D2D2D]'
                        }`}
                      >
                        {speed}
                      </motion.button>
                    ))}
                  </div>
                </div>
              )}

              {device.type === 'light' && (
                <div className="mt-4 grid grid-cols-2 gap-4">
                  <div className="flex items-center gap-2 p-3 bg-[#1F1F1F] rounded-lg">
                    <Power className="w-5 h-5 text-yellow-400" />
                    <span>Power: {device.status ? 'Active' : 'Inactive'}</span>
                  </div>
                  <div className="flex items-center gap-2 p-3 bg-[#1F1F1F] rounded-lg">
                    <Zap className="w-5 h-5 text-yellow-400" />
                    <span>Status: {device.status ? 'Illuminated' : 'Dark'}</span>
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </div>

        <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                  src="http://raspberrypi.local:8000/video_feed"
                  alt="Live Camera Feed"
                  className="w-full rounded-lg"
                />
              </div>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#141414] p-6 rounded-xl border border-[#1F1F1F]"
          >
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              <h2 className="text-xl font-semibold text-white">System Logs</h2>
            </div>
            <div className="space-y-4 max-h-80 overflow-y-auto pr-2">
              {/* System logs would be mapped here */}
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
            {/* Voice assistant messages would be mapped here */}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
/* eslint-disable @typescript-eslint/no-unused-vars */
import { create } from 'zustand';
import { Device } from '../types';
import axios from 'axios';

interface DeviceState {
  devices: Device[];
  updateDevice: (deviceId: string, updates: Partial<Device>) => Promise<void>;
  fetchDevices: () => Promise<void>;
}

export const useDeviceStore = create<DeviceState>((set) => ({
  devices: [],
  updateDevice: async (deviceId, updates) => {
    try {
      await axios.put(`http://localhost:8000/devices/${deviceId}`, updates);
      set((state) => ({
        devices: state.devices.map((device) =>
          device.id === deviceId ? { ...device, ...updates } : device
        ),
      }));
    } catch (error) {
      throw new Error('Failed to update device');
    }
  },
  fetchDevices: async () => {
    try {
      const response = await axios.get('http://localhost:8000/devices');
      set({ devices: response.data });
    } catch (error) {
      throw new Error('Failed to fetch devices');
    }
  },
}));
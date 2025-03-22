/* eslint-disable @typescript-eslint/no-unused-vars */
import { create } from 'zustand';
import { User } from '../types';
import axios from 'axios';

interface AuthState {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  login: async (username, password) => {
    try {
      const response = await axios.post('http://localhost:8000/login', {
        username,
        password,
      });
      set({ user: response.data });
    } catch (error) {
      throw new Error('Invalid credentials');
    }
  },
  logout: () => set({ user: null }),
}));
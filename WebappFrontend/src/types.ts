export interface User {
  id: string;
  username: string;
  password: string;
  role: 'admin' | 'guest';
}

export interface Device {
  id: string;
  name: string;
  type: 'ac' | 'fan' | 'light';
  status: boolean;
  temperature?: number;
  speed?: 1 | 2 | 3;
}

export interface SensorData {
  temperature: number;
  humidity: number;
  airQuality: number;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'device' | 'security' | 'assistant';
}

export interface AssistantMessage {
  id: string;
  timestamp: string;
  query: string;
  response: string;
}
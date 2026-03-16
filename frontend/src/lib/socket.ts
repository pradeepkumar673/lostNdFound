// src/lib/socket.ts
import { io, Socket } from 'socket.io-client';

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || 'http://localhost:5000';

let socket: Socket | null = null;

export const getSocket = (): Socket => {
  if (!socket) {
    const token = localStorage.getItem('clf_token');
    socket = io(SOCKET_URL, {
      auth: { token },
      transports: ['websocket', 'polling'],
      autoConnect: false,
    });
  }
  return socket;
};

export const connectSocket = () => {
  const s = getSocket();
  if (!s.connected) s.connect();
  return s;
};

export const disconnectSocket = () => {
  if (socket?.connected) {
    socket.disconnect();
    socket = null;
  }
};

export type SocketEvents = {
  // Real-time item events
  'item:new': (item: unknown) => void;
  'item:updated': (item: unknown) => void;
  // Match events
  'match:found': (match: unknown) => void;
  // Chat events
  'message:new': (message: unknown) => void;
  'message:read': (data: { room_id: string; user_id: string }) => void;
  'user:typing': (data: { room_id: string; user: unknown }) => void;
  'user:stop-typing': (data: { room_id: string; user_id: string }) => void;
  // Notification events
  'notification:new': (notification: unknown) => void;
  // Room events
  'room:joined': (data: { room_id: string }) => void;
};

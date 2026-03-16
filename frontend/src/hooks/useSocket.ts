// src/hooks/useSocket.ts
import { useEffect, useCallback } from 'react';
import { getSocket } from '@/lib/socket';

type EventHandler = (data: unknown) => void;

export function useSocketEvent(event: string, handler: EventHandler) {
  useEffect(() => {
    const socket = getSocket();
    socket.on(event, handler);
    return () => { socket.off(event, handler); };
  }, [event, handler]);
}

export function useSocketEmit() {
  return useCallback((event: string, data?: unknown) => {
    const socket = getSocket();
    socket.emit(event, data);
  }, []);
}

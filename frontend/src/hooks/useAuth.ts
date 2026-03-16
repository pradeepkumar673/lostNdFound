// src/hooks/useAuth.ts
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/api';
import { useStore } from '@/store';

export function useAuthSync() {
  const { token, setAuth, clearAuth } = useStore();

  const { data, error } = useQuery({
    queryKey: ['me'],
    queryFn: authApi.me,
    enabled: !!token,
    retry: false,
    staleTime: 1000 * 60 * 5,
  });

  useEffect(() => {
    if (data && token) {
      setAuth(data, token);
    }
  }, [data, token, setAuth]);

  useEffect(() => {
    if (error) clearAuth();
  }, [error, clearAuth]);

  return { user: data };
}

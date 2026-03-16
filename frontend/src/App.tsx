// src/App.tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { useEffect } from 'react';
import { useStore } from '@/store';
import { connectSocket, disconnectSocket, getSocket } from '@/lib/socket';
import { queryClient } from '@/lib/queryClient';
import { useAuthSync } from '@/hooks/useAuth';
import { showNotificationToast } from '@/components/notifications/NotificationToast';
import type { Notification } from '@/types';

// Layouts
import AppLayout from '@/components/common/AppLayout';
import AuthLayout from '@/components/common/AuthLayout';

// Pages
import LandingPage from '@/pages/LandingPage';
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import DashboardPage from '@/pages/DashboardPage';
import ItemsPage from '@/pages/ItemsPage';
import NewItemPage from '@/pages/NewItemPage';
import ItemDetailPage from '@/pages/ItemDetailPage';
import MatchesPage from '@/pages/MatchesPage';
import ChatPage from '@/pages/ChatPage';
import NotificationsPage from '@/pages/NotificationsPage';
import HeatmapPage from '@/pages/HeatmapPage';
import ProfilePage from '@/pages/ProfilePage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useStore((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { token, addNotification, setUnreadCount } = useStore();
  useAuthSync();

  useEffect(() => {
    if (!token) return;

    const socket = connectSocket();

    socket.on('notification:new', (notif) => {
      addNotification(notif as Notification);
      showNotificationToast(notif as Notification);
    });

    socket.on('match:found', () => {
      queryClient.invalidateQueries({ queryKey: ['matches'] });
    });

    socket.on('item:updated', () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
    });

    return () => {
      socket.off('notification:new');
      socket.off('match:found');
      socket.off('item:updated');
      disconnectSocket();
    };
  }, [token, addNotification, setUnreadCount]);

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'hsl(222, 47%, 12%)',
            border: '1px solid hsl(222, 47%, 20%)',
            color: 'hsl(210, 40%, 96%)',
            borderRadius: '12px',
            fontSize: '14px',
          },
        }}
        richColors
      />

      <Routes>
        {/* Public */}
        <Route path="/" element={<LandingPage />} />
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        {/* Protected */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/items" element={<ItemsPage />} />
          <Route path="/items/new" element={<NewItemPage />} />
          <Route path="/items/:id" element={<ItemDetailPage />} />
          <Route path="/matches" element={<MatchesPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:roomId" element={<ChatPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/heatmap" element={<HeatmapPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

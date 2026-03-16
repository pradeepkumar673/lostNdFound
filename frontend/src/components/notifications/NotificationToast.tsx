// src/components/notifications/NotificationToast.tsx
import { toast } from 'sonner';
import type { Notification } from '@/types';

const ICONS: Record<string, string> = {
  match_found: '🎯',
  claim_received: '📦',
  claim_approved: '✅',
  item_resolved: '🎉',
  message: '💬',
  badge_earned: '🏆',
};

export function showNotificationToast(notif: Notification) {
  const icon = ICONS[notif.type] ?? '🔔';

  toast(notif.title, {
    description: notif.body,
    icon: <span className="text-lg">{icon}</span>,
    action: notif.data?.item_id
      ? {
          label: 'View →',
          onClick: () => window.location.href = `/items/${notif.data?.item_id}`,
        }
      : undefined,
    duration: 5000,
  });
}

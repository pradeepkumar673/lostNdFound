// src/pages/NotificationsPage.tsx
import { useQuery, useMutation } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Bell, Check, GitMerge, MessageCircle, Award, Package, ArrowRight } from 'lucide-react';
import { notificationsApi } from '@/lib/api';
import { useStore } from '@/store';
import { queryClient } from '@/lib/queryClient';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { Notification } from '@/types';

const NOTIF_CONFIG: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  match_found: { icon: GitMerge, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  claim_received: { icon: Package, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  claim_approved: { icon: Check, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  item_resolved: { icon: Check, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  message: { icon: MessageCircle, color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
  badge_earned: { icon: Award, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
};

function NotifCard({ notif }: { notif: Notification }) {
  const { markRead } = useStore();
  const config = NOTIF_CONFIG[notif.type] ?? { icon: Bell, color: 'text-muted-foreground', bg: 'bg-secondary' };
  const Icon = config.icon;

  const { mutate: mark } = useMutation({
    mutationFn: () => notificationsApi.markRead(notif.id),
    onSuccess: () => {
      markRead(notif.id);
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'glass rounded-2xl p-4 border transition-all flex items-start gap-4',
        notif.read ? 'border-border/30 opacity-70' : 'border-emerald-500/10 bg-emerald-500/3'
      )}
    >
      <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', config.bg)}>
        <Icon className={cn('w-5 h-5', config.color)} />
      </div>

      <div className="flex-1 min-w-0">
        <p className="font-semibold text-foreground text-sm">{notif.title}</p>
        <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">{notif.body}</p>
        <div className="flex items-center gap-3 mt-2">
          <span className="text-xs text-muted-foreground">{formatRelativeTime(notif.created_at)}</span>
          {notif.data?.item_id && (
            <Link
              to={`/items/${notif.data.item_id}`}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
            >
              View <ArrowRight className="w-3 h-3" />
            </Link>
          )}
        </div>
      </div>

      {!notif.read && (
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <button
            onClick={() => mark()}
            className="text-xs text-muted-foreground hover:text-foreground p-1.5 rounded-lg hover:bg-white/5 transition-all"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </motion.div>
  );
}

export default function NotificationsPage() {
  const { markAllRead } = useStore();

  const { data, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list(),
  });

  const { mutate: markAll } = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      markAllRead();
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const notifications = data?.items ?? [];
  const unread = notifications.filter((n) => !n.read).length;

  return (
    <div className="p-6 md:p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display font-bold text-2xl text-foreground flex items-center gap-2">
            <Bell className="w-6 h-6 text-emerald-400" /> Notifications
          </h1>
          {unread > 0 && (
            <p className="text-sm text-muted-foreground mt-1">{unread} unread</p>
          )}
        </div>
        {unread > 0 && (
          <button
            onClick={() => markAll()}
            className="text-sm text-emerald-400 hover:text-emerald-300 font-medium px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 transition-all"
          >
            Mark all read
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-20 rounded-2xl" />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 glass rounded-3xl border border-dashed border-border">
          <Bell className="w-12 h-12 text-muted-foreground/30 mb-3" />
          <h3 className="font-semibold text-foreground mb-1">No notifications</h3>
          <p className="text-muted-foreground text-sm">You're all caught up!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => <NotifCard key={n.id} notif={n} />)}
        </div>
      )}
    </div>
  );
}

// src/components/common/NotificationBell.tsx
import { Bell } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '@/store';

export default function NotificationBell() {
  const unreadCount = useStore((s) => s.unreadCount);

  return (
    <Link
      to="/notifications"
      className="relative p-2 rounded-xl hover:bg-white/5 text-muted-foreground hover:text-foreground transition-all"
    >
      <Bell className="w-5 h-5" />
      <AnimatePresence>
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center text-[10px] font-bold text-white shadow-emerald-sm"
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  );
}

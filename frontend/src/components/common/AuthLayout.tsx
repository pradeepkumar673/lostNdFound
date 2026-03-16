// src/components/common/AuthLayout.tsx
import { Outlet, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

export default function AuthLayout() {
  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-background">
      {/* Animated background orbs */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl animate-pulse-glow" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-indigo-500/8 rounded-full blur-3xl animate-pulse-glow animation-delay-1000" />
        <div className="absolute top-3/4 left-1/2 w-64 h-64 bg-emerald-400/5 rounded-full blur-2xl animate-float" />
      </div>

      {/* Logo top-left */}
      <Link to="/" className="absolute top-6 left-6 flex items-center gap-2.5 z-10">
        <div className="w-9 h-9 rounded-xl bg-emerald-500 flex items-center justify-center shadow-emerald-sm">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <span className="font-display font-bold text-foreground hidden sm:block">CampusLostFound</span>
      </Link>

      {/* Form card */}
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md mx-4 relative z-10"
      >
        <div className="glass rounded-3xl p-8">
          <Outlet />
        </div>
      </motion.div>
    </div>
  );
}

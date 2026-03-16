// src/pages/LandingPage.tsx
import { Link } from 'react-router-dom';
import { motion, useScroll, useTransform } from 'framer-motion';
import { useRef, useEffect, useState } from 'react';
import { ArrowRight, Search, PlusCircle, Sparkles, MapPin, Clock, Zap, Shield, Heart } from 'lucide-react';
import { statsApi } from '@/lib/api';

const floatingItems = [
  { emoji: '🎒', label: 'Backpack', x: '8%', y: '20%', delay: 0 },
  { emoji: '💻', label: 'Laptop', x: '88%', y: '15%', delay: 0.3 },
  { emoji: '📱', label: 'Phone', x: '5%', y: '65%', delay: 0.6 },
  { emoji: '🔑', label: 'Keys', x: '92%', y: '60%', delay: 0.9 },
  { emoji: '📚', label: 'Books', x: '15%', y: '80%', delay: 1.2 },
  { emoji: '⌚', label: 'Watch', x: '80%', y: '78%', delay: 1.5 },
  { emoji: '💳', label: 'Card', x: '50%', y: '8%', delay: 0.4 },
];

const features = [
  {
    icon: Sparkles,
    title: 'AI-Powered Matching',
    desc: 'Gemini + CLIP vision AI finds visual matches across lost and found items automatically.',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
  },
  {
    icon: Zap,
    title: 'Instant Notifications',
    desc: 'Get real-time alerts the moment a match is found for any of your items.',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
  },
  {
    icon: Shield,
    title: 'Verified Campus Users',
    desc: 'Only verified students and faculty. Safe, trusted, secure campus network.',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
  },
  {
    icon: Heart,
    title: 'Earn & Give Back',
    desc: 'Earn points and badges for returning found items. Build your campus karma.',
    color: 'text-pink-400',
    bg: 'bg-pink-500/10',
  },
];

function AnimatedCounter({ target, duration = 2000 }: { target: number; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef(false);

  useEffect(() => {
    if (ref.current) return;
    ref.current = true;
    const start = Date.now();
    const timer = setInterval(() => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));
      if (progress >= 1) clearInterval(timer);
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);

  return <span>{count.toLocaleString()}</span>;
}

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ['start start', 'end start'] });
  const heroY = useTransform(scrollYProgress, [0, 1], ['0%', '30%']);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0]);
  const [stats, setStats] = useState({ items_found_today: 47, matches_today: 23, total_items: 1204 });

  useEffect(() => {
    statsApi.global().then(setStats).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">
      {/* Navbar */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 md:px-12 h-16">
        <div className="glass rounded-2xl px-4 py-2 flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-emerald-500 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-display font-bold text-sm">CampusLostFound</span>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/login" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors px-4 py-2">
            Sign in
          </Link>
          <Link to="/register" className="btn-emerald text-sm py-2 px-5">
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section ref={heroRef} className="relative min-h-screen flex items-center justify-center overflow-hidden pt-16">
        {/* Background gradient */}
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-hero-gradient" />
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] bg-emerald-500/8 rounded-full blur-[100px]" />
        </div>

        {/* Floating items */}
        {floatingItems.map((item, i) => (
          <motion.div
            key={i}
            className="absolute hidden md:flex flex-col items-center gap-1 pointer-events-none"
            style={{ left: item.x, top: item.y }}
            initial={{ opacity: 0, scale: 0 }}
            animate={{
              opacity: [0.4, 0.7, 0.4],
              scale: 1,
              y: [0, -12, 0],
            }}
            transition={{
              opacity: { duration: 3, repeat: Infinity, delay: item.delay },
              scale: { duration: 0.5, delay: item.delay + 0.5 },
              y: { duration: 4 + i * 0.5, repeat: Infinity, ease: 'easeInOut', delay: item.delay },
            }}
          >
            <div className="glass w-12 h-12 rounded-2xl flex items-center justify-center text-2xl shadow-glass">
              {item.emoji}
            </div>
          </motion.div>
        ))}

        {/* Hero content */}
        <motion.div style={{ y: heroY, opacity: heroOpacity }} className="relative z-10 text-center px-6 max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 text-sm font-medium text-emerald-400 mb-8 border border-emerald-500/20"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI-Powered Campus Recovery</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 100 }}
            className="font-display font-bold text-5xl md:text-7xl text-foreground leading-tight tracking-tight mb-6"
          >
            Find what you lost.{' '}
            <span className="gradient-text">Return what</span>
            <br />you found.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed"
          >
            Campus's smartest lost &amp; found platform. AI matches your lost items with found ones
            in real time. Never lose anything for good.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link to="/items" className="btn-emerald flex items-center gap-2.5 text-base px-8 py-4">
              <Search className="w-5 h-5" />
              Browse Items
            </Link>
            <Link
              to="/register"
              className="glass flex items-center gap-2.5 text-base font-semibold px-8 py-4 rounded-2xl hover:bg-white/8 transition-all border border-white/10 text-foreground"
            >
              <PlusCircle className="w-5 h-5 text-emerald-400" />
              Post Now
              <ArrowRight className="w-4 h-4" />
            </Link>
          </motion.div>

          {/* Live stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="flex items-center justify-center gap-8 mt-16"
          >
            {[
              { label: 'Items found today', value: stats.items_found_today, suffix: '' },
              { label: 'AI matches made', value: stats.matches_today, suffix: '' },
              { label: 'Total items listed', value: stats.total_items, suffix: '+' },
            ].map((stat, i) => (
              <div key={i} className="text-center">
                <div className="font-display font-bold text-2xl md:text-3xl text-foreground">
                  <AnimatedCounter target={stat.value} />
                  {stat.suffix}
                </div>
                <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 text-muted-foreground/50"
        >
          <div className="w-5 h-8 rounded-full border-2 border-current flex items-start justify-center p-1">
            <div className="w-1 h-2 bg-current rounded-full animate-bounce" />
          </div>
        </motion.div>
      </section>

      {/* Features section */}
      <section className="py-24 px-6 md:px-12 max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-display font-bold text-3xl md:text-5xl text-foreground mb-4">
            Smart recovery, <span className="gradient-text">powered by AI</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Every lost item has a chance to be found. Our AI works 24/7 to connect lost and found items.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="glass rounded-3xl p-8 border border-white/5 hover:border-emerald-500/15 transition-all card-hover"
            >
              <div className={`w-12 h-12 ${f.bg} rounded-2xl flex items-center justify-center mb-5`}>
                <f.icon className={`w-6 h-6 ${f.color}`} />
              </div>
              <h3 className="font-display font-bold text-xl text-foreground mb-3">{f.title}</h3>
              <p className="text-muted-foreground leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 text-center relative">
        <div className="absolute inset-0 bg-emerald-glow pointer-events-none" />
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="max-w-2xl mx-auto relative z-10"
        >
          <h2 className="font-display font-bold text-3xl md:text-5xl text-foreground mb-6">
            Start recovering items today
          </h2>
          <p className="text-muted-foreground text-lg mb-10">
            Join thousands of students who've already recovered their belongings.
          </p>
          <Link to="/register" className="btn-emerald inline-flex items-center gap-2 text-lg px-10 py-4">
            <Sparkles className="w-5 h-5" />
            Get Started Free
            <ArrowRight className="w-5 h-5" />
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/30 py-8 px-6 text-center text-muted-foreground text-sm">
        <div className="flex items-center justify-center gap-2 mb-2">
          <div className="w-6 h-6 rounded-lg bg-emerald-500 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-semibold text-foreground">CampusLostFound</span>
        </div>
        <p>Built with ❤️ for campuses everywhere. Powered by Gemini AI + CLIP vision.</p>
      </footer>
    </div>
  );
}

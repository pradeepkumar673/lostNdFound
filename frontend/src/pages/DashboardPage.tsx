// src/pages/DashboardPage.tsx
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { PlusCircle, TrendingUp, Search, GitMerge, CheckCircle, Package, Star, Bell } from 'lucide-react';
import { useStore } from '@/store';
import { itemsApi, matchesApi, statsApi } from '@/lib/api';
import { formatRelativeTime, getInitials } from '@/lib/utils';
import { Skeleton } from '@/components/ui/Skeleton';
import ItemCard from '@/components/item/ItemCard';
import { useEffect } from 'react';
import { getSocket } from '@/lib/socket';
import { launchConfetti } from '@/utils/confetti';

function StatCard({ icon: Icon, label, value, color, delay }: {
  icon: React.ElementType; label: string; value: number | string;
  color: string; delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: 'spring', stiffness: 200 }}
      className="glass rounded-2xl p-5 border border-white/5"
    >
      <div className={`w-10 h-10 ${color} rounded-xl flex items-center justify-center mb-3`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="font-display font-bold text-2xl text-foreground">{value}</div>
      <div className="text-sm text-muted-foreground mt-0.5">{label}</div>
    </motion.div>
  );
}

export default function DashboardPage() {
  const user = useStore((s) => s.user);

  const { data: myItems, isLoading: itemsLoading } = useQuery({
    queryKey: ['my-items'],
    queryFn: itemsApi.myItems,
  });

  const { data: matches } = useQuery({
    queryKey: ['matches'],
    queryFn: matchesApi.list,
  });

  const { data: stats } = useQuery({
    queryKey: ['global-stats'],
    queryFn: statsApi.global,
  });

  // Fire confetti when a new match arrives
  useEffect(() => {
    const socket = getSocket();
    const handler = () => launchConfetti(2500);
    socket.on('match:found', handler);
    return () => { socket.off('match:found', handler); };
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = user?.name?.split(' ')[0] || 'there';

  const lostCount = myItems?.filter((i) => i.type === 'lost').length ?? 0;
  const foundCount = myItems?.filter((i) => i.type === 'found').length ?? 0;
  const resolvedCount = myItems?.filter((i) => i.status === 'resolved').length ?? 0;
  const matchCount = matches?.length ?? 0;

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* Hero greeting */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between gap-4 flex-wrap"
      >
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center overflow-hidden">
            {user?.avatar_url ? (
              <img src={user.avatar_url} className="w-full h-full object-cover" />
            ) : (
              <span className="font-display font-bold text-lg text-emerald-400">{getInitials(user?.name || 'U')}</span>
            )}
          </div>
          <div>
            <p className="text-muted-foreground text-sm">{greeting},</p>
            <h1 className="font-display font-bold text-2xl text-foreground">{firstName} 👋</h1>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Points badge */}
          <div className="glass px-4 py-2 rounded-xl border border-yellow-500/20 flex items-center gap-2">
            <Star className="w-4 h-4 text-yellow-400" />
            <span className="font-semibold text-yellow-400 text-sm">{user?.points ?? 0} pts</span>
          </div>
          <Link to="/items/new" className="btn-emerald flex items-center gap-2 text-sm py-2.5">
            <PlusCircle className="w-4 h-4" />
            Post Item
          </Link>
        </div>
      </motion.div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Search} label="Items lost" value={lostCount} color="bg-red-500/15 text-red-400" delay={0.05} />
        <StatCard icon={Package} label="Items found" value={foundCount} color="bg-emerald-500/15 text-emerald-400" delay={0.1} />
        <StatCard icon={GitMerge} label="AI matches" value={matchCount} color="bg-indigo-500/15 text-indigo-400" delay={0.15} />
        <StatCard icon={CheckCircle} label="Resolved" value={resolvedCount} color="bg-blue-500/15 text-blue-400" delay={0.2} />
      </div>

      {/* Global stats banner */}
      {stats && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="glass rounded-2xl p-5 border border-emerald-500/10 bg-emerald-500/5"
        >
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-semibold text-emerald-400">Campus Activity Today</span>
          </div>
          <div className="flex items-center gap-6 flex-wrap">
            <div className="text-sm text-muted-foreground">
              <span className="font-bold text-foreground text-lg">{stats.items_found_today}</span> items found
            </div>
            <div className="text-sm text-muted-foreground">
              <span className="font-bold text-foreground text-lg">{stats.matches_today}</span> new matches
            </div>
            <div className="text-sm text-muted-foreground">
              <span className="font-bold text-foreground text-lg">{stats.total_items}</span> total items
            </div>
          </div>
        </motion.div>
      )}

      {/* Badges */}
      {user?.badges && user.badges.length > 0 && (
        <div>
          <h2 className="font-display font-semibold text-lg text-foreground mb-4">Your Badges</h2>
          <div className="flex items-center gap-3 flex-wrap">
            {user.badges.map((badge) => (
              <motion.div
                key={badge.id}
                whileHover={{ scale: 1.05 }}
                className="glass px-4 py-2.5 rounded-xl border border-white/10 flex items-center gap-2"
                title={badge.description}
              >
                <span className="text-xl">{badge.icon}</span>
                <div>
                  <p className="text-sm font-semibold text-foreground">{badge.name}</p>
                  <p className="text-xs text-muted-foreground">{formatRelativeTime(badge.earned_at)}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Recent matches */}
      {matches && matches.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display font-semibold text-lg text-foreground flex items-center gap-2">
              <Bell className="w-5 h-5 text-emerald-400" />
              AI Matches Found
            </h2>
            <Link to="/matches" className="text-sm text-emerald-400 hover:text-emerald-300 font-medium">View all →</Link>
          </div>
          <div className="space-y-3">
            {matches.slice(0, 3).map((match) => (
              <motion.div
                key={match.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="glass rounded-2xl p-4 border border-emerald-500/10 flex items-center gap-4"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <img
                    src={match.lost_item.images[0] || ''}
                    className="w-12 h-12 rounded-xl object-cover bg-secondary/50 flex-shrink-0"
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground truncate">{match.lost_item.title}</p>
                    <p className="text-xs text-muted-foreground">matched with "{match.found_item.title}"</p>
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <span className="match-badge">{Math.round(match.similarity_score * 100)}%</span>
                </div>
                <Link
                  to={`/items/${match.lost_item.id}`}
                  className="flex-shrink-0 text-xs font-semibold text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 px-3 py-1.5 rounded-lg transition-colors"
                >
                  View →
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* My recent items */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-lg text-foreground">My Recent Items</h2>
          <Link to="/items" className="text-sm text-emerald-400 hover:text-emerald-300 font-medium">Browse all →</Link>
        </div>
        {itemsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="glass rounded-2xl overflow-hidden">
                <Skeleton className="h-40 rounded-none" />
                <div className="p-4 space-y-2">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : myItems && myItems.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {myItems.slice(0, 6).map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <div className="glass rounded-2xl p-12 text-center border border-dashed border-border">
            <div className="text-5xl mb-4">🔍</div>
            <h3 className="font-semibold text-foreground mb-2">No items yet</h3>
            <p className="text-muted-foreground text-sm mb-6">Post your first lost or found item</p>
            <Link to="/items/new" className="btn-emerald inline-flex items-center gap-2 text-sm">
              <PlusCircle className="w-4 h-4" /> Post Now
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

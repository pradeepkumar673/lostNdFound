// src/components/item/ItemCard.tsx
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { MapPin, Clock, Eye, MessageCircle, Zap } from 'lucide-react';
import { cn, formatRelativeTime, getMatchBg, getMatchColor, PLACEHOLDER_IMAGE } from '@/lib/utils';
import type { Item } from '@/types';
import { CATEGORIES } from '@/types';

interface ItemCardProps {
  item: Item;
  style?: React.CSSProperties;
}

export default function ItemCard({ item, style }: ItemCardProps) {
  const category = CATEGORIES.find((c) => c.id === item.category);
  const topMatch = item.match_count > 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -4 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      style={style}
      className="group"
    >
      <Link to={`/items/${item.id}`}>
        <div className="glass rounded-2xl overflow-hidden border border-white/5 hover:border-emerald-500/20 transition-all duration-300 hover:shadow-card-hover">
          {/* Image */}
          <div className="relative overflow-hidden bg-secondary/50" style={{ aspectRatio: '4/3' }}>
            <img
              src={item.images[0] || PLACEHOLDER_IMAGE}
              alt={item.title}
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
              loading="lazy"
            />
            {/* Image shine effect */}
            <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

            {/* Badges overlay */}
            <div className="absolute top-3 left-3 flex items-center gap-2">
              <span className={cn(
                'text-xs font-bold px-2.5 py-1 rounded-lg backdrop-blur-sm',
                item.type === 'lost' ? 'badge-lost' : 'badge-found'
              )}>
                {item.type === 'lost' ? '🔍 Lost' : '✅ Found'}
              </span>
            </div>

            {/* Match badge */}
            {topMatch && (
              <div className="absolute top-3 right-3">
                <span className="match-badge flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  {item.match_count} match{item.match_count > 1 ? 'es' : ''}
                </span>
              </div>
            )}

            {/* Status overlay for non-active */}
            {item.status !== 'active' && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center backdrop-blur-sm">
                <span className={cn(
                  'text-sm font-bold px-4 py-2 rounded-xl border',
                  item.status === 'resolved' ? 'badge-resolved' : 'badge-claimed'
                )}>
                  {item.status === 'resolved' ? '✓ Resolved' : '⏳ Claimed'}
                </span>
              </div>
            )}
          </div>

          {/* Content */}
          <div className="p-4">
            {/* Category + color */}
            <div className="flex items-center gap-2 mb-2">
              {category && (
                <span className="text-xs font-medium text-muted-foreground bg-secondary/50 px-2 py-0.5 rounded-lg flex items-center gap-1">
                  <span>{category.icon}</span>
                  <span>{category.label}</span>
                </span>
              )}
              {item.color && (
                <span className="text-xs text-muted-foreground capitalize">{item.color}</span>
              )}
            </div>

            {/* Title */}
            <h3 className="font-semibold text-foreground text-sm leading-tight mb-2 line-clamp-2 group-hover:text-emerald-400 transition-colors">
              {item.title}
            </h3>

            {/* Meta */}
            <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3">
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                <span className="truncate max-w-[120px]">{item.campus_zone}</span>
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatRelativeTime(item.created_at)}
              </span>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all duration-200 translate-y-1 group-hover:translate-y-0">
              <button className="flex-1 flex items-center justify-center gap-1.5 bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 text-xs font-semibold py-2 rounded-xl transition-all border border-emerald-500/20">
                <Eye className="w-3.5 h-3.5" />
                View
              </button>
              <button className="flex-1 flex items-center justify-center gap-1.5 bg-secondary/50 text-muted-foreground hover:text-foreground text-xs font-semibold py-2 rounded-xl transition-all border border-border">
                <MessageCircle className="w-3.5 h-3.5" />
                Chat
              </button>
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

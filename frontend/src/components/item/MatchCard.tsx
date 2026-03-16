// src/components/item/MatchCard.tsx
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Zap } from 'lucide-react';
import { cn, getMatchBg, getMatchColor } from '@/lib/utils';
import type { Match } from '@/types';

interface MatchCardProps {
  match: Match;
  highlightItemId?: string;
}

export default function MatchCard({ match, highlightItemId }: MatchCardProps) {
  const score = Math.round(match.similarity_score * 100);
  const other = match.lost_item.id === highlightItemId ? match.found_item : match.lost_item;

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -2 }}
      className="glass rounded-2xl overflow-hidden border border-white/5 hover:border-emerald-500/20 transition-all w-44 flex-shrink-0 cursor-pointer"
    >
      <Link to={`/items/${other.id}`}>
        <div className="relative h-28 overflow-hidden bg-secondary/30">
          {other.images[0] && (
            <img src={other.images[0]} alt={other.title} className="w-full h-full object-cover" />
          )}
          <div className={cn(
            'absolute top-2 right-2 text-xs font-bold px-2 py-0.5 rounded-lg border flex items-center gap-1',
            getMatchBg(score), getMatchColor(score)
          )}>
            <Zap className="w-3 h-3" />
            {score}%
          </div>
        </div>
        <div className="p-3">
          <p className="text-xs font-semibold text-foreground truncate">{other.title}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">{other.campus_zone}</p>
        </div>
      </Link>
    </motion.div>
  );
}

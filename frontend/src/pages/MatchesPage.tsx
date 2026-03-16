// src/pages/MatchesPage.tsx
import { useQuery, useMutation } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { GitMerge, Zap, Check, X, ChevronRight } from 'lucide-react';
import { matchesApi } from '@/lib/api';
import { queryClient } from '@/lib/queryClient';
import { cn, formatRelativeTime, getMatchBg, getMatchColor } from '@/lib/utils';
import { Skeleton } from '@/components/ui/Skeleton';
import { toast } from 'sonner';

export default function MatchesPage() {
  const { data: matches = [], isLoading } = useQuery({
    queryKey: ['matches'],
    queryFn: matchesApi.list,
  });

  const { mutate: confirm } = useMutation({
    mutationFn: matchesApi.confirm,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['matches'] }); toast.success('Match confirmed!'); },
  });
  const { mutate: reject } = useMutation({
    mutationFn: matchesApi.reject,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['matches'] }); toast.success('Match dismissed'); },
  });

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="font-display font-bold text-2xl text-foreground flex items-center gap-2">
          <GitMerge className="w-6 h-6 text-emerald-400" /> AI Matches
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Items our AI thinks could be yours — sorted by confidence
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-40 rounded-2xl" />)}
        </div>
      ) : matches.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-center glass rounded-3xl p-12 border border-dashed border-border">
          <div className="text-5xl mb-4">🔍</div>
          <h3 className="font-semibold text-foreground text-xl mb-2">No matches yet</h3>
          <p className="text-muted-foreground text-sm">Post items and our AI will find matches automatically</p>
          <Link to="/items/new" className="btn-emerald mt-6 text-sm inline-flex items-center gap-2">
            Post an item
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          <AnimatePresence>
            {matches.map((match, i) => {
              const score = Math.round(match.similarity_score * 100);
              return (
                <motion.div
                  key={match.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -100 }}
                  transition={{ delay: i * 0.05 }}
                  className="glass rounded-2xl border border-white/5 overflow-hidden hover:border-emerald-500/15 transition-all"
                >
                  <div className="p-5 flex items-center gap-4 flex-wrap">
                    {/* Lost item */}
                    <Link to={`/items/${match.lost_item.id}`} className="flex items-center gap-3 flex-1 min-w-0 group">
                      <div className="w-16 h-16 rounded-xl overflow-hidden bg-secondary/50 flex-shrink-0">
                        <img src={match.lost_item.images[0] || ''} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                      </div>
                      <div className="min-w-0">
                        <span className="badge-lost text-[10px] mb-1 inline-block">Lost</span>
                        <p className="font-semibold text-foreground text-sm truncate">{match.lost_item.title}</p>
                        <p className="text-xs text-muted-foreground">{match.lost_item.campus_zone}</p>
                      </div>
                    </Link>

                    {/* Match score */}
                    <div className="flex flex-col items-center flex-shrink-0 gap-1">
                      <div className={cn('w-14 h-14 rounded-2xl flex flex-col items-center justify-center border', getMatchBg(score))}>
                        <Zap className={cn('w-4 h-4 mb-0.5', getMatchColor(score))} />
                        <span className={cn('text-sm font-bold leading-none', getMatchColor(score))}>{score}%</span>
                      </div>
                      <span className="text-[10px] text-muted-foreground">match</span>
                    </div>

                    {/* Found item */}
                    <Link to={`/items/${match.found_item.id}`} className="flex items-center gap-3 flex-1 min-w-0 group">
                      <div className="w-16 h-16 rounded-xl overflow-hidden bg-secondary/50 flex-shrink-0">
                        <img src={match.found_item.images[0] || ''} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                      </div>
                      <div className="min-w-0">
                        <span className="badge-found text-[10px] mb-1 inline-block">Found</span>
                        <p className="font-semibold text-foreground text-sm truncate">{match.found_item.title}</p>
                        <p className="text-xs text-muted-foreground">{match.found_item.campus_zone}</p>
                      </div>
                    </Link>

                    {/* Actions */}
                    {match.status === 'pending' && (
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={() => confirm(match.id)}
                          className="p-2.5 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/25 transition-all"
                          title="Confirm match"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => reject(match.id)}
                          className="p-2.5 rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all"
                          title="Dismiss"
                        >
                          <X className="w-4 h-4" />
                        </button>
                        <Link
                          to={`/items/${match.lost_item.id}`}
                          className="p-2.5 rounded-xl bg-secondary text-muted-foreground border border-border hover:text-foreground transition-all"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Link>
                      </div>
                    )}
                    {match.status !== 'pending' && (
                      <span className={cn(
                        'text-xs font-semibold px-3 py-1.5 rounded-lg border flex-shrink-0',
                        match.status === 'confirmed' ? 'badge-found' : 'badge-lost'
                      )}>
                        {match.status}
                      </span>
                    )}
                  </div>

                  {/* Match reasons */}
                  {match.match_reasons?.length > 0 && (
                    <div className="px-5 pb-4 border-t border-border/20 pt-3 flex flex-wrap gap-2">
                      {match.match_reasons.map((r, i) => (
                        <span key={i} className="text-xs px-2.5 py-1 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
                          {r}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="px-5 pb-3 text-xs text-muted-foreground">
                    Match found {formatRelativeTime(match.created_at)}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

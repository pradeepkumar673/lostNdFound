// src/pages/ItemDetailPage.tsx
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MapPin, Clock, Tag, ChevronLeft, ChevronRight,
  MessageCircle, CheckCircle, Trash2, Zap, Sparkles,
  User, Share2, Eye, GitMerge
} from 'lucide-react';
import { toast } from 'sonner';
import { itemsApi, chatApi } from '@/lib/api';
import { useStore } from '@/store';
import { CATEGORIES } from '@/types';
import { cn, formatRelativeTime, getInitials, getMatchBg, getMatchColor } from '@/lib/utils';
import { queryClient } from '@/lib/queryClient';
import ChatPanel from '@/components/chat/ChatPanel';
import { Skeleton } from '@/components/ui/Skeleton';

export default function ItemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentUser = useStore((s) => s.user);
  const [imgIdx, setImgIdx] = useState(0);
  const [showChat, setShowChat] = useState(false);
  const [chatRoomId, setChatRoomId] = useState<string | null>(null);
  const [claimMsg, setClaimMsg] = useState('');
  const [showClaimBox, setShowClaimBox] = useState(false);

  const { data: item, isLoading } = useQuery({
    queryKey: ['item', id],
    queryFn: () => itemsApi.get(id!),
    enabled: !!id,
  });

  const { data: matches } = useQuery({
    queryKey: ['item-matches', id],
    queryFn: () => itemsApi.getMatches(id!),
    enabled: !!id,
  });

  const { mutate: resolve } = useMutation({
    mutationFn: () => itemsApi.markResolved(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['item', id] });
      toast.success('Item marked as resolved! 🎉');
    },
  });

  const { mutate: deleteItem } = useMutation({
    mutationFn: () => itemsApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      toast.success('Item deleted');
      navigate('/items');
    },
  });

  const { mutate: claim, isPending: claiming } = useMutation({
    mutationFn: () => itemsApi.claimItem(id!, claimMsg),
    onSuccess: () => {
      toast.success('Claim submitted!');
      setShowClaimBox(false);
    },
  });

  const handleStartChat = async () => {
    if (!item) return;
    try {
      const room = await chatApi.createRoom(item.id, item.owner.id);
      setChatRoomId(room.id);
      setShowChat(true);
    } catch {
      toast.error('Could not start chat');
    }
  };

  const isOwner = item?.owner.id === currentUser?.id;
  const category = item ? CATEGORIES.find((c) => c.id === item.category) : null;

  if (isLoading) {
    return (
      <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
        <Skeleton className="h-80 rounded-3xl" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    );
  }

  if (!item) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <div className="text-5xl mb-4">😶</div>
        <h3 className="font-semibold text-foreground">Item not found</h3>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 max-w-4xl">
        {/* Back button */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        {/* Image carousel */}
        <div className="relative rounded-3xl overflow-hidden bg-secondary/30 mb-8" style={{ aspectRatio: '16/9' }}>
          <AnimatePresence mode="wait">
            <motion.img
              key={imgIdx}
              src={item.images[imgIdx] || ''}
              alt={item.title}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="w-full h-full object-cover"
            />
          </AnimatePresence>

          {item.images.length > 1 && (
            <>
              <button
                onClick={() => setImgIdx((i) => (i - 1 + item.images.length) % item.images.length)}
                className="absolute left-3 top-1/2 -translate-y-1/2 glass p-2 rounded-xl text-white"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <button
                onClick={() => setImgIdx((i) => (i + 1) % item.images.length)}
                className="absolute right-3 top-1/2 -translate-y-1/2 glass p-2 rounded-xl text-white"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
              <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5">
                {item.images.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setImgIdx(i)}
                    className={cn('w-2 h-2 rounded-full transition-all', i === imgIdx ? 'bg-white w-5' : 'bg-white/50')}
                  />
                ))}
              </div>
            </>
          )}

          {/* Status badge */}
          <div className="absolute top-4 left-4 flex gap-2">
            <span className={item.type === 'lost' ? 'badge-lost' : 'badge-found'}>
              {item.type === 'lost' ? '🔍 Lost' : '✅ Found'}
            </span>
            {item.status !== 'active' && (
              <span className={item.status === 'resolved' ? 'badge-resolved' : 'badge-claimed'}>
                {item.status}
              </span>
            )}
          </div>
        </div>

        {/* Thumbnail strip */}
        {item.images.length > 1 && (
          <div className="flex gap-2 mb-6">
            {item.images.map((src, i) => (
              <button key={i} onClick={() => setImgIdx(i)} className={cn('w-16 h-16 rounded-xl overflow-hidden border-2 transition-all', i === imgIdx ? 'border-emerald-500' : 'border-transparent')}>
                <img src={src} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}

        {/* Title + Meta */}
        <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
          <div>
            <h1 className="font-display font-bold text-2xl md:text-3xl text-foreground mb-2">{item.title}</h1>
            <div className="flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
              {category && (
                <span className="flex items-center gap-1.5 bg-secondary/50 px-3 py-1 rounded-lg">
                  <span>{category.icon}</span> {category.label}
                </span>
              )}
              <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4 text-emerald-400" />{item.campus_zone}</span>
              <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" />{formatRelativeTime(item.created_at)}</span>
              <span className="flex items-center gap-1.5"><Eye className="w-4 h-4" />{item.view_count} views</span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            <button className="glass p-2.5 rounded-xl border border-border text-muted-foreground hover:text-foreground transition-all">
              <Share2 className="w-4 h-4" />
            </button>
            {!isOwner && item.status === 'active' && (
              <>
                <button
                  onClick={() => setShowClaimBox(!showClaimBox)}
                  className="px-4 py-2.5 rounded-xl bg-yellow-500/15 text-yellow-400 border border-yellow-500/20 text-sm font-semibold hover:bg-yellow-500/25 transition-all"
                >
                  Claim Item
                </button>
                <button
                  onClick={handleStartChat}
                  className="btn-emerald flex items-center gap-2 text-sm py-2.5"
                >
                  <MessageCircle className="w-4 h-4" /> Chat
                </button>
              </>
            )}
            {isOwner && (
              <>
                {item.status === 'active' && (
                  <button
                    onClick={() => resolve()}
                    className="px-4 py-2.5 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 text-sm font-semibold flex items-center gap-2 hover:bg-emerald-500/25 transition-all"
                  >
                    <CheckCircle className="w-4 h-4" /> Mark Resolved
                  </button>
                )}
                <button
                  onClick={() => { if (confirm('Delete this item?')) deleteItem(); }}
                  className="px-4 py-2.5 rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 text-sm font-semibold flex items-center gap-2 hover:bg-red-500/20 transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>

        {/* Claim box */}
        <AnimatePresence>
          {showClaimBox && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="glass rounded-2xl p-4 border border-yellow-500/20 mb-6"
            >
              <h4 className="font-semibold text-foreground mb-2">Claim this item</h4>
              <textarea
                value={claimMsg}
                onChange={(e) => setClaimMsg(e.target.value)}
                placeholder="Describe why this is yours (serial number, photos, distinctive features)..."
                className="input-base resize-none mb-3"
                rows={2}
              />
              <div className="flex gap-2">
                <button onClick={() => claim()} disabled={claiming || !claimMsg.trim()} className="btn-emerald text-sm py-2 disabled:opacity-60">
                  {claiming ? 'Submitting...' : 'Submit Claim'}
                </button>
                <button onClick={() => setShowClaimBox(false)} className="text-sm px-4 py-2 rounded-xl border border-border text-muted-foreground hover:text-foreground transition-all">
                  Cancel
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Description */}
        {item.description && (
          <div className="glass rounded-2xl p-5 border border-white/5 mb-6">
            <h3 className="font-semibold text-foreground mb-2">Description</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">{item.description}</p>
          </div>
        )}

        {/* Details */}
        <div className="glass rounded-2xl p-5 border border-white/5 mb-6 grid grid-cols-2 sm:grid-cols-3 gap-4">
          {item.color && (
            <div><div className="text-xs text-muted-foreground mb-1">Color</div><div className="text-sm font-medium text-foreground capitalize">{item.color}</div></div>
          )}
          {item.brand && (
            <div><div className="text-xs text-muted-foreground mb-1">Brand</div><div className="text-sm font-medium text-foreground">{item.brand}</div></div>
          )}
          {item.tags.length > 0 && (
            <div className="col-span-2 sm:col-span-3">
              <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1"><Tag className="w-3 h-3" /> Tags</div>
              <div className="flex flex-wrap gap-1.5">
                {item.tags.map((t) => (
                  <span key={t} className="text-xs px-2.5 py-1 bg-secondary rounded-lg text-muted-foreground border border-border">#{t}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* AI Analysis */}
        {item.ai_analysis && (
          <details className="glass rounded-2xl border border-emerald-500/10 mb-6 overflow-hidden group">
            <summary className="p-5 flex items-center gap-2 cursor-pointer list-none">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <span className="font-semibold text-foreground text-sm">AI Analysis</span>
              <span className="ml-auto text-xs text-muted-foreground group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div className="px-5 pb-5 border-t border-border/30 pt-4 space-y-2">
              <p className="text-sm text-muted-foreground">{item.ai_analysis.gemini_summary}</p>
              {item.ai_analysis.features?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {item.ai_analysis.features.map((f) => (
                    <span key={f} className="text-xs px-2.5 py-1 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">{f}</span>
                  ))}
                </div>
              )}
            </div>
          </details>
        )}

        {/* Matches */}
        {matches && matches.length > 0 && (
          <div className="mb-6">
            <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
              <GitMerge className="w-4 h-4 text-emerald-400" />
              AI Matches ({matches.length})
            </h3>
            <div className="flex gap-3 overflow-x-auto no-scrollbar pb-2">
              {matches.map((match) => {
                const other = match.lost_item.id === item.id ? match.found_item : match.lost_item;
                const score = Math.round(match.similarity_score * 100);
                return (
                  <motion.div
                    key={match.id}
                    whileHover={{ scale: 1.02 }}
                    className="glass rounded-2xl border border-white/5 overflow-hidden flex-shrink-0 w-48 cursor-pointer"
                    onClick={() => navigate(`/items/${other.id}`)}
                  >
                    <div className="h-28 overflow-hidden bg-secondary/50">
                      <img src={other.images[0] || ''} className="w-full h-full object-cover" />
                    </div>
                    <div className="p-3">
                      <p className="text-xs font-semibold text-foreground truncate mb-1.5">{other.title}</p>
                      <span className={cn('text-xs font-bold px-2 py-0.5 rounded-lg border', getMatchBg(score), getMatchColor(score))}>
                        <Zap className="w-2.5 h-2.5 inline mr-0.5" />{score}% match
                      </span>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        )}

        {/* Owner */}
        <div className="glass rounded-2xl p-5 border border-white/5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center overflow-hidden">
            {item.owner.avatar_url ? (
              <img src={item.owner.avatar_url} className="w-full h-full object-cover" />
            ) : (
              <span className="font-bold text-emerald-400 text-sm">{getInitials(item.owner.name)}</span>
            )}
          </div>
          <div>
            <p className="font-semibold text-foreground text-sm">{item.owner.name}</p>
            <p className="text-xs text-muted-foreground">{item.owner.department} · {item.owner.roll_number}</p>
          </div>
          {!isOwner && (
            <button onClick={handleStartChat} className="ml-auto btn-emerald flex items-center gap-2 text-sm py-2">
              <MessageCircle className="w-4 h-4" /> Message
            </button>
          )}
        </div>
      </div>

      {/* Chat panel */}
      <AnimatePresence>
        {showChat && chatRoomId && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 360, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="hidden md:flex border-l border-border/30 flex-shrink-0 overflow-hidden"
          >
            <ChatPanel roomId={chatRoomId} onClose={() => setShowChat(false)} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

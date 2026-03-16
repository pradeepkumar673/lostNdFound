// src/pages/ProfilePage.tsx
import { useState, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Camera, Star, Award, Package, CheckCircle, Edit2, Save, X } from 'lucide-react';
import { toast } from 'sonner';
import { authApi, itemsApi } from '@/lib/api';
import { useStore } from '@/store';
import { queryClient } from '@/lib/queryClient';
import { cn, getInitials, formatDate } from '@/lib/utils';
import ItemCard from '@/components/item/ItemCard';
import { Skeleton } from '@/components/ui/Skeleton';

export default function ProfilePage() {
  const { user, updateUser } = useStore();
  const fileRef = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(user?.name || '');

  const { data: myItems, isLoading } = useQuery({
    queryKey: ['my-items'],
    queryFn: itemsApi.myItems,
  });

  const { mutate: saveProfile, isPending: saving } = useMutation({
    mutationFn: (fd: FormData) => authApi.updateProfile(fd),
    onSuccess: (updated) => {
      updateUser(updated);
      queryClient.invalidateQueries({ queryKey: ['me'] });
      setEditing(false);
      toast.success('Profile updated!');
    },
    onError: () => toast.error('Failed to update profile'),
  });

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('avatar', file);
    saveProfile(fd);
  };

  const handleSaveName = () => {
    if (!editName.trim()) return;
    const fd = new FormData();
    fd.append('name', editName.trim());
    saveProfile(fd);
  };

  const stats = [
    { icon: Package, label: 'Items Posted', value: myItems?.length ?? 0, color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
    { icon: CheckCircle, label: 'Resolved', value: myItems?.filter((i) => i.status === 'resolved').length ?? 0, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { icon: Star, label: 'Points', value: user?.points ?? 0, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    { icon: Award, label: 'Badges', value: user?.badges?.length ?? 0, color: 'text-pink-400', bg: 'bg-pink-500/10' },
  ];

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-8">
      {/* Profile card */}
      <div className="glass rounded-3xl p-6 md:p-8 border border-white/5">
        <div className="flex items-start gap-6 flex-wrap">
          {/* Avatar */}
          <div className="relative group">
            <div className="w-24 h-24 rounded-3xl bg-emerald-500/15 border-2 border-emerald-500/20 overflow-hidden flex items-center justify-center">
              {user?.avatar_url ? (
                <img src={user.avatar_url} className="w-full h-full object-cover" />
              ) : (
                <span className="font-display font-bold text-3xl text-emerald-400">{getInitials(user?.name || 'U')}</span>
              )}
            </div>
            <button
              onClick={() => fileRef.current?.click()}
              className="absolute inset-0 rounded-3xl bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <Camera className="w-6 h-6 text-white" />
            </button>
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleAvatarChange} />
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            {editing ? (
              <div className="flex items-center gap-2 mb-2">
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="input-base text-xl font-bold py-2"
                  autoFocus
                />
                <button onClick={handleSaveName} disabled={saving} className="p-2 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                  <Save className="w-4 h-4" />
                </button>
                <button onClick={() => { setEditing(false); setEditName(user?.name || ''); }} className="p-2 rounded-xl bg-secondary text-muted-foreground border border-border">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3 mb-1">
                <h1 className="font-display font-bold text-2xl text-foreground">{user?.name}</h1>
                <button onClick={() => setEditing(true)} className="p-1.5 rounded-lg hover:bg-white/5 text-muted-foreground">
                  <Edit2 className="w-4 h-4" />
                </button>
              </div>
            )}
            <p className="text-muted-foreground text-sm">{user?.department}</p>
            <p className="text-muted-foreground text-sm">{user?.roll_number} · {user?.email}</p>
            <p className="text-muted-foreground text-xs mt-1">Member since {user?.created_at ? formatDate(user.created_at) : '—'}</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6 pt-6 border-t border-border/30">
          {stats.map((s, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="text-center"
            >
              <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-2', s.bg)}>
                <s.icon className={cn('w-5 h-5', s.color)} />
              </div>
              <div className="font-display font-bold text-xl text-foreground">{s.value}</div>
              <div className="text-xs text-muted-foreground">{s.label}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Badges */}
      {user?.badges && user.badges.length > 0 && (
        <div>
          <h2 className="font-display font-semibold text-lg text-foreground mb-4 flex items-center gap-2">
            <Award className="w-5 h-5 text-yellow-400" /> Badges
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {user.badges.map((badge) => (
              <motion.div
                key={badge.id}
                whileHover={{ scale: 1.03, y: -2 }}
                className="glass rounded-2xl p-4 border border-white/5 text-center"
              >
                <div className="text-3xl mb-2">{badge.icon}</div>
                <p className="font-semibold text-foreground text-sm">{badge.name}</p>
                <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{badge.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* My items */}
      <div>
        <h2 className="font-display font-semibold text-lg text-foreground mb-4">My Items</h2>
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-56 rounded-2xl" />)}
          </div>
        ) : myItems && myItems.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {myItems.map((item) => <ItemCard key={item.id} item={item} />)}
          </div>
        ) : (
          <div className="glass rounded-2xl p-10 text-center border border-dashed border-border">
            <p className="text-muted-foreground">No items posted yet</p>
          </div>
        )}
      </div>
    </div>
  );
}

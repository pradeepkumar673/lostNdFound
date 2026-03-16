// src/pages/ItemsPage.tsx
import { useState, useCallback } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Camera, Filter, X, SlidersHorizontal } from 'lucide-react';
import { itemsApi } from '@/lib/api';
import type { ItemFilters, ItemType } from '@/types';
import { CATEGORIES, CAMPUS_ZONES } from '@/types';
import ItemCard from '@/components/item/ItemCard';
import { ItemCardSkeleton } from '@/components/ui/Skeleton';
import { cn, debounce } from '@/lib/utils';
import ImageSearchModal from '@/components/item/ImageSearchModal';

export default function ItemsPage() {
  const [filters, setFilters] = useState<ItemFilters>({ per_page: 12 });
  const [showFilters, setShowFilters] = useState(false);
  const [showImageSearch, setShowImageSearch] = useState(false);
  const [searchInput, setSearchInput] = useState('');

  const debouncedSearch = useCallback(
    debounce((val: string) => setFilters((f) => ({ ...f, search: val || undefined, page: 1 })), 400),
    []
  );

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteQuery({
    queryKey: ['items', filters],
    queryFn: ({ pageParam = 1 }) => itemsApi.list({ ...filters, page: pageParam as number }),
    initialPageParam: 1,
    getNextPageParam: (last) => last.has_next ? last.page + 1 : undefined,
  });

  const allItems = data?.pages.flatMap((p) => p.items) ?? [];

  const setFilter = (key: keyof ItemFilters, val: string | undefined) =>
    setFilters((f) => ({ ...f, [key]: val, page: 1 }));

  return (
    <div className="flex h-full">
      {/* Sidebar filters - desktop */}
      <AnimatePresence>
        {showFilters && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="hidden md:flex flex-col border-r border-border/30 overflow-y-auto no-scrollbar flex-shrink-0"
          >
            <div className="p-5 space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-foreground">Filters</h3>
                <button
                  onClick={() => setFilters({ per_page: 12 })}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear all
                </button>
              </div>

              {/* Type toggle */}
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 block">Type</label>
                <div className="flex gap-2">
                  {(['lost', 'found'] as ItemType[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => setFilter('type', filters.type === t ? undefined : t)}
                      className={cn(
                        'flex-1 py-2 rounded-xl text-sm font-semibold transition-all capitalize',
                        filters.type === t
                          ? t === 'lost' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-secondary/50 text-muted-foreground border border-border hover:bg-secondary'
                      )}
                    >
                      {t === 'lost' ? '🔍' : '✅'} {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Categories */}
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 block">Category</label>
                <div className="grid grid-cols-2 gap-2">
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setFilter('category', filters.category === cat.id ? undefined : cat.id)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all',
                        filters.category === cat.id
                          ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                          : 'bg-secondary/50 text-muted-foreground border border-border hover:bg-secondary'
                      )}
                    >
                      <span>{cat.icon}</span> {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Location */}
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 block">Location</label>
                <div className="space-y-1.5">
                  {CAMPUS_ZONES.map((zone) => (
                    <button
                      key={zone}
                      onClick={() => setFilter('location', filters.location === zone ? undefined : zone)}
                      className={cn(
                        'w-full text-left px-3 py-2 rounded-xl text-xs font-medium transition-all',
                        filters.location === zone
                          ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                          : 'text-muted-foreground hover:bg-secondary/50'
                      )}
                    >
                      {zone}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status */}
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 block">Status</label>
                <div className="space-y-1.5">
                  {['active', 'claimed', 'resolved'].map((status) => (
                    <button
                      key={status}
                      onClick={() => setFilter('status', filters.status === status ? undefined : status as ItemFilters['status'])}
                      className={cn(
                        'w-full text-left px-3 py-2 rounded-xl text-xs font-semibold capitalize transition-all',
                        filters.status === status
                          ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                          : 'text-muted-foreground hover:bg-secondary/50'
                      )}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Search bar */}
        <div className="p-4 md:p-6 border-b border-border/30 space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                value={searchInput}
                onChange={(e) => {
                  setSearchInput(e.target.value);
                  debouncedSearch(e.target.value);
                }}
                placeholder="Search items by title, description, brand..."
                className="input-base pl-10 pr-10"
              />
              {searchInput && (
                <button
                  onClick={() => { setSearchInput(''); setFilter('search', undefined); }}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <button
              onClick={() => setShowImageSearch(true)}
              className="glass px-3.5 py-3 rounded-xl text-muted-foreground hover:text-foreground border border-border hover:border-emerald-500/30 transition-all flex items-center gap-2 text-sm font-medium flex-shrink-0"
              title="Search by image"
            >
              <Camera className="w-4 h-4" />
              <span className="hidden sm:block">Image Search</span>
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={cn(
                'glass px-3.5 py-3 rounded-xl border transition-all flex items-center gap-2 text-sm font-medium flex-shrink-0',
                showFilters
                  ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                  : 'border-border text-muted-foreground hover:text-foreground'
              )}
            >
              <SlidersHorizontal className="w-4 h-4" />
              <span className="hidden sm:block">Filters</span>
            </button>
          </div>

          {/* Active filter chips */}
          {(filters.type || filters.category || filters.location || filters.status) && (
            <div className="flex items-center gap-2 flex-wrap">
              {filters.type && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-secondary text-xs font-medium text-foreground border border-border">
                  {filters.type}
                  <button onClick={() => setFilter('type', undefined)}><X className="w-3 h-3" /></button>
                </span>
              )}
              {filters.category && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-secondary text-xs font-medium text-foreground border border-border">
                  {CATEGORIES.find((c) => c.id === filters.category)?.label}
                  <button onClick={() => setFilter('category', undefined)}><X className="w-3 h-3" /></button>
                </span>
              )}
              {filters.location && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-secondary text-xs font-medium text-foreground border border-border">
                  📍 {filters.location}
                  <button onClick={() => setFilter('location', undefined)}><X className="w-3 h-3" /></button>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Items grid */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
              {[...Array(12)].map((_, i) => <ItemCardSkeleton key={i} />)}
            </div>
          ) : allItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <div className="text-6xl mb-4">🔍</div>
              <h3 className="font-semibold text-foreground text-xl mb-2">Nothing found</h3>
              <p className="text-muted-foreground text-sm max-w-sm">
                Try adjusting your filters or searching with different keywords.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-muted-foreground">
                  <span className="font-semibold text-foreground">{data?.pages[0]?.total ?? 0}</span> items
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                <AnimatePresence>
                  {allItems.map((item, i) => (
                    <ItemCard key={item.id} item={item} style={{ animationDelay: `${(i % 12) * 50}ms` }} />
                  ))}
                </AnimatePresence>
              </div>

              {hasNextPage && (
                <div className="flex justify-center mt-8">
                  <button
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                    className="glass px-6 py-3 rounded-xl text-sm font-semibold text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/10 transition-all disabled:opacity-60"
                  >
                    {isFetchingNextPage ? 'Loading...' : 'Load more'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {showImageSearch && <ImageSearchModal onClose={() => setShowImageSearch(false)} />}
    </div>
  );
}

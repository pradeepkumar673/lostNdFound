// src/components/item/ItemGrid.tsx
import { motion, AnimatePresence } from 'framer-motion';
import ItemCard from './ItemCard';
import { ItemCardSkeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import type { Item } from '@/types';
import { Link } from 'react-router-dom';

interface ItemGridProps {
  items: Item[];
  isLoading?: boolean;
  skeletonCount?: number;
  columns?: 2 | 3 | 4;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
}

const colClasses = {
  2: 'grid-cols-1 sm:grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3',
  4: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4',
};

export default function ItemGrid({
  items,
  isLoading = false,
  skeletonCount = 8,
  columns = 3,
  emptyTitle = 'No items found',
  emptyDescription = 'Try adjusting your filters or search terms.',
  emptyAction,
}: ItemGridProps) {
  if (isLoading) {
    return (
      <div className={`grid gap-4 ${colClasses[columns]}`}>
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <ItemCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (!items.length) {
    return (
      <EmptyState
        emoji="🔍"
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction || (
          <Link to="/items/new" className="btn-emerald text-sm inline-flex items-center gap-2">
            Post an item
          </Link>
        )}
      />
    );
  }

  return (
    <div className={`grid gap-4 ${colClasses[columns]}`}>
      <AnimatePresence>
        {items.map((item, i) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ delay: Math.min(i * 0.04, 0.4) }}
          >
            <ItemCard item={item} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

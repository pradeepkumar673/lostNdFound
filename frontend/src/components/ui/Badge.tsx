// src/components/ui/Badge.tsx
import { cn } from '@/lib/utils';
import type { ItemType, ItemStatus } from '@/types';

interface StatusBadgeProps {
  type?: ItemType;
  status?: ItemStatus;
  className?: string;
}

export function TypeBadge({ type, className }: { type: ItemType; className?: string }) {
  return (
    <span className={cn(type === 'lost' ? 'badge-lost' : 'badge-found', className)}>
      {type === 'lost' ? '🔍 Lost' : '✅ Found'}
    </span>
  );
}

export function StatusBadge({ status, className }: { status: ItemStatus; className?: string }) {
  return (
    <span className={cn(
      status === 'active' ? 'badge-found' :
      status === 'claimed' ? 'badge-claimed' : 'badge-resolved',
      className
    )}>
      {status}
    </span>
  );
}

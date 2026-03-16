// src/components/ui/EmptyState.tsx
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  emoji?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ emoji = '🔍', title, description, action, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'flex flex-col items-center justify-center text-center py-16 px-8 glass rounded-3xl border border-dashed border-border',
        className
      )}
    >
      <div className="text-6xl mb-5 animate-float">{emoji}</div>
      <h3 className="font-display font-bold text-xl text-foreground mb-2">{title}</h3>
      {description && (
        <p className="text-muted-foreground text-sm max-w-xs leading-relaxed mb-6">{description}</p>
      )}
      {action && <div>{action}</div>}
    </motion.div>
  );
}

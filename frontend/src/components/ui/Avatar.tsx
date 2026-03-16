// src/components/ui/Avatar.tsx
import { cn, getInitials } from '@/lib/utils';

interface AvatarProps {
  name: string;
  src?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const sizeMap = {
  xs: 'w-6 h-6 text-[10px]',
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-12 h-12 text-base',
  xl: 'w-16 h-16 text-xl',
};

export function Avatar({ name, src, size = 'md', className }: AvatarProps) {
  return (
    <div className={cn(
      'rounded-full bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center overflow-hidden flex-shrink-0',
      sizeMap[size],
      className
    )}>
      {src ? (
        <img src={src} alt={name} className="w-full h-full object-cover" />
      ) : (
        <span className="font-bold text-emerald-400">{getInitials(name)}</span>
      )}
    </div>
  );
}

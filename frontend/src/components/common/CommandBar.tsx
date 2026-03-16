// src/components/common/CommandBar.tsx
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, LayoutDashboard, PlusCircle, GitMerge, MessageCircle, Map, Bell, User, X } from 'lucide-react';

const COMMANDS = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard', shortcut: '' },
  { label: 'Browse Items', icon: Search, path: '/items', shortcut: '' },
  { label: 'Post New Item', icon: PlusCircle, path: '/items/new', shortcut: '' },
  { label: 'My Matches', icon: GitMerge, path: '/matches', shortcut: '' },
  { label: 'Messages', icon: MessageCircle, path: '/chat', shortcut: '' },
  { label: 'Campus Heatmap', icon: Map, path: '/heatmap', shortcut: '' },
  { label: 'Notifications', icon: Bell, path: '/notifications', shortcut: '' },
  { label: 'My Profile', icon: User, path: '/profile', shortcut: '' },
];

export default function CommandBar() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
        setQuery('');
        setSelected(0);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  const handleSelect = (path: string) => {
    navigate(path);
    setOpen(false);
    setQuery('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected((s) => Math.min(s + 1, filtered.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
    if (e.key === 'Enter' && filtered[selected]) handleSelect(filtered[selected].path);
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
            className="relative z-10 w-full max-w-md mx-4"
          >
            <div className="glass rounded-2xl border border-white/10 overflow-hidden shadow-card-hover">
              {/* Search input */}
              <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border/30">
                <Search className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSelected(0); }}
                  onKeyDown={handleKeyDown}
                  placeholder="Search pages..."
                  className="flex-1 bg-transparent text-foreground placeholder-muted-foreground text-sm outline-none"
                />
                <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Results */}
              <div className="py-2 max-h-72 overflow-y-auto no-scrollbar">
                {filtered.length === 0 ? (
                  <p className="text-center text-sm text-muted-foreground py-6">No results found</p>
                ) : (
                  filtered.map((cmd, i) => (
                    <button
                      key={cmd.path}
                      onClick={() => handleSelect(cmd.path)}
                      onMouseEnter={() => setSelected(i)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-all ${
                        i === selected ? 'bg-emerald-500/10 text-emerald-400' : 'text-foreground hover:bg-white/5'
                      }`}
                    >
                      <cmd.icon className="w-4 h-4 flex-shrink-0" />
                      {cmd.label}
                    </button>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="px-4 py-2.5 border-t border-border/30 flex items-center gap-4 text-[10px] text-muted-foreground">
                <span><kbd className="font-mono bg-secondary px-1.5 py-0.5 rounded text-[10px]">↑↓</kbd> navigate</span>
                <span><kbd className="font-mono bg-secondary px-1.5 py-0.5 rounded text-[10px]">↵</kbd> select</span>
                <span><kbd className="font-mono bg-secondary px-1.5 py-0.5 rounded text-[10px]">Esc</kbd> close</span>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

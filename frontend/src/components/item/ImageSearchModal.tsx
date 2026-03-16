// src/components/item/ImageSearchModal.tsx
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Upload, Sparkles, Search } from 'lucide-react';
import { itemsApi } from '@/lib/api';
import { toast } from 'sonner';
import type { Item } from '@/types';
import ItemCard from './ItemCard';

export default function ImageSearchModal({ onClose }: { onClose: () => void }) {
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [results, setResults] = useState<Item[] | null>(null);
  const [loading, setLoading] = useState(false);

  const onDrop = useCallback((files: File[]) => {
    if (!files[0]) return;
    setImage(files[0]);
    setPreview(URL.createObjectURL(files[0]));
    setResults(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
    maxFiles: 1,
  });

  const handleSearch = async () => {
    if (!image) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('image', image);
      const data = await itemsApi.searchByImage(fd);
      setResults(data);
    } catch {
      toast.error('Image search failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="glass rounded-3xl w-full max-w-2xl max-h-[90vh] overflow-y-auto no-scrollbar border border-white/10"
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="font-display font-bold text-xl text-foreground flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-emerald-400" />
                Visual Search
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5">Upload an image to find similar items</p>
            </div>
            <button onClick={onClose} className="p-2 rounded-xl hover:bg-white/5 text-muted-foreground">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drop zone */}
          {!preview ? (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ${
                isDragActive ? 'border-emerald-500 bg-emerald-500/5' : 'border-border hover:border-emerald-500/50'
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-foreground font-medium">Drop an image here</p>
              <p className="text-muted-foreground text-sm mt-1">or click to browse</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="relative rounded-2xl overflow-hidden">
                <img src={preview} className="w-full max-h-48 object-cover" />
                <button
                  onClick={() => { setPreview(null); setImage(null); setResults(null); }}
                  className="absolute top-3 right-3 glass p-1.5 rounded-lg text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <button
                onClick={handleSearch}
                disabled={loading}
                className="w-full btn-emerald flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Searching with CLIP AI...
                  </>
                ) : (
                  <><Search className="w-4 h-4" /> Find Similar Items</>
                )}
              </button>
            </div>
          )}

          {/* Results */}
          <AnimatePresence>
            {results !== null && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6"
              >
                <h3 className="font-semibold text-foreground mb-3">
                  {results.length > 0 ? `${results.length} similar items found` : 'No similar items found'}
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {results.map((item) => <ItemCard key={item.id} item={item} />)}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}

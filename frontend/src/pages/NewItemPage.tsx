// src/pages/NewItemPage.tsx
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import { useMutation } from '@tanstack/react-query';
import {
  Upload, Sparkles, X, ChevronRight, ChevronLeft,
  MapPin, Tag, Check, Loader2, Wand2, AlertCircle
} from 'lucide-react';
import { toast } from 'sonner';
import { itemsApi } from '@/lib/api';
import type { AIAnalysis, ItemType } from '@/types';
import { CATEGORIES, CAMPUS_ZONES } from '@/types';
import { cn } from '@/lib/utils';
import { queryClient } from '@/lib/queryClient';

const STEPS = ['Upload Images', 'AI Analysis', 'Item Details', 'Review'];

export default function NewItemPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [images, setImages] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [aiResult, setAiResult] = useState<AIAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [tagInput, setTagInput] = useState('');

  const [form, setForm] = useState({
    type: 'lost' as ItemType,
    title: '',
    description: '',
    category: '',
    campus_zone: '',
    color: '',
    brand: '',
    tags: [] as string[],
  });

  const onDrop = useCallback((accepted: File[]) => {
    const newFiles = [...images, ...accepted].slice(0, 5);
    setImages(newFiles);
    setPreviews(newFiles.map((f) => URL.createObjectURL(f)));
  }, [images]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
    maxFiles: 5,
  });

  const removeImage = (i: number) => {
    const newFiles = images.filter((_, idx) => idx !== i);
    setImages(newFiles);
    setPreviews(newFiles.map((f) => URL.createObjectURL(f)));
  };

  const handleAnalyze = async () => {
    if (!images.length) { toast.error('Upload at least one image'); return; }
    setAnalyzing(true);
    try {
      const fd = new FormData();
      images.forEach((img) => fd.append('images', img));
      const result = await itemsApi.analyze(fd);
      setAiResult(result);
      setForm((f) => ({
        ...f,
        title: result.suggested_title || f.title,
        description: result.suggested_description || f.description,
        category: result.category || f.category,
        color: result.color || f.color,
        brand: result.brand || f.brand,
        tags: result.tags || f.tags,
      }));
      setStep(1);
      toast.success('AI analysis complete! ✨');
    } catch {
      toast.error('AI analysis failed. You can fill details manually.');
      setStep(2);
    } finally {
      setAnalyzing(false);
    }
  };

  const { mutate: submitItem, isPending } = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      images.forEach((img) => fd.append('images', img));
      Object.entries(form).forEach(([k, v]) => {
        if (Array.isArray(v)) fd.append(k, JSON.stringify(v));
        else if (v) fd.append(k, v);
      });
      return itemsApi.create(fd);
    },
    onSuccess: (item) => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['my-items'] });
      toast.success('Item posted successfully! 🎉');
      navigate(`/items/${item.id}`);
    },
    onError: () => toast.error('Failed to post item'),
  });

  const addTag = (tag: string) => {
    const cleaned = tag.trim().toLowerCase();
    if (cleaned && !form.tags.includes(cleaned)) {
      setForm((f) => ({ ...f, tags: [...f.tags, cleaned] }));
    }
    setTagInput('');
  };

  const removeTag = (tag: string) => setForm((f) => ({ ...f, tags: f.tags.filter((t) => t !== tag) }));

  const canProceed = [
    images.length > 0,
    true,
    form.title.length > 2 && form.category && form.campus_zone,
    true,
  ];

  return (
    <div className="p-6 md:p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display font-bold text-2xl text-foreground mb-1">Post New Item</h1>
        <p className="text-muted-foreground text-sm">AI will help auto-fill details from your images</p>
      </div>

      {/* Step indicators */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((label, i) => (
          <div key={i} className="flex items-center gap-2 flex-1">
            <div className="flex flex-col items-center gap-1">
              <div className={cn(
                'w-8 h-8 rounded-xl flex items-center justify-center text-sm font-bold transition-all',
                i < step ? 'step-completed' : i === step ? 'step-active' : 'step-inactive'
              )}>
                {i < step ? <Check className="w-4 h-4" /> : i + 1}
              </div>
              <span className={cn('text-xs font-medium hidden sm:block', i === step ? 'text-emerald-400' : 'text-muted-foreground')}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={cn('flex-1 h-0.5 mb-5 transition-all', i < step ? 'bg-emerald-500' : 'bg-border')} />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
        >
          {/* Step 0: Upload */}
          {step === 0 && (
            <div className="space-y-6">
              <div
                {...getRootProps()}
                className={cn(
                  'border-2 border-dashed rounded-3xl p-12 text-center cursor-pointer transition-all',
                  isDragActive ? 'border-emerald-500 bg-emerald-500/5' : 'border-border hover:border-emerald-500/50 hover:bg-emerald-500/3'
                )}
              >
                <input {...getInputProps()} />
                <div className="w-16 h-16 bg-emerald-500/10 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-emerald-500/20">
                  <Upload className="w-8 h-8 text-emerald-400" />
                </div>
                <h3 className="font-semibold text-foreground text-lg mb-1">Drop images here</h3>
                <p className="text-muted-foreground text-sm">or click to browse — up to 5 images</p>
              </div>

              {/* Previews */}
              {previews.length > 0 && (
                <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
                  {previews.map((src, i) => (
                    <div key={i} className="relative group aspect-square rounded-xl overflow-hidden bg-secondary/50">
                      <img src={src} className="w-full h-full object-cover" />
                      <button
                        onClick={() => removeImage(i)}
                        className="absolute top-1 right-1 w-6 h-6 bg-black/70 rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <X className="w-3 h-3 text-white" />
                      </button>
                      {i === 0 && (
                        <div className="absolute bottom-1 left-1 px-1.5 py-0.5 bg-black/70 rounded text-[10px] text-white font-medium">Main</div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Type selector */}
              <div>
                <label className="text-sm font-semibold text-foreground/80 mb-3 block">What are you posting?</label>
                <div className="grid grid-cols-2 gap-3">
                  {(['lost', 'found'] as ItemType[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => setForm((f) => ({ ...f, type: t }))}
                      className={cn(
                        'py-4 rounded-2xl font-semibold capitalize text-sm transition-all border',
                        form.type === t
                          ? t === 'lost'
                            ? 'bg-red-500/20 text-red-400 border-red-500/30'
                            : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : 'bg-secondary/50 text-muted-foreground border-border'
                      )}
                    >
                      <span className="text-2xl block mb-1">{t === 'lost' ? '🔍' : '✅'}</span>
                      I {t} something
                    </button>
                  ))}
                </div>
              </div>

              {/* AI analyze button */}
              {images.length > 0 && (
                <motion.button
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="w-full py-4 rounded-2xl font-bold text-white flex items-center justify-center gap-3 transition-all"
                  style={{ background: 'linear-gradient(135deg, #10b981, #059669)', boxShadow: '0 0 30px rgba(16,185,129,0.4)' }}
                >
                  {analyzing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Analyzing with Gemini AI...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-5 h-5" />
                      <span>✨ Analyze with AI</span>
                    </>
                  )}
                </motion.button>
              )}
            </div>
          )}

          {/* Step 1: AI Results */}
          {step === 1 && aiResult && (
            <div className="space-y-4">
              <div className="glass rounded-2xl p-5 border border-emerald-500/20 bg-emerald-500/5">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="w-5 h-5 text-emerald-400" />
                  <h3 className="font-semibold text-emerald-400">AI Analysis Results</h3>
                </div>

                <div className="space-y-3">
                  {/* Category confidence */}
                  <div>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-muted-foreground">Category confidence</span>
                      <span className="font-semibold text-foreground">{Math.round(aiResult.category_confidence * 100)}%</span>
                    </div>
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${aiResult.category_confidence * 100}%` }}
                        transition={{ duration: 0.8, ease: 'easeOut' }}
                        className="h-full bg-emerald-500 rounded-full"
                      />
                    </div>
                  </div>

                  {/* Suggested title */}
                  <div className="flex items-start gap-3 p-3 bg-secondary/50 rounded-xl">
                    <span className="text-xs font-semibold text-muted-foreground uppercase mt-0.5">Title</span>
                    <span className="text-sm text-foreground font-medium">{aiResult.suggested_title}</span>
                  </div>

                  {/* Category */}
                  <div className="flex items-center gap-3 p-3 bg-secondary/50 rounded-xl">
                    <span className="text-xs font-semibold text-muted-foreground uppercase">Category</span>
                    <span className="text-sm text-foreground">{aiResult.category}</span>
                  </div>

                  {/* Color & Brand */}
                  {(aiResult.color || aiResult.brand) && (
                    <div className="flex gap-3">
                      {aiResult.color && (
                        <div className="flex-1 p-3 bg-secondary/50 rounded-xl">
                          <div className="text-xs font-semibold text-muted-foreground uppercase mb-1">Color</div>
                          <div className="text-sm text-foreground capitalize">{aiResult.color}</div>
                        </div>
                      )}
                      {aiResult.brand && (
                        <div className="flex-1 p-3 bg-secondary/50 rounded-xl">
                          <div className="text-xs font-semibold text-muted-foreground uppercase mb-1">Brand</div>
                          <div className="text-sm text-foreground">{aiResult.brand}</div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* OCR text */}
                  {aiResult.ocr_text && (
                    <div className="p-3 bg-secondary/50 rounded-xl border border-yellow-500/20">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-yellow-400" />
                        <span className="text-xs font-semibold text-yellow-400">Text detected in image</span>
                      </div>
                      <p className="text-sm text-foreground font-mono">{aiResult.ocr_text}</p>
                    </div>
                  )}

                  {/* Tags */}
                  {aiResult.tags.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {aiResult.tags.map((tag) => (
                        <span key={tag} className="text-xs px-2.5 py-1 bg-secondary rounded-lg text-muted-foreground border border-border">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="glass rounded-2xl p-4 border border-border">
                <p className="text-sm text-muted-foreground">
                  <span className="text-emerald-400 font-semibold">All fields have been pre-filled</span> based on the AI analysis. 
                  You can review and edit them in the next step.
                </p>
              </div>
            </div>
          )}

          {/* Step 2: Item Details form */}
          {step === 2 && (
            <div className="space-y-5">
              {/* Title */}
              <div>
                <label className="text-sm font-semibold text-foreground/80 mb-1.5 block">Title *</label>
                <input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="e.g. Black Lenovo ThinkPad Laptop"
                  className="input-base"
                />
              </div>

              {/* Description */}
              <div>
                <label className="text-sm font-semibold text-foreground/80 mb-1.5 block">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  rows={3}
                  placeholder="Describe the item in detail..."
                  className="input-base resize-none"
                />
              </div>

              {/* Category */}
              <div>
                <label className="text-sm font-semibold text-foreground/80 mb-2 block">Category *</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setForm((f) => ({ ...f, category: cat.id }))}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium border transition-all',
                        form.category === cat.id
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : 'bg-secondary/50 text-muted-foreground border-border hover:bg-secondary'
                      )}
                    >
                      <span>{cat.icon}</span> {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Location */}
              <div>
                <label className="text-sm font-semibold text-foreground/80 mb-1.5 block flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-emerald-400" /> Campus Zone *
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {CAMPUS_ZONES.map((zone) => (
                    <button
                      key={zone}
                      onClick={() => setForm((f) => ({ ...f, campus_zone: zone }))}
                      className={cn(
                        'px-3 py-2 rounded-xl text-xs font-medium border transition-all text-left',
                        form.campus_zone === zone
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : 'bg-secondary/50 text-muted-foreground border-border hover:bg-secondary'
                      )}
                    >
                      {zone}
                    </button>
                  ))}
                </div>
              </div>

              {/* Color + Brand */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-semibold text-foreground/80 mb-1.5 block">Color</label>
                  <input
                    value={form.color}
                    onChange={(e) => setForm((f) => ({ ...f, color: e.target.value }))}
                    placeholder="e.g. Black, Blue"
                    className="input-base"
                  />
                </div>
                <div>
                  <label className="text-sm font-semibold text-foreground/80 mb-1.5 block">Brand</label>
                  <input
                    value={form.brand}
                    onChange={(e) => setForm((f) => ({ ...f, brand: e.target.value }))}
                    placeholder="e.g. Apple, Samsung"
                    className="input-base"
                  />
                </div>
              </div>

              {/* Tags */}
              <div>
                <label className="text-sm font-semibold text-foreground/80 mb-1.5 block flex items-center gap-1.5">
                  <Tag className="w-4 h-4 text-emerald-400" /> Tags
                </label>
                <div className="flex gap-2 flex-wrap mb-2">
                  {form.tags.map((tag) => (
                    <span key={tag} className="inline-flex items-center gap-1 px-2.5 py-1 bg-secondary rounded-lg text-xs font-medium text-muted-foreground border border-border">
                      #{tag}
                      <button onClick={() => removeTag(tag)}><X className="w-3 h-3" /></button>
                    </span>
                  ))}
                </div>
                <input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(tagInput); } }}
                  placeholder="Type a tag and press Enter"
                  className="input-base"
                />
              </div>
            </div>
          )}

          {/* Step 3: Review */}
          {step === 3 && (
            <div className="space-y-6">
              <div className="glass rounded-2xl overflow-hidden border border-white/5">
                {/* Images preview */}
                {previews.length > 0 && (
                  <div className="flex gap-2 p-4 overflow-x-auto no-scrollbar">
                    {previews.map((src, i) => (
                      <img key={i} src={src} className="w-24 h-24 rounded-xl object-cover flex-shrink-0" />
                    ))}
                  </div>
                )}
                <div className="p-5 space-y-3 border-t border-border/30">
                  <div className="flex items-center gap-2">
                    <span className={cn('text-xs font-bold px-2.5 py-1 rounded-lg', form.type === 'lost' ? 'badge-lost' : 'badge-found')}>
                      {form.type === 'lost' ? '🔍 Lost' : '✅ Found'}
                    </span>
                    <span className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded-lg capitalize">
                      {CATEGORIES.find((c) => c.id === form.category)?.icon} {form.category}
                    </span>
                  </div>
                  <h3 className="font-display font-bold text-xl text-foreground">{form.title}</h3>
                  {form.description && <p className="text-sm text-muted-foreground">{form.description}</p>}
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <MapPin className="w-4 h-4 text-emerald-400" />
                    {form.campus_zone}
                  </div>
                  {form.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {form.tags.map((t) => (
                        <span key={t} className="text-xs px-2 py-0.5 bg-secondary rounded text-muted-foreground">#{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between mt-8 pt-4 border-t border-border/30">
        <button
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-border text-muted-foreground hover:text-foreground hover:bg-white/5 disabled:opacity-30 transition-all font-medium text-sm"
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        {step < STEPS.length - 1 ? (
          <button
            onClick={() => setStep((s) => s + 1)}
            disabled={!canProceed[step]}
            className="btn-emerald flex items-center gap-2 text-sm disabled:opacity-40"
          >
            Continue <ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={() => submitItem()}
            disabled={isPending}
            className="btn-emerald flex items-center gap-2 text-sm disabled:opacity-60"
          >
            {isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Posting...</>
            ) : (
              <><Check className="w-4 h-4" /> Post Item</>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

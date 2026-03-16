// src/pages/RegisterPage.tsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail, Lock, User, Hash, ChevronDown, Eye, EyeOff, ArrowRight, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { z } from 'zod';
import { authApi } from '@/lib/api';
import { useStore } from '@/store';
import { cn } from '@/lib/utils';

const DEPARTMENTS = [
  'Computer Science', 'Electrical Engineering', 'Mechanical Engineering',
  'Civil Engineering', 'Electronics', 'Information Technology',
  'Chemical Engineering', 'Biotechnology', 'MBA', 'Other',
];

const schema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  roll_number: z.string().min(3, 'Enter a valid roll number'),
  email: z.string().email('Enter a valid email'),
  department: z.string().min(1, 'Select your department'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

export default function RegisterPage() {
  const navigate = useNavigate();
  const setAuth = useStore((s) => s.setAuth);
  const [form, setForm] = useState({ name: '', roll_number: '', email: '', department: '', password: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
    setErrors((e2) => ({ ...e2, [e.target.name]: '' }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = schema.safeParse(form);
    if (!result.success) {
      const fieldErrors: Record<string, string> = {};
      result.error.errors.forEach((err) => {
        if (err.path[0]) fieldErrors[err.path[0] as string] = err.message;
      });
      setErrors(fieldErrors);
      return;
    }
    setLoading(true);
    try {
      const { user, token } = await authApi.register(form);
      setAuth(user, token);
      toast.success(`Welcome to CampusLostFound, ${user.name.split(' ')[0]}! 🎉`);
      navigate('/dashboard');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message || 'Registration failed';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    { name: 'name', label: 'Full Name', icon: User, type: 'text', placeholder: 'Pradeep Kumar' },
    { name: 'roll_number', label: 'Roll Number', icon: Hash, type: 'text', placeholder: '21CS001' },
    { name: 'email', label: 'College Email', icon: Mail, type: 'email', placeholder: 'you@college.edu' },
  ];

  return (
    <div>
      <div className="text-center mb-7">
        <div className="w-14 h-14 bg-emerald-500/15 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-emerald-500/20">
          <Sparkles className="w-7 h-7 text-emerald-400" />
        </div>
        <h1 className="font-display font-bold text-2xl text-foreground mb-1.5">Create account</h1>
        <p className="text-muted-foreground text-sm">Join your campus lost &amp; found network</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3.5">
        {fields.map((field) => (
          <div key={field.name}>
            <label className="block text-sm font-medium text-foreground/80 mb-1.5">{field.label}</label>
            <div className="relative">
              <field.icon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                name={field.name}
                type={field.type}
                value={form[field.name as keyof typeof form]}
                onChange={handleChange}
                placeholder={field.placeholder}
                className={cn('input-base pl-10', errors[field.name] && 'border-red-500/50')}
              />
            </div>
            {errors[field.name] && <p className="text-red-400 text-xs mt-1">{errors[field.name]}</p>}
          </div>
        ))}

        {/* Department */}
        <div>
          <label className="block text-sm font-medium text-foreground/80 mb-1.5">Department</label>
          <div className="relative">
            <select
              name="department"
              value={form.department}
              onChange={handleChange}
              className={cn('input-base appearance-none', errors.department && 'border-red-500/50')}
            >
              <option value="">Select department</option>
              {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          </div>
          {errors.department && <p className="text-red-400 text-xs mt-1">{errors.department}</p>}
        </div>

        {/* Password */}
        <div>
          <label className="block text-sm font-medium text-foreground/80 mb-1.5">Password</label>
          <div className="relative">
            <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              name="password"
              type={showPass ? 'text' : 'password'}
              value={form.password}
              onChange={handleChange}
              placeholder="Min. 6 characters"
              className={cn('input-base pl-10 pr-10', errors.password && 'border-red-500/50')}
            />
            <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
              {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password}</p>}
        </div>

        <motion.button
          type="submit"
          disabled={loading}
          whileTap={{ scale: 0.98 }}
          className="w-full btn-emerald flex items-center justify-center gap-2 mt-1 disabled:opacity-60"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>Create Account <ArrowRight className="w-4 h-4" /></>
          )}
        </motion.button>
      </form>

      <p className="text-center text-sm text-muted-foreground mt-5">
        Already have an account?{' '}
        <Link to="/login" className="text-emerald-400 hover:text-emerald-300 font-semibold">Sign in</Link>
      </p>
    </div>
  );
}

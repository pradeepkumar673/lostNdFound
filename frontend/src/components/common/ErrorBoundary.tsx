// src/components/common/ErrorBoundary.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-6">
        <div className="glass rounded-3xl p-10 max-w-md w-full text-center border border-red-500/20">
          <div className="w-16 h-16 bg-red-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="w-8 h-8 text-red-400" />
          </div>
          <h2 className="font-display font-bold text-2xl text-foreground mb-3">Something went wrong</h2>
          <p className="text-muted-foreground text-sm mb-2 font-mono bg-secondary/50 rounded-xl p-3 text-left overflow-auto">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <p className="text-muted-foreground text-sm mb-8">Don't worry — your data is safe.</p>
          <div className="flex items-center gap-3 justify-center">
            <button
              onClick={() => this.setState({ hasError: false })}
              className="btn-emerald flex items-center gap-2 text-sm"
            >
              <RefreshCw className="w-4 h-4" /> Try Again
            </button>
            <Link to="/dashboard" className="px-4 py-2.5 rounded-xl border border-border text-sm text-muted-foreground hover:text-foreground transition-all">
              Go Home
            </Link>
          </div>
        </div>
      </div>
    );
  }
}

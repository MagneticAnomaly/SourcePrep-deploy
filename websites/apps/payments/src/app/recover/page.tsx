'use client';

import { useState } from 'react';
import { ArrowLeft, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

export default function Page() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setStatus('loading');
    setMessage('');

    try {
      const res = await fetch('/api/recover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.error || 'Failed to send recovery email');
      
      setStatus('success');
      setMessage(data.message);
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Something went wrong');
    }
  };

  return (
    <div className="mx-auto max-w-lg px-4 py-16">
      <a 
        href="/" 
        className="inline-flex items-center text-sm text-text-muted hover:text-primary transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4 mr-1" />
        Back to payments
      </a>

      <div className="bg-surface border border-border rounded-xl p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-text">Recover License</h1>
        <p className="mt-2 text-text-muted">
          Lost your license key? Enter the email address you used during checkout 
          and we&apos;ll send it to you.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-6">
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium text-text">
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              disabled={status === 'loading' || status === 'success'}
              className="w-full h-10 px-3 rounded-md border border-border bg-background text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            />
          </div>

          {status === 'error' && (
            <div className="p-3 rounded-md bg-error/10 border border-error/20 flex items-start gap-3 text-sm text-error">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{message}</span>
            </div>
          )}

          {status === 'success' ? (
            <div className="p-4 rounded-md bg-success/10 border border-success/20 flex items-start gap-3 text-sm text-success">
              <CheckCircle className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-medium">Recovery email sent!</p>
                <p className="mt-1 opacity-90">{message}</p>
              </div>
            </div>
          ) : (
            <button
              type="submit"
              disabled={status === 'loading'}
              className="w-full h-10 bg-primary text-white font-medium rounded-md hover:bg-primary-hover disabled:opacity-70 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {status === 'loading' && <Loader2 className="w-4 h-4 animate-spin" />}
              Send Recovery Email
            </button>
          )}
        </form>
      </div>

      <p className="mt-8 text-center text-sm text-text-muted">
        Still having trouble?{' '}
        <a href="mailto:licenses@sourceprep.io" className="text-primary hover:underline">
          Contact support
        </a>
      </p>
    </div>
  );
}

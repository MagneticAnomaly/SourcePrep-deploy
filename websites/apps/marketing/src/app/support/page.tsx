"use client";

import { Button } from '@prep/ui';
import { Mail, Book, MessageSquare, AlertTriangle } from 'lucide-react';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text selection:bg-primary/20">
      <div className="mx-auto max-w-5xl px-6 py-24">

        {/* Nav Back */}
        <div className="mb-12">
          <a href="/" className="inline-flex items-center gap-2 text-sm font-medium text-text-muted hover:text-primary transition-colors">
            ← Return to Overview
          </a>
        </div>

        {/* Header */}
        <div className="mb-16">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-text mb-6">
            Support
          </h1>
          <p className="text-xl text-text-muted max-w-2xl leading-relaxed">
            Need help with Prep? Choose the support channel that best fits your needs.
          </p>
        </div>

        {/* Support Options Grid */}
        <div className="grid md:grid-cols-2 gap-8 mb-20">
          
          <div className="bg-surface border border-border rounded-xl p-8 shadow-sm transition-all hover:shadow-md">
            <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center text-primary mb-6">
              <Book className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-text mb-3">Documentation</h3>
            <p className="text-text-muted mb-6">
              Check our comprehensive guides, API references, and troubleshooting steps.
            </p>
            <Button variant="outline" className="w-full" asChild>
              <a href="https://docs.runprep.io">View Docs</a>
            </Button>
          </div>

          <div className="bg-surface border border-border rounded-xl p-8 shadow-sm transition-all hover:shadow-md">
            <div className="w-12 h-12 bg-success/10 rounded-lg flex items-center justify-center text-success mb-6">
              <MessageSquare className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-text mb-3">Community Support</h3>
            <p className="text-text-muted mb-6">
              Join our GitHub Discussions to ask questions, share tips, and request features.
            </p>
            <Button variant="outline" className="w-full" asChild>
              <a href="https://github.com/MagneticAnomaly/Prep-MCP/discussions">Go to GitHub</a>
            </Button>
          </div>

          <div className="bg-surface border border-border rounded-xl p-8 shadow-sm transition-all hover:shadow-md">
            <div className="w-12 h-12 bg-info/10 rounded-lg flex items-center justify-center text-info mb-6">
              <Mail className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-text mb-3">Email Support</h3>
            <p className="text-text-muted mb-6">
              Priority email support is available for Pro, Team, and Enterprise license holders.
            </p>
            <Button className="w-full shadow-sm" asChild>
              <a href="mailto:support@runprep.io">Email Support</a>
            </Button>
          </div>

          <div className="bg-surface border border-border rounded-xl p-8 shadow-sm transition-all hover:shadow-md">
            <div className="w-12 h-12 bg-warning/10 rounded-lg flex items-center justify-center text-warning mb-6">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-text mb-3">Security & Billing</h3>
            <p className="text-text-muted mb-6">
              For security reports, legal inquiries, or issues with your license activation.
            </p>
            <div className="flex gap-4">
              <Button variant="outline" className="flex-1" asChild>
                <a href="mailto:security@runprep.io">Security</a>
              </Button>
              <Button variant="outline" className="flex-1" asChild>
                <a href="mailto:billing@runprep.io">Billing</a>
              </Button>
            </div>
          </div>

        </div>
        
      </div>
    </main>
  );
}

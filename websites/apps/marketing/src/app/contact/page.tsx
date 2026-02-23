"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Page() {
  const router = useRouter();
  useEffect(() => {
    // Redirect to mailto — this page is no longer a primary destination
    window.location.href = 'mailto:support@codrag.io';
    // Fallback: show a simple redirect page
  }, []);

  return (
    <main className="min-h-screen bg-background text-text flex items-center justify-center">
      <div className="text-center max-w-md mx-auto px-6">
        <h1 className="text-2xl font-bold mb-4">Contact Us</h1>
        <p className="text-text-muted mb-6">Opening your email client...</p>
        <div className="space-y-3">
          <a href="mailto:support@codrag.io" className="block text-primary hover:underline font-mono">support@codrag.io</a>
          <a href="mailto:security@codrag.io" className="block text-primary hover:underline font-mono">security@codrag.io</a>
          <a href="https://github.com/MagneticAnomaly/CoDRAG-MCP/discussions" className="block text-primary hover:underline">GitHub Discussions →</a>
        </div>
        <div className="mt-8">
          <a href="/" className="text-sm text-text-muted hover:text-text transition-colors">← Return Home</a>
        </div>
      </div>
    </main>
  );
}

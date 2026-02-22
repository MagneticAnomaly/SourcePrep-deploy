"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Page() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/security#data-collection');
  }, [router]);

  return (
    <main className="min-h-screen bg-background text-text flex items-center justify-center">
      <p className="text-text-muted">Redirecting to <a href="/security#data-collection" className="text-primary hover:underline">Security &amp; Privacy</a>...</p>
    </main>
  );
}

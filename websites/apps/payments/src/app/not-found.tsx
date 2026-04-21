"use client";

import { Button } from '@prep/ui';

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-6">
      <h1 className="text-9xl font-bold text-primary opacity-20">404</h1>
      <h2 className="mt-8 text-3xl font-bold tracking-tight text-text">Page not found</h2>
      <p className="mt-4 text-lg text-text-muted max-w-md mx-auto">
        We couldn&apos;t find this page.
      </p>
      <div className="mt-10">
        <Button asChild>
          <a href="/">Return to Payments</a>
        </Button>
      </div>
    </div>
  );
}

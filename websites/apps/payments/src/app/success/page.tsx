export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-bold tracking-tight">Purchase complete</h1>
        <p className="mt-4 text-lg text-text-muted">
          Thanks for supporting CoDRAG. Your receipt and license details should
          arrive by email.
        </p>

        <div className="mt-8 space-y-2 rounded-lg border border-border bg-surface p-6 text-sm text-text-muted">
          <div>- Check your inbox (and spam folder) for your receipt.</div>
          <div>- Save your license key somewhere secure.</div>
          <div>
            - If you lose it later, use{' '}
            <a className="underline" href="/recover">
              license recovery
            </a>
            .
          </div>
        </div>

        <div className="mt-10 flex flex-wrap gap-3">
          <a
            href="https://docs.codrag.io"
            className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text"
          >
            Read docs
          </a>
          <a
            href="https://support.codrag.io"
            className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text"
          >
            Support
          </a>
          <a
            href="https://codrag.io"
            className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text"
          >
            Back to codrag.io
          </a>
        </div>
      </div>
    </main>
  );
}

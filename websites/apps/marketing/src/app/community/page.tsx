"use client";

import { Button } from '@prep/ui';

const GITHUB_URL =
  process.env.NEXT_PUBLIC_PREP_GITHUB_URL ??
  'https://github.com/MagneticAnomaly/RunPrep-MCP';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text overflow-hidden relative">
      {/* Glass/Community Background Effects */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/20 blur-[120px] rounded-full -z-10 translate-x-1/2 -translate-y-1/2"></div>
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-blue-500/20 blur-[120px] rounded-full -z-10 -translate-x-1/2 translate-y-1/2"></div>

      <div className="mx-auto max-w-7xl px-6 py-24">
        <a href="/" className="text-sm text-text-muted hover:text-text transition-colors mb-12 inline-block">
          ← Return Home
        </a>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 mb-24">
          <div>
            <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
              Join the<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-blue-500">
                Collective.
              </span>
            </h1>
            <p className="text-xl text-text-muted leading-relaxed max-w-lg">
              Prep is built for developers, by developers. We&apos;re building the future of 
              structured context together.
            </p>
          </div>
          <div className="flex flex-col justify-center items-start space-y-4">
             {/* Stats or Social Proof could go here */}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-24">
          {/* GitHub Discussions - Primary */}
          <div className="group relative rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-8 hover:bg-white/10 transition-all duration-300 shadow-2xl shadow-black/5 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-8">
                <span className="px-3 py-1 rounded-full bg-primary/20 text-primary text-xs font-bold uppercase tracking-widest">Discussion Hub</span>
                <span className="text-primary opacity-50">↗</span>
              </div>
              <h3 className="text-3xl font-bold mb-4">GitHub Discussions</h3>
              <p className="text-lg text-text-muted mb-8">
                The central town square. Ask questions, share workflows, vote on RFCs, and connect with other users.
              </p>
              <Button asChild size="lg" className="rounded-full w-full sm:w-auto">
                <a href={`${GITHUB_URL}/discussions`} target="_blank" rel="noopener noreferrer">
                  Join the Conversation
                </a>
              </Button>
            </div>
          </div>

          {/* GitHub Issues - Secondary */}
          <div className="group relative rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-8 hover:bg-white/10 transition-all duration-300 shadow-2xl shadow-black/5">
             <div className="relative z-10">
              <div className="flex items-center justify-between mb-8">
                <span className="px-3 py-1 rounded-full bg-surface text-text-muted text-xs font-bold uppercase tracking-widest">Issue Tracker</span>
                <span className="text-text-muted opacity-50">↗</span>
              </div>
              <h3 className="text-3xl font-bold mb-4">Report & Request</h3>
              <p className="text-lg text-text-muted mb-8">
                Found a bug? Need a specific feature? Open an issue on our tracker. We prioritize based on community needs.
              </p>
              <Button asChild variant="outline" size="lg" className="rounded-full w-full sm:w-auto border-white/10 hover:bg-white/5">
                <a href={`${GITHUB_URL}/issues`} target="_blank" rel="noopener noreferrer">
                  Open an Issue
                </a>
              </Button>
            </div>
          </div>
        </div>

        {/* Ways to Contribute */}
        <section className="mb-24">
          <h2 className="text-3xl font-bold mb-12 text-center">How to Contribute</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-8 rounded-2xl bg-surface/50 border border-border">
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-6 text-primary text-xl">🐛</div>
              <h3 className="text-xl font-bold mb-2">Edge Cases</h3>
              <p className="text-text-muted leading-relaxed">
                Prep parses dozens of languages. If your codebase triggers weird behavior, your bug report helps everyone.
              </p>
            </div>
            <div className="p-8 rounded-2xl bg-surface/50 border border-border">
              <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center mb-6 text-blue-500 text-xl">💡</div>
              <h3 className="text-xl font-bold mb-2">Workflows</h3>
              <p className="text-text-muted leading-relaxed">
                Share your &quot;Prep Stack&quot; — which models, prompts, and IDE setups are you using? We feature the best ones.
              </p>
            </div>
            <div className="p-8 rounded-2xl bg-surface/50 border border-border">
              <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center mb-6 text-green-500 text-xl">✍️</div>
              <h3 className="text-xl font-bold mb-2">Content</h3>
              <p className="text-text-muted leading-relaxed">
                Written a blog post or made a video? Let us know. We love to signal-boost community content.
              </p>
            </div>
          </div>
        </section>

        <div className="flex flex-wrap justify-center gap-4">
          <Button asChild variant="ghost" className="rounded-full">
            <a href="/contact">Help Center</a>
          </Button>
          <Button asChild variant="ghost" className="rounded-full">
            <a href="/contact">Contact Team</a>
          </Button>
          <Button asChild variant="ghost" className="rounded-full">
            <a href="/blog">Read Blog</a>
          </Button>
        </div>
      </div>
    </main>
  );
}

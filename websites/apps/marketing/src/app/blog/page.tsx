"use client";

import { Button, XIcon } from '@prep/ui';
import { Github } from 'lucide-react';
import { GITHUB_REPO_URL } from '@/lib/links';
import { BLOG_POSTS } from '../../config/blog';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text selection:bg-primary/20">
      <div className="mx-auto max-w-7xl px-6 py-24">

        {/* Nav */}
        <div className="mb-20 font-mono text-xs tracking-widest uppercase text-text-subtle">
          <a href="/" className="hover:text-primary hover:underline underline-offset-4 transition-all">
            ← Return to Base
          </a>
        </div>

        {/* Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 mb-32">
          <div className="lg:col-span-7 relative z-10">
            <h1 className="text-7xl md:text-9xl font-bold tracking-tight leading-[0.85] text-text">
              The<br/>
              <span className="italic text-primary">Context</span><br/>
              Log.
            </h1>
          </div>
          <div className="lg:col-span-5 flex flex-col justify-end items-start relative">
            <div className="absolute top-0 right-0 w-32 h-32 rounded-full bg-primary/10 blur-3xl -z-10"></div>
            <p className="font-mono text-sm md:text-base leading-relaxed text-text-muted max-w-md border-l-2 border-primary pl-6 py-2">
              Notes on the intersection of human creativity and machine intelligence.
              Engineering deep dives, product philosophy, and the future of agentic workflows and epistemic search.
            </p>
          </div>
        </div>

        {/* Featured Post */}
        <div className="mb-32 relative">
          {BLOG_POSTS.filter(p => p.featured).map(post => (
            <div key={post.slug} className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              <div className="lg:col-span-8 relative">
                <div className="absolute -inset-4 bg-surface/50 rounded-2xl -rotate-1 border border-border-subtle z-0"></div>
                <div className="relative bg-surface border border-border rounded-2xl p-8 md:p-12 shadow-lg z-10 hover:-translate-y-1 transition-transform cursor-pointer">
                   <div className="font-mono text-xs text-primary mb-4 uppercase tracking-widest">{post.date}</div>
                   <h2 className="text-4xl md:text-6xl font-bold mb-6 leading-tight hover:underline decoration-2 underline-offset-4 decoration-primary">
                     {post.title}
                   </h2>
                   <p className="font-mono text-sm md:text-base text-text-muted leading-relaxed max-w-2xl">
                     {post.excerpt}
                   </p>
                   <div className="mt-8 flex gap-2">
                     {post.tags.map(tag => (
                       <span key={tag} className="px-3 py-1 rounded-full border border-border text-xs font-bold uppercase bg-background">
                         {tag}
                       </span>
                     ))}
                   </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Recent Posts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-16 mb-24">
          <div className="md:col-span-2 mb-8 border-b border-border pb-4 flex justify-between items-end">
            <h3 className="text-3xl font-bold italic">Recent Signals</h3>
            <span className="font-mono text-xs text-text-subtle">ARCHIVE_ACCESS</span>
          </div>

          {BLOG_POSTS.filter(p => !p.featured).map((post, idx) => (
            <div
              key={post.slug}
              className={`
                group relative flex flex-col items-start
                ${idx % 2 === 1 ? 'md:mt-24' : ''}
              `}
            >
              <div className="w-full bg-surface border border-border p-8 rounded-lg hover:rounded-2xl transition-all duration-300 hover:shadow-lg hover:border-primary/30">
                <div className="flex justify-between items-center mb-6">
                  <span className="font-mono text-xs text-text-subtle">{post.date}</span>
                  <span className="font-mono text-xs uppercase text-primary">{post.author}</span>
                </div>
                <div className="flex gap-4 mb-4">
                  <a href="https://x.com/Prep_io" className="text-text-subtle hover:text-text transition-colors">
                    <XIcon className="w-5 h-5" />
                  </a>
                  <a href={GITHUB_REPO_URL} className="text-text-subtle hover:text-text transition-colors">
                    <Github className="w-5 h-5" />
                  </a>
                </div>
                <h3 className="text-3xl font-bold mb-4 leading-tight group-hover:text-primary transition-colors">
                  {post.title}
                </h3>
                <p className="font-mono text-sm text-text-muted mb-6 leading-relaxed">
                  {post.excerpt}
                </p>
                <Button asChild variant="outline" className="rounded-full">
                  <a>Coming soon</a>
                </Button>
              </div>
            </div>
          ))}
        </div>

        {/* Newsletter CTA */}
        <div className="relative mt-32 max-w-4xl mx-auto text-center">
          <div className="bg-surface border-2 border-dashed border-border p-12 md:p-24 rounded-2xl">
            <h3 className="text-4xl md:text-5xl font-bold mb-6">Stay in the loop.</h3>
            <p className="font-mono text-text-muted mb-8 max-w-lg mx-auto">
              We write about once a month. No spam, just updates on the structural web.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center max-w-md mx-auto">
               <Button asChild>
                 <a href="https://x.com/Prep_io">Follow on X</a>
               </Button>
               <Button asChild variant="outline">
                 <a href="/rss">RSS Feed</a>
               </Button>
            </div>
          </div>
        </div>

      </div>
    </main>
  );
}

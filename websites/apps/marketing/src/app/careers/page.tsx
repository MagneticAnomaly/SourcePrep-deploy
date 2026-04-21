"use client";

import { Button } from '@prep/ui';

interface JobListing {
  id: string;
  title: string;
  department: string;
  location: string;
  type: 'Full-time' | 'Part-time' | 'Contract';
  description: string;
  requirements: string[];
}

const OPEN_POSITIONS: JobListing[] = [
  {
    id: 'eng-001',
    title: 'Senior Rust Engineer — Engine Core',
    department: 'Engineering',
    location: 'Remote (US / EU)',
    type: 'Full-time',
    description:
      'CoDRAG\'s indexing engine is migrating from Python to Rust for 10–50x performance gains on developer machines. You\'ll build the Rust core — parallel file walking, tree-sitter multi-language parsing (Python, TypeScript, Go, Rust, Java, C/C++), in-memory trace graph, and sub-200ms incremental rebuilds — exposed to the Python daemon via PyO3.',
    requirements: [
      'Strong Rust experience (2+ years production)',
      'Familiarity with tree-sitter, compiler internals, or AST parsing',
      'Experience with PyO3 or other FFI bridging (Python ↔ native)',
      'Comfort with performance profiling and memory-efficient data structures',
      'Bonus: experience with the ignore crate, rayon, petgraph, or language servers',
    ],
  },
  {
    id: 'eng-002',
    title: 'Full-Stack Engineer — Dashboard & Desktop App',
    department: 'Engineering',
    location: 'Remote (US / EU)',
    type: 'Full-time',
    description:
      'Own the CoDRAG desktop experience built with Tauri + React. Design and implement the modular dashboard, project management UI, and real-time build status. Ship features that developers interact with daily.',
    requirements: [
      'Strong TypeScript + React experience',
      'Experience with Tauri, Electron, or native desktop frameworks',
      'Eye for developer UX — you\'ve built tools developers love',
      'Bonus: experience with Storybook, design systems, or Tailwind',
    ],
  },
  {
    id: 'eng-003',
    title: 'Developer Advocate',
    department: 'Developer Relations',
    location: 'Remote',
    type: 'Contract',
    description:
      'Help developers understand why structured context matters for AI-assisted development. Write tutorials, create demos, engage with the community, and represent CoDRAG at conferences and in online developer spaces.',
    requirements: [
      'Published technical writing (blog posts, docs, or tutorials)',
      'Active presence in developer communities',
      'Hands-on experience with AI coding tools (Cursor, Windsurf, Copilot)',
      'Bonus: experience with MCP, RAG, or code intelligence tools',
    ],
  },
];

export default function Page() {
  const departments = [...new Set(OPEN_POSITIONS.map((j) => j.department))];

  return (
    <main className="min-h-screen bg-background text-text">
      {/* Swiss Minimal / International Style Layout */}
      <div className="mx-auto max-w-7xl px-6 py-24">
        
        {/* Header - Massive Scale */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 mb-32 border-t-4 border-primary pt-8">
          <div className="lg:col-span-8">
            <h1 className="text-6xl md:text-8xl font-bold tracking-tighter leading-[0.9] mb-8">
              Work<br />With<br />Context.
            </h1>
          </div>
          <div className="lg:col-span-4 flex flex-col justify-end pb-2">
            <p className="text-xl md:text-2xl font-medium leading-tight text-text-muted">
              We&apos;re building the structural layer for AI code intelligence. 
              Epistemic. Sophisticated. Honest.
            </p>
          </div>
        </div>

        {/* Values - Grid System */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mb-32 border-t border-border pt-8">
          <div className="space-y-4">
            <h3 className="text-sm font-mono uppercase tracking-widest text-primary">01 &mdash; Remote</h3>
            <p className="text-lg font-medium">Work from anywhere. Async first. Deep work prioritized over meetings.</p>
          </div>
          <div className="space-y-4">
            <h3 className="text-sm font-mono uppercase tracking-widest text-primary">02 &mdash; Impact</h3>
            <p className="text-lg font-medium">Small team, massive leverage. Every commit ships to users.</p>
          </div>
          <div className="space-y-4">
            <h3 className="text-sm font-mono uppercase tracking-widest text-primary">03 &mdash; Ownership</h3>
            <p className="text-lg font-medium">Own your features from RFC to production. No busywork.</p>
          </div>
        </div>

        {/* Positions - Swiss List */}
        <div className="space-y-0">
          <div className="flex items-center justify-between border-b-2 border-text py-4 mb-8">
            <h2 className="text-4xl font-bold tracking-tight">Open Positions</h2>
            <span className="font-mono text-sm">{OPEN_POSITIONS.length} ROLES AVAILABLE</span>
          </div>

          <div className="mb-12 p-4 border border-text bg-surface-muted">
            <p className="font-mono text-sm text-text-muted">
              <strong>NOTE:</strong> We are not actively hiring at this exact moment, but we are always interested in connecting with exceptional engineers for future roles. Feel free to reach out.
            </p>
          </div>

          {departments.map((dept) => (
            <div key={dept} className="mb-16">
              <h3 className="font-mono text-sm uppercase tracking-widest text-text-muted mb-6">{dept}</h3>
              <div className="space-y-0">
                {OPEN_POSITIONS.filter((j) => j.department === dept).map((job) => (
                  <div
                    key={job.id}
                    className="group border-t border-border py-8 grid grid-cols-1 lg:grid-cols-12 gap-8 hover:bg-surface transition-colors"
                  >
                    <div className="lg:col-span-4">
                      <h4 className="text-2xl font-bold group-hover:text-primary transition-colors">{job.title}</h4>
                      <div className="flex gap-2 mt-2 font-mono text-xs text-text-muted">
                        <span>{job.type.toUpperCase()}</span>
                        <span>/</span>
                        <span>{job.location.toUpperCase()}</span>
                      </div>
                    </div>
                    <div className="lg:col-span-5">
                      <p className="text-lg leading-relaxed text-text-muted">{job.description}</p>
                    </div>
                    <div className="lg:col-span-3 flex items-start justify-end">
                      <Button asChild variant="outline" className="rounded-none border-2">
                        <a href={`mailto:careers@codrag.io?subject=${encodeURIComponent(job.title + ' — ' + job.id)}`}>
                          Apply &rarr;
                        </a>
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer CTA */}
        <div className="mt-24 border-t border-border pt-12 grid grid-cols-1 lg:grid-cols-12 gap-8">
           <div className="lg:col-span-8">
             <h3 className="text-3xl font-bold mb-4">Don&apos;t see a fit?</h3>
             <p className="text-xl text-text-muted">
               We&apos;re always looking for exceptional talent. If you have a unique skill set 
               that aligns with our mission, pitch us a role.
             </p>
           </div>
           <div className="lg:col-span-4 flex items-center justify-end">
             <Button asChild size="lg" className="rounded-none text-lg px-8 py-6">
                <a href="mailto:careers@codrag.io?subject=General Application">Get in Touch</a>
             </Button>
           </div>
        </div>

      </div>
    </main>
  );
}

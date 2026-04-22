"use client";

import { DetailPageLayout } from '@prep/ui';
import { Shield, BookOpen, AlertTriangle, CheckCircle, ArrowRight, RefreshCw } from 'lucide-react';

const SECTIONS = [
  { id: 'how', label: 'How It Works' },
  { id: 'concepts', label: 'Concepts' },
  { id: 'antibodies', label: 'Assertions & Antibodies' },
  { id: 'alerts', label: 'Violation Alerts' },
  { id: 'living', label: 'Living Architecture' },
];

export default function ImmuneSystemPage() {
  return (
    <DetailPageLayout
      title="Immune System"
      subtitle="Architectural Guardrails"
      description="Design decisions become runtime defenses. Record the 'why' behind your architecture, and SourcePrep enforces it automatically."
      badge="Unique"
      sections={SECTIONS}
      docsUrl="https://docs.sourceprep.io/concepts/immune-system"
      docsLabel="Concepts & antibodies guide"
    >
      {/* How It Works */}
      <section id="how">
        <h2 className="text-2xl font-semibold text-text mb-4">How It Works</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          SourcePrep's immune system derives runtime architectural defenses from your recorded design decisions.
          When a team records a concept like "the payment module must never import db.transaction directly,"
          SourcePrep creates a testable assertion that generates an antibody — a runtime check that fires when
          the constraint is violated. All alerts are informational; nothing is blocked.
        </p>
        <div className="grid sm:grid-cols-4 gap-4">
          {[
            { icon: <BookOpen className="w-5 h-5" />, title: 'Record Concept', desc: 'Document a design decision or architectural constraint' },
            { icon: <CheckCircle className="w-5 h-5" />, title: 'Derive Assertion', desc: 'SourcePrep extracts a testable rule from the concept' },
            { icon: <Shield className="w-5 h-5" />, title: 'Create Antibody', desc: 'A pattern-matching guard is automatically registered' },
            { icon: <AlertTriangle className="w-5 h-5" />, title: 'Surface Alerts', desc: 'Violations appear in ambient context before work starts' },
          ].map((step) => (
            <div key={step.title} className="rounded-lg border border-border bg-surface p-4">
              <div className="text-primary mb-2">{step.icon}</div>
              <h3 className="font-medium text-sm text-text mb-1">{step.title}</h3>
              <p className="text-xs text-text-muted">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Concepts */}
      <section id="concepts">
        <h2 className="text-2xl font-semibold text-text mb-4">Concepts: The Foundation</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Concepts are recorded business rationale, design decisions, and architectural constraints. Each concept
          has a category (architecture, domain, security, constraint, decision, etc.), can be anchored to specific
          files, and can link to documentation. Constraint concepts are the seed of the immune system.
        </p>
        <div className="rounded-lg border border-border bg-[#0d1117] p-5 font-mono text-sm">
          <div className="text-[#8b949e] mb-3">{"// Example concept stored in SourcePrep"}</div>
          <div className="space-y-1.5">
            <div>
              <span className="text-[#79c0ff]">title</span>
              <span className="text-[#8b949e]">: </span>
              <span className="text-[#a5d6ff]">"Payment Saga Architecture"</span>
            </div>
            <div>
              <span className="text-[#79c0ff]">category</span>
              <span className="text-[#8b949e]">: </span>
              <span className="text-[#3fb950]">architecture</span>
            </div>
            <div>
              <span className="text-[#79c0ff]">assertion</span>
              <span className="text-[#8b949e]">: </span>
              <span className="text-[#ffa657]">"payment/ must not import db.transaction directly"</span>
            </div>
            <div className="mt-3">
              <span className="text-[#8b949e]">anchors</span>
              <span className="text-[#8b949e]">:</span>
            </div>
            <div className="pl-4 text-[#8b949e]">
              - <span className="text-[#a5d6ff]">services/payment.py</span>
            </div>
            <div className="pl-4 text-[#8b949e]">
              - <span className="text-[#a5d6ff]">services/saga_runner.py</span>
            </div>
          </div>
        </div>
        <p className="text-sm text-text-muted mt-4">
          Concepts with an <code className="text-primary font-mono">assertion</code> field automatically become
          immune system seeds. SourcePrep reads the assertion, derives a pattern rule, and registers an antibody.
          No extra configuration required.
        </p>
      </section>

      {/* Assertions & Antibodies */}
      <section id="antibodies">
        <h2 className="text-2xl font-semibold text-text mb-4">Assertions &amp; Antibodies</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          When a concept has a testable assertion, SourcePrep auto-derives an antibody from it. Antibodies are
          pattern-matching rules that evaluate against code changes. They carry a status to support gradual
          rollout.
        </p>
        <div className="grid sm:grid-cols-3 gap-4 mb-6">
          {[
            { status: 'active', color: 'text-[#3fb950]', border: 'border-[#3fb950]/30', bg: 'bg-[#3fb950]/5', desc: 'Fires and surfaces alerts in ambient context' },
            { status: 'testing', color: 'text-[#ffa657]', border: 'border-[#ffa657]/30', bg: 'bg-[#ffa657]/5', desc: 'Fires internally for observation, not yet surfaced' },
            { status: 'disabled', color: 'text-[#8b949e]', border: 'border-[#8b949e]/30', bg: 'bg-[#8b949e]/5', desc: 'Paused — concept still exists, guard is off' },
          ].map((item) => (
            <div key={item.status} className={`rounded-lg border ${item.border} ${item.bg} p-4`}>
              <span className={`font-mono text-xs font-bold ${item.color}`}>{item.status.toUpperCase()}</span>
              <p className="text-xs text-text-muted mt-1">{item.desc}</p>
            </div>
          ))}
        </div>
        <div className="rounded-lg border border-border bg-surface p-5">
          <h3 className="text-sm font-semibold text-text mb-4">Derivation Flow</h3>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-0">
            <div className="flex-1 rounded border border-border bg-background px-4 py-2 text-center text-xs text-text-muted">
              <div className="font-semibold text-text text-sm">Concept</div>
              <div className="mt-0.5">"Payment Saga Architecture"</div>
            </div>
            <ArrowRight className="w-4 h-4 text-text-muted mx-3 shrink-0" />
            <div className="flex-1 rounded border border-border bg-background px-4 py-2 text-center text-xs text-text-muted">
              <div className="font-semibold text-text text-sm">Assertion</div>
              <div className="mt-0.5">payment/ must not import db.transaction</div>
            </div>
            <ArrowRight className="w-4 h-4 text-text-muted mx-3 shrink-0" />
            <div className="flex-1 rounded border border-primary/30 bg-primary/5 px-4 py-2 text-center text-xs text-text-muted">
              <div className="font-semibold text-primary text-sm">Antibody</div>
              <div className="mt-0.5">pattern rule — auto-derived, status: active</div>
            </div>
          </div>
        </div>
      </section>

      {/* Violation Alerts */}
      <section id="alerts">
        <h2 className="text-2xl font-semibold text-text mb-4">Violation Alerts</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          When an antibody detects a violation — such as a new import that breaks a constraint — it surfaces
          in the <code className="text-primary font-mono text-sm">prep()</code> ambient context call. Your AI
          agent sees the alert before it starts work, so it can address the violation with full architectural
          understanding.
        </p>
        <div className="rounded-lg border border-border bg-[#0d1117] p-5 font-mono text-sm mb-4">
          <div className="text-[#8b949e] mb-3">{"// Surfaced in prep() ambient context:"}</div>
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-[#ffa657] mt-0.5 shrink-0" />
            <div>
              <span className="text-[#ffa657]">IMMUNE</span>
              <span className="text-[#8b949e]">: </span>
              <span className="text-[#f0f6fc]">payment/checkout.py</span>
              <span className="text-[#8b949e]"> imports </span>
              <span className="text-[#f0f6fc]">db.transaction</span>
            </div>
          </div>
          <div className="pl-6 mt-1 text-[#8b949e] text-xs">
            violates <span className="text-[#a5d6ff]">'Payment Saga Architecture'</span>
          </div>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            { label: 'Concept reference', desc: 'Links back to the recorded design decision that was violated' },
            { label: 'Violating file', desc: 'Exact file path that introduced the constraint break' },
            { label: 'Trigger detail', desc: 'Precisely what triggered the antibody (import, call, pattern)' },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-border bg-surface px-4 py-3">
              <span className="font-mono text-xs font-semibold text-primary">{item.label}</span>
              <p className="text-xs text-text-muted mt-1">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Living Architecture */}
      <section id="living">
        <h2 className="text-2xl font-semibold text-text mb-4">Living Architecture</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          The immune system evolves with your codebase. New concepts create new antibodies. Updated concepts
          update their antibodies. Removed constraints remove their defenses. It is a living set of architectural
          rules — not a static linter config you have to maintain separately.
        </p>
        <div className="space-y-3 mb-8">
          {[
            { icon: <BookOpen className="w-4 h-4" />, label: 'New concept', action: 'Antibody auto-derived and activated' },
            { icon: <RefreshCw className="w-4 h-4" />, label: 'Updated concept', action: 'Antibody rule refreshed to match new assertion' },
            { icon: <Shield className="w-4 h-4" />, label: 'Removed concept', action: 'Antibody deactivated — no orphaned guards' },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3">
              <div className="text-primary shrink-0">{item.icon}</div>
              <span className="font-mono text-xs font-semibold text-text w-36 shrink-0">{item.label}</span>
              <span className="text-sm text-text-muted">{item.action}</span>
            </div>
          ))}
        </div>
        <p className="text-text-muted text-sm mb-6">
          No competitor offers this. Static linters require you to encode rules in config files. SourcePrep derives
          guards from the design decisions your team already records — so your architectural intent and its
          enforcement stay in sync automatically.
        </p>
        <a
          href="https://docs.sourceprep.io/concepts/immune-system"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-background hover:bg-primary-hover transition-colors"
        >
          Concepts &amp; antibodies guide <ArrowRight className="w-4 h-4" />
        </a>
      </section>
    </DetailPageLayout>
  );
}

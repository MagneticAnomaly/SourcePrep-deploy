"use client";

import { useEffect, useState } from "react";
import { Button } from '@codrag/ui';
import {
  type PPPBand,
  getBand,
  formatPrice,
  getCheckoutUrl,
  LS_CHECKOUT_URLS,
  PPP_PRICES,
  DEFAULT_PPP_BAND,
} from "../../lib/pricing";

/** Read visitor country from cookie (set by edge function) or URL param (dev/testing). */
function detectCountry(): string {
  if (typeof window === "undefined") return "";

  // Dev override: ?country=IN
  const params = new URLSearchParams(window.location.search);
  const override = params.get("country");
  if (override) return override.toUpperCase();

  // Production: cookie set by Netlify Edge Function
  const match = document.cookie.match(/(?:^|; )visitor_country=([A-Z]{2})/);
  return match ? match[1] : "";
}

export default function Page() {
  const [country, setCountry] = useState("");
  const [band, setBand] = useState<PPPBand>(DEFAULT_PPP_BAND);

  useEffect(() => {
    const c = detectCountry();
    setCountry(c);
    setBand(getBand(c));
  }, []);

  const prices = PPP_PRICES[band];

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted hover:text-text transition-colors">
          ← Home
        </a>

        <div className="mt-12 text-center max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Simple, honest pricing
          </h1>
          <p className="mt-6 text-xl text-text-muted leading-relaxed">
            Local-first means your code stays yours. CoDRAG ships with built-in ONNX embeddings —
            semantic search works out of the box, no LLM required. Subscribe monthly or pay once and own it forever.
          </p>
        </div>

        {/* Pricing grid */}
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {/* Free */}
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col">
            <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Free</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-text-muted ml-1">forever</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Try CoDRAG on a single project. See how much better your AI output gets.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>1 active project</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Semantic search + structural code graph</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Context assembly + path weights</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>MCP integration (Cursor, Windsurf, etc.)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Dashboard GUI</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-text-subtle mt-0.5">&#10005;</span>
                <span className="text-text-muted">Manual builds only (no auto-rebuild or scheduling)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Smart context compression (code &amp; docs)</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              <a href="/download">Download Free</a>
            </Button>
          </div>

          {/* Pro Monthly */}
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col">
            <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Pro <span className="text-text-subtle font-normal normal-case">— monthly</span></div>
            <div className="mt-3">
              <span className="text-4xl font-bold">{formatPrice(prices.monthly)}</span>
              <span className="text-text-muted ml-1">/ month</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Full feature access, billed monthly. Cancel anytime.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Unlimited projects</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Full automation (watcher, scheduling, pipelines)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Full MCP suite + trace-aware context expansion</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Multi-repo agent support</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>9-stage graph enrichment pipeline</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-text-subtle mt-0.5">&#8594;</span>
                <span className="text-text-muted">Switch to one-time payment anytime to own it outright</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              <a href={getCheckoutUrl(LS_CHECKOUT_URLS.monthly, country)}>Start Monthly</a>
            </Button>
          </div>

          {/* Pro Perpetual — highlighted */}
          <div className="rounded-xl border-2 border-primary bg-gradient-to-br from-primary/5 to-transparent p-6 flex flex-col relative">
            <div className="absolute -top-3 right-4 bg-primary text-background text-xs font-bold px-3 py-1 rounded-full">
              Best Value
            </div>
            <div className="text-sm font-semibold text-primary uppercase tracking-wide">Pro <span className="font-normal normal-case">— one-time</span></div>
            <div className="mt-3">
              <span className="text-4xl font-bold">{formatPrice(prices.perpetual)}</span>
              <span className="text-text-muted ml-1">one-time</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Buy it once. Own it forever. Every feature, no expiry.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span><strong>All Pro features</strong></span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>No recurring fee — one payment, yours forever</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Offline activation (no internet required after activation)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Free updates for the life of the major version</span>
              </li>
            </ul>
            <Button asChild className="mt-6 w-full">
              <a href={getCheckoutUrl(LS_CHECKOUT_URLS.perpetual, country)}>Get Pro — One-Time</a>
            </Button>
          </div>
        </div>

        {/* Team + Enterprise row */}
        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          <div className="rounded-xl border border-border bg-surface p-6">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Team</div>
              <div>
                <span className="text-2xl font-bold">{formatPrice(prices.team)}</span>
                <span className="text-text-muted text-sm ml-1">/ seat / month</span>
              </div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Shared configuration, centralized policy, and license management for engineering teams.
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Everything in Pro, plus team management</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Centralized configuration & shared context layers</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>License management dashboard</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-4">
              <a href={getCheckoutUrl(LS_CHECKOUT_URLS.team, country)}>Start Team Trial</a>
            </Button>
          </div>

          <div className="rounded-xl border border-border bg-surface p-6">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Enterprise</div>
              <div className="text-2xl font-bold">Custom</div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              For organizations that need air-gapped deployment, SSO/SCIM, audit logging,
              and procurement-ready terms.
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Everything in Team, plus enterprise controls</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Air-gapped / on-premise deployment</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>SSO, SCIM, and audit logging</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-4">
              <a href="/contact">Contact Sales</a>
            </Button>
          </div>
        </div>

        {/* Trust strip */}
        <div className="mt-16 text-center space-y-4">
          <h2 className="text-xl font-semibold">Every plan includes</h2>
          <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-text-muted">
            <span>Local-first — your code stays on your machine</span>
            <span>Built-in embeddings — add Ollama or BYOK cloud for enrichment</span>
            <span>macOS & Windows</span>
            <span>MCP integration</span>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Button asChild variant="outline">
            <a href="/security">Security &amp; Privacy</a>
          </Button>
          <Button asChild variant="outline">
            <a href="/contact">Contact</a>
          </Button>
        </div>

        <p className="mt-8 text-center text-xs text-text-muted max-w-lg mx-auto">
          All prices in USD. Checkout displays your local currency automatically.
        </p>
      </div>
    </main>
  );
}

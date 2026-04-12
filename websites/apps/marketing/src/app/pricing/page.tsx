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

const IS_BETA_MODE = true;

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
          {IS_BETA_MODE && (
            <div className="mb-6 inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <span className="relative flex h-2 w-2 mr-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              CoDRAG is currently in closed beta. Prices below indicate our upcoming structure.
            </div>
          )}
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Simple, honest pricing
          </h1>
          <p className="mt-6 text-xl text-text-muted leading-relaxed">
            Private by design. Sovereign context. CoDRAG ships with built-in ONNX embeddings —
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
              Try CoDRAG on up to 3 projects. Experience the magic of real-time structural intelligence.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>3 active projects</span>
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
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Full automation (watcher, scheduling, pipelines)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Smart context compression (code &amp; docs)</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              {IS_BETA_MODE ? (
                <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request%20-%20Free%20Tier">Join Free Beta</a>
              ) : (
                <a href="/download">Download Free</a>
              )}
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
              {IS_BETA_MODE ? (
                <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request%20-%20Pro%20Monthly%20Tier">Request Beta Access</a>
              ) : (
                <a href={getCheckoutUrl(LS_CHECKOUT_URLS.monthly, country)}>Start Monthly</a>
              )}
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
              {IS_BETA_MODE ? (
                <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request%20-%20Pro%20Perpetual%20Tier">Request Beta Access</a>
              ) : (
                <a href={getCheckoutUrl(LS_CHECKOUT_URLS.perpetual, country)}>Get Pro — One-Time</a>
              )}
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
              Build the trace graph once in CI/CD. Your whole team downloads it instantly.
              Only local changes get re-enriched — no developer runs LLMs.
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span><strong>Everything in Pro</strong>, plus team infrastructure</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Headless CI/CD indexer — runs the 10-stage pipeline on every push to <code className="text-xs bg-surface-raised px-1 py-0.5 rounded">main</code></span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Shared trace graph via S3-compatible storage (R2, S3, MinIO)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Local delta sync — developers only enrich uncommitted changes</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Multi-branch support — separate indexes per branch</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Centralized configuration &amp; policy enforcement</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>License management for your team</span>
              </li>
            </ul>
            <div className="mt-4 flex items-center gap-3">
              <Button asChild variant="outline">
                {IS_BETA_MODE ? (
                  <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request%20-%20Team%20Tier">Request Beta Access</a>
                ) : (
                  <a href={getCheckoutUrl(LS_CHECKOUT_URLS.team, country)}>Start Team Trial</a>
                )}
              </Button>
              <a href="https://docs.codrag.io/guides/team-sync" className="text-xs text-primary hover:underline">
                Setup guide &rarr;
              </a>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-surface p-6">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Enterprise</div>
              <div className="text-2xl font-bold">Custom</div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Deploy inside your own infrastructure. No code leaves your network.
              GPU or CPU images run on any container orchestrator.
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span><strong>Everything in Team</strong>, plus enterprise controls</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Air-gapped deployment — GPU Docker image with baked-in models</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>VPC deployment on AWS ECS, Azure, or your own infrastructure</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>RunPod &amp; Modal adapters for serverless GPU indexing</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>SSO (SAML/OIDC) and SCIM provisioning</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Audit logging and compliance reporting</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Offline license activation — no phone-home required</span>
              </li>
            </ul>
            <div className="mt-4 flex items-center gap-3">
              <Button asChild variant="outline">
                {IS_BETA_MODE ? (
                  <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request%20-%20Enterprise%20Tier">Request Enterprise Beta</a>
                ) : (
                  <a href="/contact">Contact Sales</a>
                )}
              </Button>
              <a href="https://docs.codrag.io/guides/enterprise-deploy" className="text-xs text-primary hover:underline">
                Deployment guide &rarr;
              </a>
            </div>
          </div>
        </div>

        {/* How Team Sync Works */}
        <div className="mt-16 max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-center">How Team Sync Works</h2>
          <p className="mt-4 text-text-muted text-center">
            Your CI/CD builds the enriched trace graph once. Every developer gets it instantly.
          </p>
          <div className="mt-8 grid gap-6 sm:grid-cols-3">
            <div className="text-center">
              <div className="text-3xl">1</div>
              <p className="mt-2 font-semibold">Build once</p>
              <p className="mt-1 text-sm text-text-muted">
                A CI/CD job runs the headless Docker image after every merge. It produces the full
                10-stage enriched trace graph — structural, epistemic, clustered.
              </p>
            </div>
            <div className="text-center">
              <div className="text-3xl">2</div>
              <p className="mt-2 font-semibold">Store centrally</p>
              <p className="mt-1 text-sm text-text-muted">
                Index artifacts are uploaded to your S3-compatible bucket.
                Cloudflare R2 (zero egress), AWS S3, or MinIO all work.
              </p>
            </div>
            <div className="text-center">
              <div className="text-3xl">3</div>
              <p className="mt-2 font-semibold">Sync locally</p>
              <p className="mt-1 text-sm text-text-muted">
                Each developer&apos;s CoDRAG downloads the latest index on startup.
                Only uncommitted changes are re-enriched locally.
              </p>
            </div>
          </div>
        </div>

        <hr className="mt-16 border-border" />

        {/* Trust strip */}
        <div className="mt-16 text-center space-y-4">
          <h2 className="text-xl font-semibold">Every plan includes</h2>
          <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-text-muted">
            <span>Private by Design — your context index is yours to control</span>
            <span>Built-in embeddings — connect to Ollama Cloud or frontier cloud APIs for advanced reasoning</span>
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

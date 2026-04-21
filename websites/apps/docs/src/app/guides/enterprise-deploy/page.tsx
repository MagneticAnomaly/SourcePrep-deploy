import { AnchorHeading } from '../../../components/AnchorHeading';

export const metadata = {
  title: 'Enterprise Deployment Guide — RunPrep Docs',
  description: 'Deploy RunPrep headless indexing inside your own infrastructure: air-gapped, VPC, serverless GPU.',
};

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/guides" className="text-sm text-text-muted">
          ← Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Enterprise Deployment
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          Deploy RunPrep&apos;s headless indexer inside your own cloud infrastructure.
          No code leaves your network. GPU or CPU images run on any container orchestrator.
        </p>
        <p className="mt-2 text-sm text-text-subtle">
          Requires a <strong>Team</strong> or <strong>Enterprise</strong> license.
          See also: <a href="/guides/team-sync" className="text-primary hover:underline">Team Sync Guide</a> for
          the standard CI/CD setup.
        </p>

        <hr className="my-8 border-border" />

        {/* ── Overview ──────────────────────────────────── */}
        <AnchorHeading id="overview" level="h2">Overview</AnchorHeading>

        <p className="mt-4 text-text-muted">
          RunPrep ships two Docker images for headless indexing. Both run the full
          10-stage enrichment pipeline (structural AST parse → epistemic enrichment →
          cluster synthesis → atlas generation) and upload the resulting index to
          S3-compatible storage.
        </p>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-lg overflow-hidden">
            <thead className="bg-surface-raised text-text">
              <tr>
                <th className="px-4 py-2 text-left border-b border-border">Image</th>
                <th className="px-4 py-2 text-left border-b border-border">Size</th>
                <th className="px-4 py-2 text-left border-b border-border">GPU</th>
                <th className="px-4 py-2 text-left border-b border-border">Use case</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr>
                <td className="px-4 py-2 font-mono text-xs border-b border-border">ghcr.io/ericbintner/prep-headless:cpu</td>
                <td className="px-4 py-2 border-b border-border">~2-3 GB</td>
                <td className="px-4 py-2 border-b border-border">No</td>
                <td className="px-4 py-2 border-b border-border">CI runners + BYOK cloud LLM (OpenAI, Anthropic)</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">ghcr.io/ericbintner/prep-headless:gpu</td>
                <td className="px-4 py-2">~8-10 GB</td>
                <td className="px-4 py-2">Yes</td>
                <td className="px-4 py-2">Air-gapped / VPC with local Ollama + Qwen3</td>
              </tr>
            </tbody>
          </table>
        </div>

        <hr className="my-8 border-border" />

        {/* ── Air-Gapped ────────────────────────────────── */}
        <AnchorHeading id="air-gapped" level="h2">Air-Gapped Deployment</AnchorHeading>

        <p className="mt-4 text-text-muted">
          The <code>:gpu</code> image includes Ollama and a pre-baked Qwen3:4b model.
          No network access is required after the image is pulled. This is suitable for
          regulated environments where source code cannot leave the network.
        </p>

        <AnchorHeading id="air-gapped-setup" level="h3">Setup</AnchorHeading>
        <ol className="mt-2 list-decimal list-inside space-y-2 text-text-muted">
          <li>Pull the GPU image to your internal registry:
            <pre className="mt-1 mb-1 overflow-x-auto rounded bg-surface-raised px-3 py-2 text-xs font-mono">
{`docker pull ghcr.io/ericbintner/prep-headless:gpu
docker tag ghcr.io/ericbintner/prep-headless:gpu registry.internal/prep:gpu
docker push registry.internal/prep:gpu`}
            </pre>
          </li>
          <li>Run with GPU access:
            <pre className="mt-1 mb-1 overflow-x-auto rounded bg-surface-raised px-3 py-2 text-xs font-mono">
{`docker run --gpus all \\
  -e PREP_S3_ENDPOINT=https://minio.internal:9000 \\
  -e PREP_S3_BUCKET=prep-indexes \\
  -e PREP_S3_ACCESS_KEY=\$ACCESS_KEY \\
  -e PREP_S3_SECRET_KEY=\$SECRET_KEY \\
  -v /mnt/repos/my-project:/workspace \\
  registry.internal/prep:gpu \\
  sync-headless \\
    --repo-path /workspace \\
    --model-provider local \\
    --model-name qwen3:4b \\
    --embedder native`}
            </pre>
          </li>
          <li>The entrypoint script automatically starts Ollama in the background when <code>--model-provider local</code> is specified.</li>
        </ol>

        <AnchorHeading id="air-gapped-models" level="h3">Using Larger Models</AnchorHeading>
        <p className="mt-2 text-text-muted">
          The default image includes <code>qwen3:4b</code> (~2.5 GB). For better enrichment quality on large codebases,
          you can bake a larger model into a custom image:
        </p>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-raised p-4 text-xs font-mono text-text border border-border">
{`FROM ghcr.io/ericbintner/prep-headless:gpu
RUN ollama serve & sleep 3 && ollama pull qwen3:8b && kill %1 || true`}
        </pre>

        <hr className="my-8 border-border" />

        {/* ── AWS ────────────────────────────────────────── */}
        <AnchorHeading id="aws" level="h2">AWS ECS / Fargate</AnchorHeading>

        <p className="mt-4 text-text-muted">
          Run the headless indexer as an ECS task with GPU support.
          A reference task definition is provided in the{' '}
          <a href="https://github.com/MagneticAnomaly/prep-deploy" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
            prep-deploy
          </a>{' '}
          repository under <code>aws/</code>.
        </p>

        <ul className="mt-4 list-disc list-inside space-y-1 text-text-muted">
          <li>Use <code>p3.2xlarge</code> or <code>g4dn.xlarge</code> instance types for GPU tasks.</li>
          <li>Storage: Internal S3 with IAM role auth (no static keys needed).</li>
          <li>Trigger via EventBridge rule on CodeCommit/CodePipeline events or GitHub webhook.</li>
          <li>For CPU-only: any Fargate task type works (no GPU instance required).</li>
        </ul>

        <hr className="my-8 border-border" />

        {/* ── Azure ──────────────────────────────────────── */}
        <AnchorHeading id="azure" level="h2">Azure</AnchorHeading>

        <p className="mt-4 text-text-muted">
          Use Azure Container Apps with GPU profiles or Azure ML Processing Jobs.
        </p>
        <ul className="mt-4 list-disc list-inside space-y-1 text-text-muted">
          <li>Storage: Azure Blob Storage (S3-compatible via <code>PREP_S3_ENDPOINT</code>).</li>
          <li>Auth: Managed Identity or connection string in Key Vault.</li>
          <li>Trigger: Azure DevOps pipeline or GitHub Actions webhook.</li>
        </ul>

        <hr className="my-8 border-border" />

        {/* ── Serverless GPU ─────────────────────────────── */}
        <AnchorHeading id="serverless-gpu" level="h2">Serverless GPU (RunPod / Modal)</AnchorHeading>

        <p className="mt-4 text-text-muted">
          For teams that want GPU-powered indexing without managing infrastructure.
          Both RunPod and Modal scale to zero when idle, so you only pay for actual indexing time.
        </p>

        <AnchorHeading id="modal" level="h3">Modal</AnchorHeading>
        <ol className="mt-2 list-decimal list-inside space-y-1 text-text-muted">
          <li>Install the Modal CLI: <code>pip install modal &amp;&amp; modal setup</code></li>
          <li>Save your S3 credentials as a Modal Secret named <code>prep-s3-creds</code>.</li>
          <li>Deploy the adapter: <code>modal deploy modal/modal_adapter.py</code></li>
          <li>Copy the webhook URL into your GitHub Action.</li>
        </ol>
        <p className="mt-2 text-xs text-text-subtle">
          Adapter source:{' '}
          <a href="https://github.com/MagneticAnomaly/prep-deploy/tree/main/modal" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
            prep-deploy/modal/
          </a>
        </p>

        <AnchorHeading id="runpod" level="h3">RunPod</AnchorHeading>
        <ol className="mt-2 list-decimal list-inside space-y-1 text-text-muted">
          <li>Build and push the RunPod image:
            <pre className="mt-1 mb-1 overflow-x-auto rounded bg-surface-raised px-3 py-2 text-xs font-mono">
{`docker build -f runpod/Dockerfile.runpod -t my-org/prep-runpod .
docker push my-org/prep-runpod`}
            </pre>
          </li>
          <li>Create a Serverless Endpoint in the RunPod dashboard using your image.</li>
          <li>Set S3 credentials as endpoint environment variables.</li>
          <li>Trigger via GitHub Actions webhook or API call.</li>
        </ol>
        <p className="mt-2 text-xs text-text-subtle">
          Handler source:{' '}
          <a href="https://github.com/MagneticAnomaly/prep-deploy/tree/main/runpod" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
            prep-deploy/runpod/
          </a>
        </p>

        <hr className="my-8 border-border" />

        {/* ── Cost Comparison ────────────────────────────── */}
        <AnchorHeading id="cost" level="h2">Cost Comparison</AnchorHeading>

        <p className="mt-4 text-text-muted">
          Approximate costs for a ~5,000-file codebase with 5 merges/day.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-lg overflow-hidden">
            <thead className="bg-surface-raised text-text">
              <tr>
                <th className="px-4 py-2 text-left border-b border-border">Method</th>
                <th className="px-4 py-2 text-left border-b border-border">Per run</th>
                <th className="px-4 py-2 text-left border-b border-border">Monthly (est.)</th>
                <th className="px-4 py-2 text-left border-b border-border">Privacy</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr>
                <td className="px-4 py-2 border-b border-border">CPU + OpenAI (gpt-4.1-mini)</td>
                <td className="px-4 py-2 border-b border-border">~$8</td>
                <td className="px-4 py-2 border-b border-border">~$1,200</td>
                <td className="px-4 py-2 border-b border-border">Code sent to OpenAI</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border">GPU + Qwen3 (RunPod A4000)</td>
                <td className="px-4 py-2 border-b border-border">~$0.60</td>
                <td className="px-4 py-2 border-b border-border">~$90</td>
                <td className="px-4 py-2 border-b border-border">Fully private</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border">GPU incremental (typical PR)</td>
                <td className="px-4 py-2 border-b border-border">~$0.05</td>
                <td className="px-4 py-2 border-b border-border">~$8</td>
                <td className="px-4 py-2 border-b border-border">Fully private</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Air-gapped (own GPU server)</td>
                <td className="px-4 py-2">$0</td>
                <td className="px-4 py-2">Hardware cost only</td>
                <td className="px-4 py-2">Fully private</td>
              </tr>
            </tbody>
          </table>
        </div>

        <hr className="my-8 border-border" />

        {/* ── Security ───────────────────────────────────── */}
        <AnchorHeading id="security" level="h2">Security Posture</AnchorHeading>

        <ul className="mt-4 list-disc list-inside space-y-2 text-text-muted">
          <li><strong>No telemetry.</strong> RunPrep does not phone home, collect usage data, or send any information to external servers.</li>
          <li><strong>No cloud dependency.</strong> The GPU image includes everything needed to run completely offline.</li>
          <li><strong>Secrets leakage detection.</strong> RunPrep warns if credential-like keys appear in <code>team_config.json</code> (which is committed to Git).</li>
          <li><strong>S3 credentials</strong> are resolved from environment variables or a gitignored <code>.runprep/.secrets</code> file — never from committed files.</li>
          <li><strong>Offline license activation.</strong> Enterprise licenses are Ed25519-signed and validated locally. No internet required after activation.</li>
        </ul>

        <hr className="my-8 border-border" />

        {/* ── Enterprise Features ────────────────────────── */}
        <AnchorHeading id="enterprise-features" level="h2">Enterprise Features</AnchorHeading>

        <p className="mt-4 text-text-muted">
          Enterprise licenses include all Team features plus:
        </p>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-lg overflow-hidden">
            <thead className="bg-surface-raised text-text">
              <tr>
                <th className="px-4 py-2 text-left border-b border-border">Feature</th>
                <th className="px-4 py-2 text-left border-b border-border">Status</th>
                <th className="px-4 py-2 text-left border-b border-border">Description</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr>
                <td className="px-4 py-2 border-b border-border font-medium">Air-gapped deployment</td>
                <td className="px-4 py-2 border-b border-border"><span className="text-success">Available</span></td>
                <td className="px-4 py-2 border-b border-border">GPU Docker image with baked-in models, no internet required</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-medium">VPC deployment</td>
                <td className="px-4 py-2 border-b border-border"><span className="text-success">Available</span></td>
                <td className="px-4 py-2 border-b border-border">AWS ECS, Azure, or any container orchestrator with GPU support</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-medium">Offline licensing</td>
                <td className="px-4 py-2 border-b border-border"><span className="text-success">Available</span></td>
                <td className="px-4 py-2 border-b border-border">Ed25519-signed license files, no phone-home after activation</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-medium">SSO (SAML/OIDC)</td>
                <td className="px-4 py-2 border-b border-border"><span className="text-warning">Roadmap</span></td>
                <td className="px-4 py-2 border-b border-border">Single sign-on integration for identity management</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-medium">SCIM provisioning</td>
                <td className="px-4 py-2 border-b border-border"><span className="text-warning">Roadmap</span></td>
                <td className="px-4 py-2 border-b border-border">Automated user provisioning and deprovisioning</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium">Audit logging</td>
                <td className="px-4 py-2"><span className="text-warning">Roadmap</span></td>
                <td className="px-4 py-2">Who accessed what, exportable audit trail</td>
              </tr>
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-sm text-text-subtle">
          Roadmap features are actively in development. Contact{' '}
          <a href="mailto:enterprise@runprep.io" className="text-primary hover:underline">enterprise@runprep.io</a>{' '}
          to discuss your requirements and timeline.
        </p>

        <hr className="my-8 border-border" />

        {/* ── team_config.json Schema ────────────────────── */}
        <AnchorHeading id="team-config" level="h2">team_config.json Reference</AnchorHeading>

        <p className="mt-4 text-text-muted">
          The team configuration file is committed to your repository at <code>.runprep/team_config.json</code>.
          It contains only non-secret settings — credentials are resolved from environment variables or
          <code>.runprep/.secrets</code> (gitignored).
        </p>

        <AnchorHeading id="sync-config" level="h3">Sync Configuration</AnchorHeading>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-raised p-4 text-xs font-mono text-text border border-border">
{`{
  "sync": {
    "enabled": true,
    "s3_endpoint": "https://<account-id>.r2.cloudflarestorage.com",
    "s3_bucket": "prep-team-indexes",
    "s3_prefix": "my-repo-name",
    "poll_interval_minutes": 30
  }
}`}
        </pre>

        <AnchorHeading id="policy-config" level="h3">Policy Configuration</AnchorHeading>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-raised p-4 text-xs font-mono text-text border border-border">
{`{
  "format_version": 1,
  "enforcement": {
    "mode": "warn"
  },
  "policy": {
    "include_globs": ["src/**", "lib/**"],
    "exclude_globs": ["**/node_modules/**", "**/dist/**"]
  },
  "features": {
    "trace_enabled_default": true
  },
  "models": {
    "embedding_provider": "native",
    "embedding_model": "nomic-embed-text-v1.5"
  }
}`}
        </pre>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-lg overflow-hidden">
            <thead className="bg-surface-raised text-text">
              <tr>
                <th className="px-4 py-2 text-left border-b border-border">Field</th>
                <th className="px-4 py-2 text-left border-b border-border">Type</th>
                <th className="px-4 py-2 text-left border-b border-border">Description</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr>
                <td className="px-4 py-2 border-b border-border font-mono text-xs">enforcement.mode</td>
                <td className="px-4 py-2 border-b border-border"><code>&quot;warn&quot;</code> | <code>&quot;strict&quot;</code></td>
                <td className="px-4 py-2 border-b border-border">Warn logs policy violations; strict blocks them</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-mono text-xs">policy.include_globs</td>
                <td className="px-4 py-2 border-b border-border">string[]</td>
                <td className="px-4 py-2 border-b border-border">Glob patterns for files to include in indexing</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-mono text-xs">policy.exclude_globs</td>
                <td className="px-4 py-2 border-b border-border">string[]</td>
                <td className="px-4 py-2 border-b border-border">Glob patterns for files to exclude from indexing</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-mono text-xs">sync.enabled</td>
                <td className="px-4 py-2 border-b border-border">boolean</td>
                <td className="px-4 py-2 border-b border-border">Enable remote sync from S3 bucket</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-mono text-xs">sync.s3_endpoint</td>
                <td className="px-4 py-2 border-b border-border">string</td>
                <td className="px-4 py-2 border-b border-border">S3-compatible endpoint URL</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-mono text-xs">sync.s3_bucket</td>
                <td className="px-4 py-2 border-b border-border">string</td>
                <td className="px-4 py-2 border-b border-border">Bucket name</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border font-mono text-xs">sync.s3_prefix</td>
                <td className="px-4 py-2 border-b border-border">string</td>
                <td className="px-4 py-2 border-b border-border">Key prefix (usually repo name)</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">sync.poll_interval_minutes</td>
                <td className="px-4 py-2">number</td>
                <td className="px-4 py-2">How often local clients check for updates (default: 30)</td>
              </tr>
            </tbody>
          </table>
        </div>

        <hr className="my-8 border-border" />

        {/* ── CLI Reference ──────────────────────────────── */}
        <AnchorHeading id="cli-reference" level="h2">CLI Reference</AnchorHeading>

        <pre className="mt-4 overflow-x-auto rounded-lg bg-surface-raised p-4 text-xs font-mono text-text border border-border">
{`prep sync-headless \\
  --repo-path .                     # Path to a pre-cloned repository
  --repo-url https://...            # Or: clone from URL (uses $GIT_TOKEN for auth)
  --branch main                     # Branch to index (default: main)
  --model-provider openai           # local | openai | anthropic | google
  --model-name gpt-4.1-mini         # Model name for enrichment pipeline
  --api-key sk-...                   # API key (or use env: OPENAI_API_KEY, etc.)
  --embedder native                 # native (ONNX, CPU) | ollama
  --full                            # Force full rebuild (skip incremental)
  --s3-endpoint https://...         # S3 endpoint (or PREP_S3_ENDPOINT env)
  --s3-bucket my-bucket             # S3 bucket (or PREP_S3_BUCKET env)
  --s3-prefix my-repo               # S3 prefix (or PREP_S3_PREFIX env)
  --s3-access-key AKIA...           # S3 access key (or PREP_S3_ACCESS_KEY env)
  --s3-secret-key ...               # S3 secret key (or PREP_S3_SECRET_KEY env)`}
        </pre>

        <hr className="my-8 border-border" />

        {/* ── Links ──────────────────────────────────────── */}
        <AnchorHeading id="resources" level="h2">Resources</AnchorHeading>

        <ul className="mt-4 list-disc list-inside space-y-2 text-text-muted">
          <li>
            <a href="/guides/team-sync" className="text-primary hover:underline">Team Sync Guide</a>{' '}
            — Standard CI/CD setup with GitHub Actions
          </li>
          <li>
            <a href="https://github.com/MagneticAnomaly/prep-deploy" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
              prep-deploy repository
            </a>{' '}
            — Dockerfiles, platform adapters, and reference configurations
          </li>
          <li>
            <a href="https://runprep.io/pricing" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
              Pricing
            </a>{' '}
            — Team &amp; Enterprise plans
          </li>
          <li>
            <a href="mailto:enterprise@runprep.io" className="text-primary hover:underline">
              enterprise@runprep.io
            </a>{' '}
            — Enterprise sales and custom deployments
          </li>
        </ul>
      </div>
    </main>
  );
}

import { AnchorHeading } from '../../../components/AnchorHeading';
import { StoryEmbed } from '../../../components/StoryEmbed';

export const metadata = {
  title: 'Team Sync Guide — SourcePrep Docs',
  description: 'Set up headless CI/CD indexing so your team shares a single, pre-built trace graph.',
};

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Syncing Team Context (BYOC)
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          If you are on the <strong>Team</strong> or <strong>Enterprise</strong> tier,
          you can set up a headless indexing server so your developers never have to run
          local LLMs or burn CPU cycles to build the trace graph.
        </p>
        <p className="mt-2 text-text-muted">
          Your CI/CD pipeline builds the index once on every push to <code>main</code>.
          Every developer on your team downloads the pre-computed graph instantly.
          Their local SourcePrep only computes deltas for their uncommitted changes.
        </p>

        <hr className="my-8 border-border" />

        {/* ── How it works ─────────────────────────────────── */}
        <AnchorHeading id="how-it-works" level="h2">How it works</AnchorHeading>

        <ol className="mt-4 list-decimal list-inside space-y-2 text-text-muted">
          <li><strong>Build once:</strong> A CI/CD job runs the SourcePrep headless image after every merge to <code>main</code>. It produces the full enriched trace graph — structural, semantic, and clustered — so every developer on the team starts from the same understanding.</li>
          <li><strong>Store centrally:</strong> The index artifacts are uploaded to an S3-compatible bucket (Cloudflare R2, AWS S3, MinIO, etc.).</li>
          <li><strong>Sync locally:</strong> Each developer&apos;s SourcePrep client checks the bucket on startup and downloads the latest index in seconds.</li>
          <li><strong>Delta only:</strong> When a developer edits files locally, SourcePrep enriches only those files using their local LLM or BYOK API key. The rest of the graph comes from the shared index.</li>
        </ol>

        <div className="not-prose my-8">
          <StoryEmbed
            storyId="team-syncstatuscard--up-to-date"
            height={200}
            title="Team Sync Status"
            caption="Live preview: The Sync Status Card showing a synced team index with commit hash and last-synced timestamp."
          />
        </div>

        <p className="mt-4 text-text-muted">Two Docker image variants are available:</p>

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
                <td className="px-4 py-2 border-b border-border">GitHub Actions + BYOK (OpenAI/Anthropic)</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">ghcr.io/ericbintner/prep-headless:gpu</td>
                <td className="px-4 py-2">~8-10 GB</td>
                <td className="px-4 py-2">Yes</td>
                <td className="px-4 py-2">RunPod, Modal, AWS ECS + local Ollama</td>
              </tr>
            </tbody>
          </table>
        </div>

        <hr className="my-8 border-border" />

        {/* ── Quick Start ──────────────────────────────────── */}
        <AnchorHeading id="quick-start" level="h2">Quick Start: CPU + BYOK (Zero Infrastructure)</AnchorHeading>

        <p className="mt-4 text-text-muted">
          The fastest way to get started. Runs directly inside a free GitHub Actions runner
          using your existing OpenAI or Anthropic API key. No GPU rental, no RunPod, no Modal.
        </p>

        <AnchorHeading id="create-bucket" level="h3">1. Create a Storage Bucket</AnchorHeading>
        <p className="mt-2 text-text-muted">
          We recommend{' '}
          <a href="https://developers.cloudflare.com/r2/" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
            Cloudflare R2
          </a>{' '}
          (zero egress fees). AWS S3 or MinIO also work.
        </p>
        <p className="mt-2 text-text-muted">
          Create a bucket (e.g., <code>prep-team-indexes</code>) and generate an Access Key pair with read/write permissions.
        </p>

        <AnchorHeading id="add-github-action" level="h3">2. Add the GitHub Action</AnchorHeading>
        <p className="mt-2 text-text-muted">
          Copy the workflow template into your repository:
        </p>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-raised p-4 text-xs font-mono text-text border border-border">
{`# .github/workflows/prep-sync.yml
name: "SourcePrep Team Sync"
on:
  push:
    branches: ["main"]  # Add other branches as needed

jobs:
  index:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/ericbintner/prep-headless:cpu
    steps:
      - uses: actions/checkout@v4
      - name: Build & Upload Index
        env:
          PREP_S3_ENDPOINT: \${{ secrets.PREP_S3_ENDPOINT }}
          PREP_S3_BUCKET: \${{ secrets.PREP_S3_BUCKET }}
          PREP_S3_ACCESS_KEY: \${{ secrets.PREP_S3_ACCESS_KEY }}
          PREP_S3_SECRET_KEY: \${{ secrets.PREP_S3_SECRET_KEY }}
          OPENAI_API_KEY: \${{ secrets.OPENAI_API_KEY }}
        run: |
          prep sync-headless \\
            --repo-path . \\
            --branch "\${{ github.ref_name }}" \\
            --model-provider openai \\
            --model-name gpt-4.1-mini \\
            --embedder native`}
        </pre>
        <p className="mt-2 text-text-muted">
          That&apos;s it. Every push to <code>main</code> will rebuild the index (incrementally — only
          changed files are re-processed) and upload it to your bucket.
        </p>

        <AnchorHeading id="connect-team" level="h3">3. Connect Your Team</AnchorHeading>
        <p className="mt-2 text-text-muted">
          Commit the sync configuration to your repository (credentials are <strong>never</strong> committed):
        </p>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-raised p-4 text-xs font-mono text-text border border-border">
{`// .sourceprep/team_config.json
{
  "sync": {
    "enabled": true,
    "s3_endpoint": "https://<account-id>.r2.cloudflarestorage.com",
    "s3_bucket": "prep-team-indexes",
    "s3_prefix": "my-repo-name",
    "poll_interval_minutes": 30
  }
}`}
        </pre>
        <p className="mt-4 text-text-muted">
          Each developer provides their S3 read credentials via one of:
        </p>
        <ul className="mt-2 list-disc list-inside space-y-1 text-text-muted">
          <li>Environment variables: <code>PREP_S3_ACCESS_KEY</code> / <code>PREP_S3_SECRET_KEY</code></li>
          <li>A gitignored file: <code>.sourceprep/.secrets</code></li>
          <li>The OS keychain (prompted on first run)</li>
        </ul>
        <p className="mt-2 text-text-muted">
          When a developer opens the project, SourcePrep downloads the latest shared index automatically.
        </p>

        <hr className="my-8 border-border" />

        {/* ── Advanced: GPU ─────────────────────────────────── */}
        <AnchorHeading id="gpu-local-llm" level="h2">Advanced: GPU + Local LLM (RunPod / Modal)</AnchorHeading>

        <p className="mt-4 text-text-muted">
          For teams with large codebases or strict privacy requirements. Runs the enrichment
          pipeline on a rented GPU using open-source models (Qwen3, DeepSeek). No code leaves
          your infrastructure.
        </p>

        <AnchorHeading id="modal" level="h3">Option A: Modal (Easiest)</AnchorHeading>
        <p className="mt-2 text-text-muted">
          <a href="https://modal.com" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">Modal</a>{' '}
          provides serverless GPU execution that scales to zero.
        </p>
        <ol className="mt-2 list-decimal list-inside space-y-1 text-text-muted">
          <li>Install the Modal CLI: <code>pip install modal &amp;&amp; modal setup</code></li>
          <li>Save your S3 credentials as a Modal Secret named <code>prep-s3-creds</code>.</li>
          <li>Deploy the adapter: <code>modal deploy modal/modal_adapter.py</code></li>
          <li>Copy the webhook URL into your GitHub Action (replace the <code>run</code> step with a <code>curl</code> call to the webhook).</li>
        </ol>
        <p className="mt-2 text-xs text-text-subtle">
          The adapter source is in the{' '}
          <a href="https://github.com/MagneticAnomaly/SourcePrep-deploy" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
            prep-deploy
          </a>{' '}
          repository under <code>modal/</code>.
        </p>

        <AnchorHeading id="runpod" level="h3">Option B: RunPod Serverless</AnchorHeading>
        <p className="mt-2 text-text-muted">
          <a href="https://runpod.io" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">RunPod</a>{' '}
          provides cheap A4000/A100 GPUs on demand.
        </p>
        <ol className="mt-2 list-decimal list-inside space-y-1 text-text-muted">
          <li>Build and push the RunPod image:
            <pre className="mt-1 mb-1 overflow-x-auto rounded bg-surface-raised px-3 py-2 text-xs font-mono">
{`docker build -f runpod/Dockerfile.runpod -t my-org/prep-runpod .
docker push my-org/prep-runpod`}
            </pre>
          </li>
          <li>Create a Serverless Endpoint in the RunPod dashboard using your image.</li>
          <li>Set your S3 credentials as endpoint environment variables.</li>
          <li>Add a webhook trigger in your GitHub Action.</li>
        </ol>

        <AnchorHeading id="cost-comparison" level="h3">Cost Comparison</AnchorHeading>
        <p className="mt-2 text-text-muted">
          Approximate costs for a ~5,000-file codebase with 5 merges/day. Actual costs vary by codebase size and model pricing.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-lg overflow-hidden">
            <thead className="bg-surface-raised text-text">
              <tr>
                <th className="px-4 py-2 text-left border-b border-border">Method</th>
                <th className="px-4 py-2 text-left border-b border-border">Per run</th>
                <th className="px-4 py-2 text-left border-b border-border">Monthly (est.)</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr>
                <td className="px-4 py-2 border-b border-border">CPU + OpenAI (gpt-4.1-mini)</td>
                <td className="px-4 py-2 border-b border-border">~$8</td>
                <td className="px-4 py-2 border-b border-border">~$1,200</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border-b border-border">GPU + Qwen3 (RunPod A4000)</td>
                <td className="px-4 py-2 border-b border-border">~$0.60</td>
                <td className="px-4 py-2 border-b border-border">~$90</td>
              </tr>
              <tr>
                <td className="px-4 py-2">GPU incremental (typical PR)</td>
                <td className="px-4 py-2">~$0.05</td>
                <td className="px-4 py-2">~$8</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-text-subtle">
          Most teams start with CPU + BYOK for simplicity, then migrate to GPU as their codebase grows and API costs spike.
        </p>

        <hr className="my-8 border-border" />

        {/* ── Enterprise ───────────────────────────────────── */}
        <AnchorHeading id="enterprise" level="h2">Enterprise: AWS / Azure (VPC)</AnchorHeading>

        <p className="mt-4 text-text-muted">
          For organizations that require air-gapped deployment inside their own cloud infrastructure.
        </p>
        <p className="mt-2 text-text-muted">
          The <code>ghcr.io/ericbintner/prep-headless:gpu</code> image runs on any container
          orchestrator with GPU support:
        </p>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-raised p-4 text-xs font-mono text-text border border-border">
{`# AWS ECS / Fargate
docker run --gpus all \\
  ghcr.io/ericbintner/prep-headless:gpu \\
  sync-headless \\
    --repo-path /mnt/repo \\
    --model-provider local \\
    --model-name qwen3:8b`}
        </pre>
        <ul className="mt-4 list-disc list-inside space-y-1 text-text-muted">
          <li><strong>AWS:</strong> Use ECS with GPU task definitions or SageMaker Processing Jobs. Storage: internal S3 with IAM role auth (no static keys).</li>
          <li><strong>Azure:</strong> Use Azure Container Apps with GPU profiles or Azure ML. Storage: Azure Blob.</li>
          <li><strong>GitLab / Jenkins:</strong> Use the same Docker image in your existing CI/CD pipelines.</li>
        </ul>
        <p className="mt-2 text-xs text-text-subtle">
          A reference AWS ECS task definition is provided in the{' '}
          <a href="https://github.com/MagneticAnomaly/SourcePrep-deploy" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
            prep-deploy
          </a>{' '}
          repository under <code>aws/</code>.
        </p>

        <hr className="my-8 border-border" />

        {/* ── Local Deltas ─────────────────────────────────── */}
        <AnchorHeading id="local-deltas" level="h2">How Local Deltas Work</AnchorHeading>

        <p className="mt-4 text-text-muted">
          When a developer edits a file that exists in the shared index, SourcePrep automatically:
        </p>
        <ol className="mt-2 list-decimal list-inside space-y-1 text-text-muted">
          <li>Detects the change via the local file watcher.</li>
          <li>Enriches only that file using the developer&apos;s local LLM or BYOK key.</li>
          <li>At query time, the local delta takes priority over the shared version (the stale remote entry is masked).</li>
          <li>When the developer&apos;s changes are merged into <code>main</code> and the shared index is rebuilt, the local delta is automatically discarded.</li>
        </ol>
        <p className="mt-2 text-text-muted">
          This means every developer always has the most up-to-date context: the team&apos;s shared graph plus their own uncommitted work.
        </p>

        <hr className="my-8 border-border" />

        {/* ── Security ─────────────────────────────────────── */}
        <AnchorHeading id="security" level="h2">Security</AnchorHeading>

        <ul className="mt-4 list-disc list-inside space-y-2 text-text-muted">
          <li><strong>Never commit S3 credentials to Git.</strong> Use GitHub Secrets, Modal Secrets, or environment variables.</li>
          <li>The <code>.sourceprep/team_config.json</code> file (committed to your repo) contains only the bucket endpoint, name, and prefix — no secrets.</li>
          <li>SourcePrep includes a built-in <strong>secrets leakage detector</strong> that warns if credential-like keys appear in <code>team_config.json</code>.</li>
          <li>Each developer provides read credentials via env vars, a gitignored <code>.sourceprep/.secrets</code> file, or OS keychain.</li>
        </ul>

        <hr className="my-8 border-border" />

        {/* ── CLI Reference ────────────────────────────────── */}
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

        {/* ── FAQ ──────────────────────────────────────────── */}
        <AnchorHeading id="faq" level="h2">FAQ</AnchorHeading>

        <div className="mt-4 space-y-6">
          <div>
            <p className="font-semibold text-text">How often does the local client check for updates?</p>
            <p className="mt-1 text-text-muted">
              On daemon startup, on manual &ldquo;Sync Now&rdquo; button press, and on a configurable
              polling interval (default: every 30 minutes).
            </p>
          </div>
          <div>
            <p className="font-semibold text-text">Does every push trigger a full rebuild?</p>
            <p className="mt-1 text-text-muted">
              No. By default, <code>sync-headless</code> runs in incremental mode. It compares
              the existing index manifest against the current repo state and only re-processes
              changed, added, or deleted files. Pass <code>--full</code> to force a complete rebuild.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text">Which branches can I sync?</p>
            <p className="mt-1 text-text-muted">
              Any branch. Configure the <code>branches</code> list in your GitHub Action.
              Each branch gets its own S3 prefix automatically.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text">What if my repo is private?</p>
            <p className="mt-1 text-text-muted">
              The headless container supports Git clone via <code>$GIT_TOKEN</code> (HTTPS) or{' '}
              <code>$SSH_KEY</code> (SSH). In GitHub Actions, the <code>actions/checkout</code> step
              handles this automatically.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text">Do I need a GPU?</p>
            <p className="mt-1 text-text-muted">
              No. The <code>:cpu</code> image uses SourcePrep&apos;s built-in ONNX embedder (runs on CPU)
              and sends LLM reasoning to a cloud API (OpenAI, Anthropic, etc.). A GPU is only needed
              if you want to run models locally for privacy or cost reasons.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text">Where are the deployment templates?</p>
            <p className="mt-1 text-text-muted">
              All Dockerfiles, platform adapters (Modal, RunPod), GitHub Actions workflows, and
              AWS ECS references are in the public{' '}
              <a href="https://github.com/MagneticAnomaly/SourcePrep-deploy" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
                prep-deploy
              </a>{' '}
              repository.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

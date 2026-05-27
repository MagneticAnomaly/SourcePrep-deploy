import { AnimatedCLI, prepOverviewDemo } from '../../../components/cli-demos';
import { AnchorHeading } from '../../../components/AnchorHeading';
import { DemoAgentOpsActive } from '../../../components/demos';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/mcp" className="text-sm text-text-muted">
          ← Back to Integrations
        </a>

        <h1 className="mt-6 text-4xl font-bold tracking-tight">
          Paperclip Plugin
        </h1>
        <p className="mt-4 text-xl text-text-muted">
          Give every Paperclip agent deep structural codebase knowledge —
          module maps, dependency graphs, semantic search, and health analysis.
        </p>

        <div className="mt-8 rounded-2xl border border-primary/30 bg-primary/5 p-6">
          <h3 className="text-lg font-semibold text-primary">Why this is different</h3>
          <p className="mt-2 text-text-muted">
            Most AI agents work blind — they grep files, guess at structure, and miss
            architectural context. SourcePrep&apos;s Paperclip plugin gives agents a
            structural brain: they understand which modules exist, how files connect,
            what the blast radius of a change is, and what the codebase health looks
            like — <span className="text-text font-medium">before writing a single line of code</span>.
          </p>
          <p className="mt-2 text-text-muted">
            This is a novel workflow: <span className="text-text font-medium">epistemic-first agent orchestration</span>.
            Instead of agents discovering codebase structure through trial and error,
            SourcePrep pre-computes it and serves it on demand. The result is agents that
            make better decisions, faster, with fewer hallucinations.
          </p>
        </div>

        <div className="mt-12 prose max-w-none">
          <AnchorHeading id="how-it-works" level="h2">How It Works</AnchorHeading>

          <div className="mt-4 rounded-xl border border-border bg-surface p-6 font-mono text-sm leading-relaxed">
            <div className="text-text-muted">{'# The three-layer architecture'}</div>
            <div className="mt-2">
              <span className="text-primary">Layer 3: Paperclip</span>
              <span className="text-text-muted"> — The office. Manages WHAT agents work on.</span>
            </div>
            <div className="text-text-muted ml-4">{'     ↑ pushes tasks to'}</div>
            <div>
              <span className="text-primary">Layer 2: Agent Runtime</span>
              <span className="text-text-muted"> — HOW agents think (Claude, Codex, etc.)</span>
            </div>
            <div className="text-text-muted ml-4">{'     ↑ pulls knowledge from'}</div>
            <div>
              <span className="text-primary">Layer 1: SourcePrep</span>
              <span className="text-text-muted"> — The brain. WHAT the agent knows about your code.</span>
            </div>
          </div>

          <p className="mt-4">
            The SourcePrep plugin registers 5 tools that any Paperclip agent can call during
            their runs. These tools proxy to your local SourcePrep daemon, which has already
            indexed your codebase with embeddings, a structural graph, and epistemic analysis.
          </p>

          <AnchorHeading id="installation" level="h2">Installation</AnchorHeading>

          <h3 className="text-lg font-semibold mt-6">Prerequisites</h3>
          <ol className="list-decimal pl-6 space-y-2 mt-2">
            <li>
              <span className="font-semibold text-text">SourcePrep Desktop App</span> — Download from{' '}
              <a href="https://sourceprep.io/download" className="text-primary hover:underline">sourceprep.io/download</a>.
              The daemon must be running at <code>localhost:8400</code>.
            </li>
            <li>
              <span className="font-semibold text-text">A SourcePrep project</span> — Add your repo:{' '}
              <code>prep add /path/to/your/project</code>
            </li>
            <li>
              <span className="font-semibold text-text">A Paperclip instance</span> — Running at{' '}
              <code>localhost:3100</code> or your deployment URL.
            </li>
          </ol>

          <h3 className="text-lg font-semibold mt-6">Install the Plugin</h3>
          <div className="mt-2 rounded-lg bg-[#1a1a2e] p-4 font-mono text-sm">
            <span className="text-text-muted">$</span>{' '}
            <span className="text-text">pnpm paperclipai plugin install @prep/paperclip-plugin</span>
          </div>

          <p className="mt-3 text-text-muted text-sm">
            Or install from a local path during development:
          </p>
          <div className="mt-1 rounded-lg bg-[#1a1a2e] p-4 font-mono text-sm">
            <span className="text-text-muted">$</span>{' '}
            <span className="text-text">pnpm paperclipai plugin install ./packages/paperclip-plugin</span>
          </div>

          <h3 className="text-lg font-semibold mt-6">Configure</h3>
          <p className="mt-2">
            In Paperclip Settings → Plugins → SourcePrep:
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 text-left font-semibold">Setting</th>
                  <th className="py-2 pr-4 text-left font-semibold">Default</th>
                  <th className="py-2 text-left font-semibold">Description</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">daemon_url</td>
                  <td className="py-2 pr-4 text-xs">http://127.0.0.1:8400</td>
                  <td className="py-2 text-xs">SourcePrep daemon URL</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">project_id</td>
                  <td className="py-2 pr-4 text-xs">(auto-detected)</td>
                  <td className="py-2 text-xs">SourcePrep project ID. Auto-detects if you have one project.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">auto_context</td>
                  <td className="py-2 pr-4 text-xs">true</td>
                  <td className="py-2 text-xs">Automatically attach SourcePrep context to new issues</td>
                </tr>
              </tbody>
            </table>
          </div>

          <AnchorHeading id="tools" level="h2">Tools Reference</AnchorHeading>
          <p className="mt-2">
            Once installed, all Paperclip agents can use these tools during their runs.
            Tools are namespaced as <code>prep:*</code> and appear in the agent&apos;s tool palette.
          </p>

          <div className="not-prose my-6">
            <AnimatedCLI script={prepOverviewDemo} />
          </div>
          <p className="text-xs text-text-muted text-center italic -mt-2">
            What an agent sees when it calls <code>prep:context</code> (Paperclip&apos;s wrapper around the base <code>prep</code> MCP tool).
          </p>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 text-left font-semibold">Tool</th>
                  <th className="py-2 text-left font-semibold">What It Does</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep:context</td>
                  <td className="py-2 text-xs">Structural overview — modules, hub files, atlas. Call at the start of every task.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep:search</td>
                  <td className="py-2 text-xs">Semantic code search with structural trace expansion. Finds code by meaning, not just keywords.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep:impact</td>
                  <td className="py-2 text-xs">Blast radius analysis — what depends on a file, what it depends on. Use before modifying code.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep:audit</td>
                  <td className="py-2 text-xs">Codebase health findings — tech debt, architecture issues, dead code, naming inconsistencies.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep:observe</td>
                  <td className="py-2 text-xs">Save cross-session observations. Agents build persistent memory about the codebase.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="not-prose">
            <DemoAgentOpsActive />
            <p className="text-xs text-text-subtle italic -mt-2 mb-4">
              Live preview: The three SourcePrep agents (HR, Researcher, Custodian) with managed employee badges.
            </p>
          </div>

          <AnchorHeading id="ui" level="h2">Dashboard Extensions</AnchorHeading>
          <p className="mt-2">
            The plugin adds UI components directly into the Paperclip dashboard:
          </p>
          <ul className="list-disc pl-6 space-y-2 mt-2">
            <li>
              <span className="font-semibold text-text">Codebase Health Widget</span> — Dashboard widget
              showing readiness score, role count, research runs, and archived items at a glance.
            </li>
            <li>
              <span className="font-semibold text-text">Knowledge Scope Tab</span> — On each agent&apos;s
              detail page, shows which files SourcePrep has assigned to that agent&apos;s role scope.
            </li>
            <li>
              <span className="font-semibold text-text">Issue Context Tab</span> — On each issue&apos;s
              detail page, shows SourcePrep structural context for issues created from audit findings.
            </li>
            <li>
              <span className="font-semibold text-text">Settings Page</span> — Connection status,
              available tools reference, and plugin configuration.
            </li>
          </ul>

          <AnchorHeading id="agent-workflow" level="h2">The Agent Workflow</AnchorHeading>
          <p className="mt-2">
            Here&apos;s what happens when a Paperclip agent works on a task with SourcePrep installed:
          </p>

          <div className="mt-4 space-y-4">
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-sm">1</div>
              <div>
                <div className="font-semibold text-text">Agent calls prep:context</div>
                <div className="text-text-muted text-sm">Gets module map, hub files, and architecture overview. Now it knows the codebase structure.</div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-sm">2</div>
              <div>
                <div className="font-semibold text-text">Agent calls prep:search</div>
                <div className="text-text-muted text-sm">Finds relevant code by semantic meaning, with structural trace expansion pulling in related imports.</div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-sm">3</div>
              <div>
                <div className="font-semibold text-text">Agent calls prep:impact before changes</div>
                <div className="text-text-muted text-sm">Checks blast radius — what will break if this file is modified? How many dependents?</div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-sm">4</div>
              <div>
                <div className="font-semibold text-text">Agent calls prep:observe</div>
                <div className="text-text-muted text-sm">Saves observations for the next agent. Cross-session memory that persists across runs.</div>
              </div>
            </div>
          </div>

          <AnchorHeading id="novel-workflow" level="h2">Why This Is Novel</AnchorHeading>
          <p className="mt-2">
            Traditional AI agents approach codebases like a developer on their first day —
            grepping files, reading README.md, hoping they stumble onto the right architecture.
            SourcePrep inverts this:
          </p>
          <ul className="list-disc pl-6 space-y-2 mt-2">
            <li>
              <span className="font-semibold text-text">Pre-computed structure</span> — The code graph,
              module clusters, and hub files are already indexed. Agents don&apos;t discover structure;
              they query it.
            </li>
            <li>
              <span className="font-semibold text-text">Epistemic confidence</span> — SourcePrep knows
              which parts of the codebase are well-understood (high enrichment) vs. opaque. Agents
              can be cautious where the index is thin.
            </li>
            <li>
              <span className="font-semibold text-text">Role-scoped context</span> — A backend agent
              sees backend-relevant files. A frontend agent sees frontend files. SourcePrep&apos;s RoleVector
              system projects the atlas differently per role.
            </li>
            <li>
              <span className="font-semibold text-text">Impact-aware changes</span> — Before modifying
              a file, agents know exactly what depends on it. This prevents the cascade of broken
              imports that plagues autonomous coding agents.
            </li>
          </ul>

          <AnchorHeading id="source" level="h2">Source Code</AnchorHeading>
          <p className="mt-2">
            The plugin source is at{' '}
            <a href="https://github.com/MagneticAnomaly/SourcePrep/tree/main/packages/paperclip-plugin-prep" className="text-primary hover:underline">
              packages/paperclip-plugin-prep
            </a>{' '}
            in the SourcePrep repository. It&apos;s MIT-licensed.
          </p>
        </div>
      </div>
    </main>
  );
}

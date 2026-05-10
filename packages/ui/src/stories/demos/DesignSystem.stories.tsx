import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { ArrowRight, Play, Save, Search } from 'lucide-react';
import { Button } from '../../components/primitives/Button';
import { Select } from '../../components/primitives/Select';
import { SearchableSelect } from '../../components/primitives/SearchableSelect';
import { Checkbox } from '../../components/primitives/Checkbox';
import { SlidingSwitch2, SlidingSwitch3 } from '../../components/primitives/SlidingSwitch';
import { CopyButton } from '../../components/context/CopyButton';
import { CitationBlock } from '../../components/context/CitationBlock';
import { Section } from '../../components/settings/Section';
import { SettingRow } from '../../components/settings/SettingRow';
import { Toggle } from '../../components/primitives/Toggle';
import { StatusBadge } from '../../components/status/StatusBadge';
import { PanelChrome } from '../../components/layout/PanelChrome';
import './DesignSystem.css';

const meta: Meta = {
  title: 'Demos/Design System',
  parameters: { layout: 'fullscreen' },
};
export default meta;

const swatches: [string, string][] = [
  ['background', 'App canvas'],
  ['surface', 'Cards, panels'],
  ['surface-raised', 'Toolbars, hover'],
  ['border', 'Frames, dividers'],
  ['text', 'Primary text'],
  ['text-muted', 'Secondary text'],
  ['primary', 'Brand, action'],
  ['success', 'Confirmation'],
  ['warning', 'Caution'],
  ['error', 'Critical'],
  ['info', 'Neutral notice'],
];

const spacingScale = [1, 2, 3, 4, 6, 8, 12, 16];

const TEXT_COLOR = 'hsl(var(--text))';
const MUTED_COLOR = 'hsl(var(--text-muted))';

export const Showcase: StoryObj = {
  name: 'Overview',
  render: () => (
    <div className="ds-showcase">
      <header className="ds-hero">
        <div className="ds-hero-eyebrow">SourcePrep · Design System</div>
        <h1 style={{ color: TEXT_COLOR }}>Design System Demo</h1>
        <p>
          A single-page reference for the core design language — color, type, spacing, primitives,
          and panel chrome. The same tokens drive the dashboard and the marketing site.
        </p>
      </header>

      {/* COLOR */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Color</h2>
          <p>Semantic tokens. Each theme remaps these values; consumers reference the role, not the hex.</p>
        </div>
        <div className="ds-swatches">
          {swatches.map(([token, label]) => (
            <div key={token} className="ds-swatch">
              <div className="ds-swatch-chip" style={{ background: 'hsl(var(--' + token + '))' }} />
              <div className="ds-swatch-name"><code>--{token}</code></div>
              <div className="ds-swatch-role">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* TYPOGRAPHY */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Typography</h2>
          <p>System font stack — Inter for prose, JetBrains Mono for code. Tracked, sized, and weighted for IDE-density UIs.</p>
        </div>
        <div className="ds-typography">
          <TypeRow label="Display">
            <span style={{ fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.02em', color: TEXT_COLOR }}>
              The quick brown fox
            </span>
          </TypeRow>
          <TypeRow label="Heading 1">
            <span style={{ fontSize: '1.75rem', fontWeight: 700, color: TEXT_COLOR }}>
              The quick brown fox jumps
            </span>
          </TypeRow>
          <TypeRow label="Heading 2">
            <span style={{ fontSize: '1.25rem', fontWeight: 600, color: TEXT_COLOR }}>
              The quick brown fox jumps over
            </span>
          </TypeRow>
          <TypeRow label="Body">
            <span style={{ fontSize: '1rem', color: TEXT_COLOR }}>
              The quick brown fox jumps over the lazy dog.
            </span>
          </TypeRow>
          <TypeRow label="Small">
            <span style={{ fontSize: '0.875rem', color: MUTED_COLOR }}>
              The quick brown fox jumps over the lazy dog.
            </span>
          </TypeRow>
          <TypeRow label="Code">
            <code style={{
              fontFamily: '"JetBrains Mono", ui-monospace, monospace',
              fontSize: '0.875rem',
              background: 'hsl(var(--surface-raised))',
              color: TEXT_COLOR,
              padding: '0.25rem 0.5rem',
              borderRadius: 4,
            }}>
              const ctx = await prep.search(query);
            </code>
          </TypeRow>
        </div>
      </section>

      {/* SPACING */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Spacing</h2>
          <p>4-pixel base scale. Multipliers (1, 2, 3, 4, 6, 8, 12, 16) cover the common rhythm.</p>
        </div>
        <div className="ds-spacing">
          {spacingScale.map((m) => (
            <div key={m} className="ds-spacing-row">
              <span className="ds-spacing-label">{m * 4}px</span>
              <div className="ds-spacing-bar" style={{ width: m * 4 + 'px' }} />
            </div>
          ))}
        </div>
      </section>

      {/* BUTTONS */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Buttons</h2>
          <p>Variants, sizes, and pill action capsules. Every action in the product is one of these.</p>
        </div>
        <div className="ds-grid">
          <div className="ds-row">
            <Button variant="default">Default</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="link">Link</Button>
          </div>
          <div className="ds-row">
            <Button size="sm">Small</Button>
            <Button>Default</Button>
            <Button size="lg">Large</Button>
            <Button size="icon"><ArrowRight className="h-4 w-4" /></Button>
            <Button><Save className="h-4 w-4 mr-2" />With icon</Button>
            <Button disabled>Disabled</Button>
          </div>
          <div className="ds-row">
            <Button variant="pill" tone="default"><Play className="w-3.5 h-3.5" />Run</Button>
            <Button variant="pill" tone="success"><Play className="w-3.5 h-3.5" />Run</Button>
            <Button variant="pill" tone="warning"><Play className="w-3.5 h-3.5" />Resume</Button>
            <Button variant="pill" tone="default" disabled><Play className="w-3.5 h-3.5" />Disabled</Button>
          </div>
        </div>
      </section>

      {/* SLIDING SWITCHES */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Sliding switches</h2>
          <p>Segmented two- and three-state controls used in the pipeline panel for Manual / Auto / Scheduled.</p>
        </div>
        <SlidingSwitchSpecimen />
      </section>

      {/* FORM ELEMENTS */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Form elements</h2>
          <p>The atoms of every settings page and inline control.</p>
        </div>
        <div className="ds-form-grid">
          <div className="ds-form-cell">
            <span className="ds-form-label">Select</span>
            <Select
              defaultValue="ollama"
              options={[
                { value: 'ollama', label: 'Ollama (local)' },
                { value: 'openai', label: 'OpenAI' },
                { value: 'anthropic', label: 'Anthropic' },
              ]}
            />
          </div>
          <div className="ds-form-cell">
            <span className="ds-form-label">Searchable Select</span>
            <SearchableSelect
              options={[
                { value: 'qwen', label: 'qwen2.5:3b' },
                { value: 'llama', label: 'llama3.2:3b' },
                { value: 'mistral', label: 'mistral:7b' },
              ]}
              value="qwen"
              onChange={() => {}}
              placeholder="Pick a model…"
            />
          </div>
          <div className="ds-form-cell">
            <span className="ds-form-label">Toggle</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Toggle checked onChange={() => {}} />
              <span style={{ fontSize: '0.875rem', color: MUTED_COLOR }}>Auto-rebuild</span>
            </div>
          </div>
          <div className="ds-form-cell">
            <span className="ds-form-label">Checkbox</span>
            <CheckboxSpecimen />
          </div>
          <div className="ds-form-cell">
            <span className="ds-form-label">Setting Row</span>
            <div style={{
              background: 'hsl(var(--surface))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 6,
              padding: '0.75rem',
            }}>
              <SettingRow
                id="auto-rebuild"
                label="Auto-rebuild on file change"
                description="Re-runs the index when watched files change."
                control={<Toggle checked onChange={() => {}} />}
              />
            </div>
          </div>
        </div>
      </section>

      {/* STATUS */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Status</h2>
          <p>Compact indicators for system state — used inline and in panel headers.</p>
        </div>
        <div className="ds-row">
          <StatusBadge status="fresh" />
          <StatusBadge status="stale" />
          <StatusBadge status="building" />
          <StatusBadge status="pending" />
          <StatusBadge status="error" />
          <StatusBadge status="disabled" />
        </div>
      </section>

      {/* PRIMITIVES */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Primitives in context</h2>
          <p>How a citation, a copy affordance, and a section header sit alongside each other.</p>
        </div>
        <Section title="Search results">
          <CitationBlock sourcePath="src/prep/api/routes.py" span={{ start_line: 12, end_line: 28 }} score={0.84} />
          <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
            <CopyButton text="Sample context block" label="Copy context" />
          </div>
        </Section>
      </section>

      {/* PANEL CHROME */}
      <section className="ds-section">
        <div className="ds-section-head">
          <h2 style={{ color: TEXT_COLOR }}>Panel chrome</h2>
          <p>The frame every dashboard panel sits inside. Drag handle, title, icon, collapse, close.</p>
        </div>
        <div style={{ maxWidth: '32rem' }}>
          <PanelChrome
            title="Knowledge Query"
            icon={Search}
            description="Semantic search across documentation, plans, and codebase meanings."
          >
            <div style={{ padding: '1.25rem', color: MUTED_COLOR, fontSize: '0.875rem' }}>
              Inner panel content goes here. Every panel in the dashboard wears this chrome.
            </div>
          </PanelChrome>
        </div>
      </section>
    </div>
  ),
};

function TypeRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="ds-type-row">
      <span className="ds-type-label">{label}</span>
      <div>{children}</div>
    </div>
  );
}

function CheckboxSpecimen() {
  const [a, setA] = useState(true);
  const [b, setB] = useState(false);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: MUTED_COLOR }}>
        <Checkbox checked={a} onCheckedChange={setA} />
        Threshold trigger
      </label>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: MUTED_COLOR }}>
        <Checkbox checked={b} onCheckedChange={setB} size="sm" />
        Schedule (size="sm")
      </label>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: MUTED_COLOR, opacity: 0.6 }}>
        <Checkbox checked disabled onCheckedChange={() => {}} />
        Disabled
      </label>
    </div>
  );
}

function SlidingSwitchSpecimen() {
  const [auto, setAuto] = useState(true);
  const [mode, setMode] = useState<'manual' | 'auto' | 'scheduled'>('auto');
  return (
    <div className="ds-grid">
      <div className="ds-row">
        <span style={{ fontSize: '0.75rem', color: MUTED_COLOR, minWidth: '8rem' }}>Two-state</span>
        <SlidingSwitch2 value={auto} onChange={setAuto} />
        <span style={{ fontSize: '0.75rem', color: MUTED_COLOR }}>{auto ? 'Auto' : 'Manual'}</span>
      </div>
      <div className="ds-row">
        <span style={{ fontSize: '0.75rem', color: MUTED_COLOR, minWidth: '8rem' }}>Three-state</span>
        <SlidingSwitch3
          value={mode}
          options={[
            { label: 'Manual', value: 'manual' },
            { label: 'Auto', value: 'auto' },
            { label: 'Scheduled', value: 'scheduled' },
          ]}
          onChange={setMode}
        />
        <span style={{ fontSize: '0.75rem', color: MUTED_COLOR }}>{mode}</span>
      </div>
    </div>
  );
}

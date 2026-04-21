import { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Flex,
  Grid,
  Metric,
  ProgressBar,
  Select,
  SelectItem,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
  Text,
  TextInput,
  Title,
} from '@tremor/react';
import {
  FolderTree,
  sampleFileTree,
  IndexStats,
  sampleIndexStats,
  sampleMarketingStats,
  TraceGraph,
  TraceGraphMini,
  sampleTraceNodes,
  MarketingHero,
  FeatureBlocks,
  prepFeatures,
  marketingFeatures,
} from './components';
import { 
  Brain, 
  Folder, 
  FileText, 
  Sun, 
  Moon 
} from 'lucide-react';

type ThemeId = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n';

type ThemeOption = {
  id: ThemeId;
  label: string;
  description: string;
};

const themeOptions: ThemeOption[] = [
  { id: 'a', label: 'A: Slate Developer', description: 'Neutral grays, monospace feel' },
  { id: 'b', label: 'B: Deep Focus', description: 'Deep blues, high contrast' },
  { id: 'c', label: 'C: Signal Green', description: 'Green accents, terminal vibe' },
  { id: 'd', label: 'D: Warm Craft', description: 'Warm tones, approachable' },
  { id: 'e', label: 'E: Neo-Brutalist', description: 'Bold, raw, high contrast, zero radius' },
  { id: 'f', label: 'F: Swiss Minimal', description: 'Clean grids, international red, whitespace' },
  { id: 'g', label: 'G: Glass-Morphic', description: 'Translucent layers, blurs, soft shadows' },
  { id: 'h', label: 'H: Retro-Futurism', description: 'Synthwave, neon glows, dark grids' },
  { id: 'm', label: 'M: Retro Aurora', description: 'Retro-future with teal/blue/purple glows' },
  { id: 'n', label: 'N: Retro Mirage', description: 'Retro-future variant with layered neon haze' },
  { id: 'i', label: 'I: Studio Collage', description: 'Expressive, layered, Cranbrook-inspired' },
  { id: 'j', label: 'J: Yale Grid', description: 'Typographic discipline, quiet, semantic' },
  { id: 'k', label: 'K: Inclusive Focus', description: 'High contrast, clear focus, accessible' },
  { id: 'l', label: 'L: Enterprise Console', description: 'Dense, governed, productive' },
];

type StatusState = 'fresh' | 'stale' | 'building' | 'error';

function statusColor(status: StatusState): 'green' | 'yellow' | 'blue' | 'red' {
  switch (status) {
    case 'fresh':
      return 'green';
    case 'stale':
      return 'yellow';
    case 'building':
      return 'blue';
    case 'error':
      return 'red';
  }
}

function statusLabel(status: StatusState): string {
  switch (status) {
    case 'fresh':
      return 'Fresh';
    case 'stale':
      return 'Stale';
    case 'building':
      return 'Building';
    case 'error':
      return 'Error';
  }
}

type HeroVariant = 'centered' | 'split' | 'neo' | 'swiss' | 'glass' | 'retro' | 'studio' | 'yale' | 'focus' | 'enterprise';
type FeatureVariant = 'cards' | 'list' | 'bento';

type HeroLayout = 'default' | 'centered' | 'split';

function getThemeDefaultHeroVariant(theme: ThemeId): HeroVariant {
  if (theme === 'e') return 'neo';
  if (theme === 'f') return 'swiss';
  if (theme === 'g') return 'glass';
  if (theme === 'h') return 'retro';
  if (theme === 'm' || theme === 'n') return 'retro';
  if (theme === 'i') return 'studio';
  if (theme === 'j') return 'yale';
  if (theme === 'k') return 'focus';
  if (theme === 'l') return 'enterprise';
  if (theme === 'a' || theme === 'd') return 'centered';
  if (theme === 'b' || theme === 'c') return 'split';
  return 'centered';
}

export default function App() {
  const [theme, setTheme] = useState<ThemeId>('i');
  const [darkMode, setDarkMode] = useState(false);
  const [query, setQuery] = useState('where does auth token get validated');
  const [heroVariant, setHeroVariant] = useState<HeroVariant>('studio');
  const [heroLayout, setHeroLayout] = useState<HeroLayout>('default');
  const [featureVariant, setFeatureVariant] = useState<FeatureVariant>('cards');
  const [selectedTraceNode, setSelectedTraceNode] = useState<string>('1');

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-prep-theme', theme);
    root.classList.toggle('dark', darkMode);

    // Auto-switch hero variant based on theme for better demo
    if (heroLayout === 'default') {
      setHeroVariant(getThemeDefaultHeroVariant(theme));
    }
  }, [theme, darkMode, heroLayout]);

  const themeLabel = useMemo(() => {
    return themeOptions.find((t) => t.id === theme)?.label ?? theme;
  }, [theme]);

  const currentTheme = useMemo(() => {
    return themeOptions.find((t) => t.id === theme);
  }, [theme]);

  const searchResults = useMemo(
    () => [
      {
        path: 'src/prep/api/auth.py',
        lines: '42-67',
        score: 0.87,
        status: 'fresh' as const,
        preview:
          'def validate_token(token: str) -> Claims:\n    claims = jwt.decode(token, ...)\n    if claims.exp < now():\n        raise AuthError("expired")',
      },
      {
        path: 'src/prep/server.py',
        lines: '142-175',
        score: 0.81,
        status: 'building' as const,
        preview:
          '@app.middleware("http")\nasync def add_request_id(request, call_next):\n    request_id = ...\n    response = await call_next(request)',
      },
      {
        path: 'src/prep/core/security.py',
        lines: '10-28',
        score: 0.72,
        status: 'stale' as const,
        preview:
          'def hash_secret(secret: str) -> str:\n    salt = os.urandom(16)\n    return pbkdf2_hmac(..., salt=salt)',
      },
    ],
    [],
  );

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top Controls Bar */}
      <div className="sticky top-0 z-50 border-b border-border bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/80">
        <div className="mx-auto w-full max-w-7xl px-6 py-3">
          <Flex justifyContent="between" alignItems="center" className="gap-6">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🧠</span>
                <Title className="text-text">Prep</Title>
              </div>
              <Badge color="blue" size="sm">Design Preview</Badge>
            </div>

            <Flex className="gap-3" justifyContent="end" alignItems="center">
              <div className="w-[200px] shrink-0">
                <Select value={theme} onValueChange={(v) => setTheme(v as ThemeId)}>
                  {themeOptions.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.label}
                    </SelectItem>
                  ))}
                </Select>
              </div>

              <Button
                variant="secondary"
                onClick={() => setDarkMode((v) => !v)}
                className="border border-border"
              >
                {darkMode ? '☀️ Light' : '🌙 Dark'}
              </Button>
            </Flex>
          </Flex>
        </div>
      </div>

      <div className="mx-auto w-full max-w-7xl px-6 py-8">
        {/* Theme Info */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <Text className="text-text-muted">
              {currentTheme?.description} • {darkMode ? 'Dark Mode' : 'Light Mode'}
            </Text>
          </div>
          <Flex className="gap-2">
            <Badge color="gray" size="sm">Tremor + TailwindCSS</Badge>
            <Badge color="gray" size="sm">CSS Variables</Badge>
          </Flex>
        </div>

        <TabGroup>
          <TabList variant="solid" className="border border-border">
            <Tab>Marketing</Tab>
            <Tab>Dashboard</Tab>
            <Tab>Components</Tab>
          </TabList>

          <TabPanels>
            {/* MARKETING TAB */}
            <TabPanel>
              <div className="mt-6 space-y-12">
                {/* Hero variant selector */}
                <Flex justifyContent="between" alignItems="center" className="mb-4">
                  <Text className="text-text-muted text-sm">Hero Layout:</Text>
                  <Flex className="gap-2">
                    <Button
                      size="xs"
                      variant={heroLayout === 'default' ? 'primary' : 'secondary'}
                      onClick={() => {
                        setHeroLayout('default');
                        setHeroVariant(getThemeDefaultHeroVariant(theme));
                      }}
                      className={heroLayout === 'default' ? 'bg-primary text-white' : 'border border-border'}
                    >
                      Default
                    </Button>
                    <Button
                      size="xs"
                      variant={heroLayout === 'centered' ? 'primary' : 'secondary'}
                      onClick={() => {
                        setHeroLayout('centered');
                        setHeroVariant('centered');
                      }}
                      className={heroLayout === 'centered' ? 'bg-primary text-white' : 'border border-border'}
                    >
                      Center
                    </Button>
                    <Button
                      size="xs"
                      variant={heroLayout === 'split' ? 'primary' : 'secondary'}
                      onClick={() => {
                        setHeroLayout('split');
                        setHeroVariant('split');
                      }}
                      className={heroLayout === 'split' ? 'bg-primary text-white' : 'border border-border'}
                    >
                      Split
                    </Button>
                  </Flex>
                </Flex>

                {/* Hero Section */}
                <MarketingHero variant={heroVariant} />

                {/* Stats Bar */}
                <div className="py-8 border-y border-border">
                  <div className="text-center mb-6">
                    <Text className="text-text-subtle uppercase tracking-wider text-sm">Proven Performance</Text>
                  </div>
                  <IndexStats stats={sampleMarketingStats} variant="large" />
                </div>

                {/* Features Section */}
                <div>
                  <Flex justifyContent="between" alignItems="center" className="mb-6">
                    <div>
                      <Title className="text-text text-2xl">Why Prep?</Title>
                      <Text className="text-text-muted mt-1">Built for developers who value their code and time</Text>
                    </div>
                    <Flex className="gap-2">
                      <Button
                        size="xs"
                        variant={featureVariant === 'cards' ? 'primary' : 'secondary'}
                        onClick={() => setFeatureVariant('cards')}
                        className={featureVariant === 'cards' ? 'bg-primary text-white' : 'border border-border'}
                      >
                        Cards
                      </Button>
                      <Button
                        size="xs"
                        variant={featureVariant === 'list' ? 'primary' : 'secondary'}
                        onClick={() => setFeatureVariant('list')}
                        className={featureVariant === 'list' ? 'bg-primary text-white' : 'border border-border'}
                      >
                        List
                      </Button>
                      <Button
                        size="xs"
                        variant={featureVariant === 'bento' ? 'primary' : 'secondary'}
                        onClick={() => setFeatureVariant('bento')}
                        className={featureVariant === 'bento' ? 'bg-primary text-white' : 'border border-border'}
                      >
                        Bento
                      </Button>
                    </Flex>
                  </Flex>
                  <FeatureBlocks features={prepFeatures} variant={featureVariant} />
                </div>

                {/* Problem-Solution Section */}
                <Card className="border border-border bg-gradient-to-br from-surface to-surface-raised p-8">
                  <div className="text-center mb-8">
                    <Badge size="lg" className="bg-warning/10 text-warning border border-warning/20 mb-4">
                      The Problem
                    </Badge>
                    <Title className="text-text text-2xl">Your AI makes mistakes because it can't see enough</Title>
                    <Text className="text-text-muted mt-2 max-w-2xl mx-auto">
                      AI coding assistants hallucinate when they lack context. Manual copy-pasting 
                      is slow, error-prone, and doesn't scale.
                    </Text>
                  </div>
                  <FeatureBlocks features={marketingFeatures} variant="list" />
                </Card>

                {/* Trust Logos */}
                <div className="py-8 text-center">
                  <Text className="text-text-subtle text-sm mb-6">Works seamlessly with</Text>
                  <Flex justifyContent="center" className="gap-8 flex-wrap">
                    {['Cursor', 'Windsurf', 'VS Code', 'Ollama', 'Any MCP IDE'].map((tool) => (
                      <div key={tool} className="px-4 py-2 rounded-lg border border-border-subtle bg-surface-raised">
                        <Text className="text-text-muted font-medium">{tool}</Text>
                      </div>
                    ))}
                  </Flex>
                </div>

                {/* Final CTA */}
                <Card className="border-2 border-primary/50 bg-gradient-to-r from-primary/10 to-primary/5 text-center py-12">
                  <Title className="text-text text-3xl">Ready to supercharge your AI workflow?</Title>
                  <Text className="text-text-muted mt-2 text-lg">
                    Join the founders who ship faster with better AI context.
                  </Text>
                  <Flex className="mt-8 gap-4" justifyContent="center">
                    <Button size="lg" className="bg-primary hover:bg-primary-hover text-white px-8 font-semibold">
                      Get Founder's Edition — $49
                    </Button>
                    <Button size="lg" variant="secondary" className="border border-border px-8">
                      Try Free (2 projects)
                    </Button>
                  </Flex>
                  <Text className="text-text-subtle text-sm mt-4">
                    Perpetual license • No subscription • Works offline
                  </Text>
                </Card>
              </div>
            </TabPanel>

            {/* DASHBOARD TAB */}
            <TabPanel>
              <div className="mt-6 space-y-6">
                {/* Stats Overview */}
                <IndexStats stats={sampleIndexStats} />

                <Grid numItems={1} numItemsLg={3} className="gap-6">
                  {/* Left Column: Project & Search */}
                  <Col numColSpan={1} numColSpanLg={2}>
                    <div className="space-y-6">
                      {/* Project Header */}
                      <Card className="border border-border bg-surface shadow-sm">
                        <Flex justifyContent="between" alignItems="start">
                          <div>
                            <Flex className="gap-3" alignItems="center">
                              <Folder className="w-8 h-8 text-primary" />
                              <div>
                                <Title className="text-text">LinuxBrain</Title>
                                <Text className="font-mono text-sm text-text-subtle">LinuxBrain</Text>
                              </div>
                            </Flex>
                          </div>
                          <Flex className="gap-2">
                            <Badge color="green">Fresh</Badge>
                            <Badge color="blue">Auto-rebuild</Badge>
                          </Flex>
                        </Flex>
                        <Divider className="my-4" />
                        <Flex className="gap-3">
                          <Button className="bg-primary text-white" size="sm">
                            Rebuild Index
                          </Button>
                          <Button variant="secondary" className="border border-border" size="sm">
                            Settings
                          </Button>
                          <Button variant="secondary" className="border border-border" size="sm">
                            View Logs
                          </Button>
                        </Flex>
                      </Card>

                      {/* Search */}
                      <Card className="border border-border bg-surface shadow-sm">
                        <Flex justifyContent="between" alignItems="center" className="mb-4">
                          <Title className="text-text">Semantic Search</Title>
                          <Badge color="blue">{searchResults.length} results</Badge>
                        </Flex>
                        <TextInput
                          value={query}
                          onValueChange={setQuery}
                          placeholder="Search your codebase semantically..."
                          className="mb-4"
                        />
                        <div className="space-y-3">
                          {searchResults.map((r) => (
                            <div
                              key={r.path}
                              className="group rounded-lg border border-border-subtle bg-surface-raised p-4 transition-all hover:border-primary/50 hover:shadow-md cursor-pointer"
                            >
                              <Flex justifyContent="between" alignItems="start" className="gap-4">
                                <div className="flex-1 min-w-0">
                                  <Flex className="gap-2" alignItems="center">
                                    <FileText className="w-5 h-5 text-text-muted group-hover:text-primary transition-colors" />
                                    <div className="font-mono text-sm text-text truncate">{r.path}</div>
                                  </Flex>
                                  <div className="mt-1 text-xs text-text-subtle ml-7">Lines {r.lines}</div>
                                </div>
                                <Flex className="gap-2 shrink-0" alignItems="center">
                                  <Badge color={statusColor(r.status)} size="xs">{statusLabel(r.status)}</Badge>
                                  <div className={`px-2 py-1 rounded-full text-xs font-semibold ${
                                    r.score > 0.85 ? 'bg-success/20 text-success' : 
                                    r.score > 0.75 ? 'bg-info/20 text-info' : 'bg-text-subtle/20 text-text-subtle'
                                  }`}>
                                    {Math.round(r.score * 100)}%
                                  </div>
                                </Flex>
                              </Flex>
                              <pre className="mt-3 overflow-x-auto rounded-md border border-border-subtle bg-background p-3 text-xs font-mono">
                                <code className="text-text-muted">{r.preview}</code>
                              </pre>
                            </div>
                          ))}
                        </div>
                      </Card>
                    </div>
                  </Col>

                  {/* Right Column: File Tree & Trace */}
                  <Col>
                    <div className="space-y-6">
                      {/* Folder Tree */}
                      <Card className="border border-border bg-surface shadow-sm">
                        <Flex justifyContent="between" alignItems="center" className="mb-4">
                          <Title className="text-text">Indexed Files</Title>
                          <Badge color="gray" size="xs">1,234 files</Badge>
                        </Flex>
                        <div className="max-h-[300px] overflow-y-auto -mx-2">
                          <FolderTree data={sampleFileTree} />
                        </div>
                      </Card>

                      {/* Trace Graph Mini */}
                      <Card className="border border-border bg-surface shadow-sm">
                        <Flex justifyContent="between" alignItems="center" className="mb-4">
                          <Title className="text-text">Trace Index</Title>
                          <Badge color="blue" size="xs">Pro</Badge>
                        </Flex>
                        <TraceGraphMini nodeCount={847} edgeCount={2341} />
                        <Text className="text-text-subtle text-xs mt-3">
                          Symbol relationships and import graph
                        </Text>
                      </Card>

                      {/* LLM Status */}
                      <Card className="border border-border bg-surface shadow-sm">
                        <Title className="text-text mb-4">LLM Services</Title>
                        <div className="space-y-3">
                          <Flex justifyContent="between" alignItems="center" className="p-2 rounded-lg bg-surface-raised">
                            <Flex className="gap-2" alignItems="center">
                              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
                              <Text className="text-text">Ollama</Text>
                            </Flex>
                            <Text className="text-text-subtle text-xs">localhost:11434</Text>
                          </Flex>
                          <Flex justifyContent="between" alignItems="center" className="p-2 rounded-lg bg-surface-raised">
                            <Flex className="gap-2" alignItems="center">
                              <span className="w-2 h-2 rounded-full bg-text-subtle/50" />
                              <Text className="text-text-muted">Lyra</Text>
                            </Flex>
                            <Badge color="gray" size="xs">Disabled</Badge>
                          </Flex>
                        </div>
                      </Card>
                    </div>
                  </Col>
                </Grid>

                {/* Trace Details */}
                <Grid numItems={1} numItemsLg={2} className="gap-6">
                  <Card className="border border-border bg-surface shadow-sm">
                    <Title className="text-text mb-4">Symbol Explorer</Title>
                    <TraceGraph 
                      nodes={sampleTraceNodes} 
                      edges={[]} 
                      selectedNode={selectedTraceNode}
                      onSelectNode={setSelectedTraceNode}
                    />
                  </Card>

                  <Card className="border border-border bg-surface shadow-sm">
                    <Title className="text-text">Context Assembly</Title>
                    <Text className="mt-1 text-text-muted mb-4">Ready-to-use chunks for LLM prompts</Text>

                    <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
                      <Flex justifyContent="between" alignItems="center">
                        <div>
                          <div className="font-mono text-sm text-text">src/prep/server.py</div>
                          <div className="text-xs text-text-subtle">Lines 142–175 • 847 chars</div>
                        </div>
                        <Flex className="gap-2">
                          <Button variant="secondary" className="border border-border" size="xs">
                            Copy
                          </Button>
                          <Button variant="secondary" className="border border-border" size="xs">
                            Expand
                          </Button>
                        </Flex>
                      </Flex>
                      <pre className="mt-3 overflow-x-auto rounded-md border border-border-subtle bg-background p-3 text-xs">
                        <code>
                          <span style={{ color: 'hsl(var(--syntax-comment))' }}># build endpoint</span>
                          {'\n'}
                          <span style={{ color: 'hsl(var(--syntax-keyword))' }}>@</span>
                          <span style={{ color: 'hsl(var(--syntax-function))' }}>app</span>
                          .post(
                          <span style={{ color: 'hsl(var(--syntax-string))' }}>
                            "/projects/{'{'}project_id{'}'}/build"
                          </span>
                          )
                          {'\n'}
                          <span style={{ color: 'hsl(var(--syntax-keyword))' }}>async</span>{' '}
                          <span style={{ color: 'hsl(var(--syntax-keyword))' }}>def</span>{' '}
                          <span style={{ color: 'hsl(var(--syntax-function))' }}>build_project</span>(project_id: str):
                          {'\n    '}
                          <span style={{ color: 'hsl(var(--syntax-string))' }}>
                            """Trigger project index build."""
                          </span>
                        </code>
                      </pre>
                      <Flex className="mt-3 gap-2" alignItems="center">
                        <Badge color="blue" size="xs">Citation</Badge>
                        <Text className="text-text-subtle text-xs">
                          Traceable to file + lines
                        </Text>
                      </Flex>
                    </div>
                  </Card>
                </Grid>
              </div>
            </TabPanel>

            {/* COMPONENTS TAB */}
            <TabPanel>
              <div className="mt-6 space-y-8">
                {/* Color Palette */}
                <Card className="border border-border bg-surface shadow-sm">
                  <Title className="text-text mb-4">Color Palette</Title>
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    {[
                      { name: 'Primary', var: '--primary', className: 'bg-primary' },
                      { name: 'Primary Hover', var: '--primary-hover', className: 'bg-primary-hover' },
                      { name: 'Background', var: '--background', className: 'bg-background border' },
                      { name: 'Surface', var: '--surface', className: 'bg-surface border' },
                      { name: 'Surface Raised', var: '--surface-raised', className: 'bg-surface-raised border' },
                      { name: 'Border', var: '--border', className: 'bg-border' },
                      { name: 'Text', var: '--text', className: 'bg-text' },
                      { name: 'Text Muted', var: '--text-muted', className: 'bg-text-muted' },
                      { name: 'Success', var: '--success', className: 'bg-success' },
                      { name: 'Warning', var: '--warning', className: 'bg-warning' },
                      { name: 'Error', var: '--error', className: 'bg-error' },
                      { name: 'Info', var: '--info', className: 'bg-info' },
                    ].map((color) => (
                      <div key={color.name} className="text-center">
                        <div className={`h-12 rounded-lg ${color.className} border-border`} />
                        <Text className="text-text-muted text-xs mt-2">{color.name}</Text>
                        <Text className="text-text-subtle text-xs font-mono">{color.var}</Text>
                      </div>
                    ))}
                  </div>
                </Card>

                {/* Buttons */}
                <Card className="border border-border bg-surface shadow-sm">
                  <Title className="text-text mb-4">Buttons</Title>
                  <div className="space-y-4">
                    <div>
                      <Text className="text-text-muted text-sm mb-2">Primary</Text>
                      <Flex className="gap-3 flex-wrap">
                        <Button size="xs" className="bg-primary text-white">Extra Small</Button>
                        <Button size="sm" className="bg-primary text-white">Small</Button>
                        <Button className="bg-primary text-white">Default</Button>
                        <Button size="lg" className="bg-primary text-white">Large</Button>
                      </Flex>
                    </div>
                    <div>
                      <Text className="text-text-muted text-sm mb-2">Secondary</Text>
                      <Flex className="gap-3 flex-wrap">
                        <Button size="xs" variant="secondary" className="border border-border">Extra Small</Button>
                        <Button size="sm" variant="secondary" className="border border-border">Small</Button>
                        <Button variant="secondary" className="border border-border">Default</Button>
                        <Button size="lg" variant="secondary" className="border border-border">Large</Button>
                      </Flex>
                    </div>
                  </div>
                </Card>

                {/* Badges */}
                <Card className="border border-border bg-surface shadow-sm">
                  <Title className="text-text mb-4">Badges</Title>
                  <Flex className="gap-3 flex-wrap">
                    <Badge color="green">Success</Badge>
                    <Badge color="yellow">Warning</Badge>
                    <Badge color="red">Error</Badge>
                    <Badge color="blue">Info</Badge>
                    <Badge color="gray">Neutral</Badge>
                    <Badge color="purple">Pro</Badge>
                  </Flex>
                </Card>

                {/* Typography */}
                <Card className="border border-border bg-surface shadow-sm">
                  <Title className="text-text mb-4">Typography</Title>
                  <div className="space-y-4">
                    <div>
                      <Metric className="text-text">Metric: 1,234</Metric>
                    </div>
                    <div>
                      <Title className="text-text">Title: Section Heading</Title>
                    </div>
                    <div>
                      <Text className="text-text">Text (default): Body text content</Text>
                    </div>
                    <div>
                      <Text className="text-text-muted">Text (muted): Secondary content</Text>
                    </div>
                    <div>
                      <Text className="text-text-subtle">Text (subtle): Tertiary content</Text>
                    </div>
                    <div>
                      <Text className="font-mono text-text">Monospace: src/prep/server.py</Text>
                    </div>
                  </div>
                </Card>

                {/* Cards */}
                <Card className="border border-border bg-surface shadow-sm">
                  <Title className="text-text mb-4">Card Styles</Title>
                  <Grid numItems={1} numItemsMd={3} className="gap-4">
                    <Card className="border border-border bg-surface">
                      <Text className="text-text-muted text-sm">Default Card</Text>
                      <Title className="text-text mt-2">Surface Background</Title>
                    </Card>
                    <Card className="border border-border bg-surface-raised">
                      <Text className="text-text-muted text-sm">Raised Card</Text>
                      <Title className="text-text mt-2">Elevated Surface</Title>
                    </Card>
                    <Card className="border-2 border-primary/50 bg-primary/5">
                      <Text className="text-text-muted text-sm">Highlighted Card</Text>
                      <Title className="text-text mt-2">Primary Accent</Title>
                    </Card>
                  </Grid>
                </Card>

                {/* Form Elements */}
                <Card className="border border-border bg-surface shadow-sm">
                  <Title className="text-text mb-4">Form Elements</Title>
                  <Grid numItems={1} numItemsMd={2} className="gap-6">
                    <div>
                      <Text className="text-text-muted text-sm mb-2">Text Input</Text>
                      <TextInput placeholder="Enter search query..." />
                    </div>
                    <div>
                      <Text className="text-text-muted text-sm mb-2">Select</Text>
                      <Select defaultValue="a">
                        <SelectItem value="a">Option A</SelectItem>
                        <SelectItem value="b">Option B</SelectItem>
                        <SelectItem value="c">Option C</SelectItem>
                      </Select>
                    </div>
                  </Grid>
                </Card>

                {/* Progress */}
                <Card className="border border-border bg-surface shadow-sm">
                  <Title className="text-text mb-4">Progress Indicators</Title>
                  <div className="space-y-4">
                    <div>
                      <Text className="text-text-muted text-sm mb-2">Build Progress: 75%</Text>
                      <ProgressBar value={75} color="blue" />
                    </div>
                    <div>
                      <Text className="text-text-muted text-sm mb-2">Index Coverage: 92%</Text>
                      <ProgressBar value={92} color="green" />
                    </div>
                    <div>
                      <Text className="text-text-muted text-sm mb-2">Stale Files: 15%</Text>
                      <ProgressBar value={15} color="yellow" />
                    </div>
                  </div>
                </Card>
              </div>
            </TabPanel>
          </TabPanels>
        </TabGroup>
      </div>
    </div>
  );
}

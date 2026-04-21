import { Button, Section, SettingRow, Select } from '@prep/ui';
import { Image as ImageIcon } from 'lucide-react';
import { SettingsPage } from '../SettingsPage';

// ── Constants (lifted verbatim from SettingsDrawer.tsx:22-43) ─────────────
const MODE_OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

const THEME_OPTIONS = [
  { value: 'none', label: 'Default' },
  { value: 'a', label: 'A: Slate Developer' },
  { value: 'b', label: 'B: Deep Focus' },
  { value: 'c', label: 'C: Signal Green' },
  { value: 'd', label: 'D: Warm Craft' },
  { value: 'e', label: 'E: Neo-Brutalist' },
  { value: 'f', label: 'F: Swiss Minimal' },
  { value: 'g', label: 'G: Glass-Morphic' },
  { value: 'h', label: 'H: Retro-Futurism' },
  { value: 'm', label: 'M: Retro Aurora' },
  { value: 'n', label: 'N: Retro Mirage' },
  { value: 'i', label: 'I: Studio Collage' },
  { value: 'j', label: 'J: Yale Grid' },
  { value: 'k', label: 'K: Inclusive Focus' },
  { value: 'l', label: 'L: Enterprise Console' },
]

export interface AppearancePageProps {
  uiMode: 'light' | 'dark';
  onModeChange: (mode: 'light' | 'dark') => void;
  uiTheme: string;
  onThemeChange: (theme: string) => void;
  bgImage: string | null;
  onBgImageChange: (url: string | null) => void;
}

export function AppearancePage({
  uiMode,
  onModeChange,
  uiTheme,
  onThemeChange,
  bgImage,
  onBgImageChange,
}: AppearancePageProps) {
  // Lifted verbatim from SettingsDrawer.tsx:238-244
  const handleBgUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => onBgImageChange(reader.result as string)
    reader.readAsDataURL(file)
  }

  const bgImageControl = (
    <div className="flex items-center gap-2">
      <label className="flex-1 flex items-center justify-center gap-2 px-3 py-2 border border-dashed border-border rounded cursor-pointer hover:bg-surface-raised transition-colors text-sm text-text-muted">
        <ImageIcon className="w-4 h-4" />
        {bgImage ? 'Change image...' : 'Upload image...'}
        <input type="file" accept="image/*" onChange={handleBgUpload} className="hidden" />
      </label>
      {bgImage && (
        <Button variant="ghost" size="sm" onClick={() => onBgImageChange(null)} className="text-text-muted">
          Remove
        </Button>
      )}
    </div>
  );

  return (
    <SettingsPage
      title="Appearance"
      scope="global"
      description="Theme, colour mode, and background."
    >
      <Section>
        <SettingRow
          id="appearance-color-mode"
          label="Color Mode"
          control={
            <Select
              value={uiMode}
              onChange={(e) => onModeChange(e.target.value as 'light' | 'dark')}
              aria-label="Color Mode"
              size="sm"
              options={MODE_OPTIONS}
            />
          }
        />
        <SettingRow
          id="appearance-theme"
          label="Theme"
          control={
            <Select
              value={uiTheme}
              onChange={(e) => onThemeChange(e.target.value)}
              aria-label="Visual Theme"
              size="sm"
              options={THEME_OPTIONS}
            />
          }
          last
        />
      </Section>

      <Section title="Background Image">
        <SettingRow
          label="Background Image"
          description="Optional image shown behind the dashboard at 10% opacity."
          control={bgImageControl}
          last
        />
      </Section>
    </SettingsPage>
  );
}

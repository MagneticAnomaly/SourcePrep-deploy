import type { Preview } from '@storybook/react';
import React from 'react';
import '../src/styles/index.css';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      disable: true, // We handle background via the decorator and theme
    },
    layout: 'fullscreen',
  },
  globalTypes: {
    theme: {
      name: 'Mode',
      description: 'Light/Dark mode',
      defaultValue: 'dark', // Default to dark for better initial impact
      toolbar: {
        icon: 'circlehollow',
        items: [
          { value: 'light', icon: 'sun', title: 'Light' },
          { value: 'dark', icon: 'moon', title: 'Dark' },
        ],
        showName: true,
      },
    },
    prepTheme: {
      name: 'Visual Style',
      description: 'Prep visual theme direction',
      defaultValue: 'h', // Default to Retro-Futurism as requested
      toolbar: {
        icon: 'paintbrush',
        items: [
          { value: 'none', title: 'Default (Tokens only)' },
          { value: 'a', title: 'A: Slate Developer' },
          { value: 'b', title: 'B: Deep Focus' },
          { value: 'c', title: 'C: Signal Green' },
          { value: 'd', title: 'D: Warm Craft' },
          { value: 'e', title: 'E: Neo-Brutalist' },
          { value: 'f', title: 'F: Swiss Minimal' },
          { value: 'g', title: 'G: Glass-Morphic' },
          { value: 'h', title: 'H: Retro-Futurism' },
          { value: 'm', title: 'M: Retro Aurora' },
          { value: 'n', title: 'N: Retro Mirage' },
          { value: 'i', title: 'I: Studio Collage' },
          { value: 'j', title: 'J: Yale Grid' },
          { value: 'k', title: 'K: Inclusive Focus' },
          { value: 'l', title: 'L: Enterprise Console' },
        ],
        showName: true,
      },
    },
    docsMode: {
      name: 'Docs Mode',
      description: 'Hides dev-only controls (bg upload, etc.) for embedded previews',
      defaultValue: 'false',
      toolbar: {
        icon: 'eye',
        items: [
          { value: 'false', title: 'Dev Mode (show controls)' },
          { value: 'true', title: 'Docs Mode (clean)' },
        ],
      },
    },
  },
  decorators: [
    (Story, context) => {
      const mode = context.globals.theme;
      const prepTheme = context.globals.prepTheme;
      const isDocsMode = context.globals.docsMode === 'true';

      const [bgImage, setBgImage] = React.useState<string | null>(null);
      const bgKey = 'prep_storybook_bg_image';
      
      // Set light/dark mode
      React.useEffect(() => {
        document.documentElement.classList.toggle('dark', mode === 'dark');
        document.documentElement.setAttribute('data-theme', mode);
        
        // Set Prep visual theme (or remove if 'none')
        if (prepTheme && prepTheme !== 'none') {
          document.documentElement.setAttribute('data-prep-theme', prepTheme);
        } else {
          document.documentElement.removeAttribute('data-prep-theme');
        }
      }, [mode, prepTheme]);

      React.useEffect(() => {
        try {
          const stored = window.localStorage.getItem(bgKey);
          if (stored) setBgImage(stored);
        } catch {
          // ignore
        }
      }, []);

      React.useEffect(() => {
        try {
          if (bgImage) window.localStorage.setItem(bgKey, bgImage);
          else window.localStorage.removeItem(bgKey);
        } catch {
          // ignore
        }
      }, [bgImage]);

      const onPickBg: React.ChangeEventHandler<HTMLInputElement> = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
          const result = typeof reader.result === 'string' ? reader.result : null;
          if (result) setBgImage(result);
        };
        reader.readAsDataURL(file);
      };
      
      return (
        <div
          className="min-h-screen w-full bg-background text-foreground font-sans transition-colors duration-200"
          style={
            bgImage
              ? {
                  backgroundImage: `url(${bgImage})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                  backgroundRepeat: 'no-repeat',
                  backgroundAttachment: 'fixed',
                }
              : undefined
          }
        >
          {/* Dev-only background upload toolbar — hidden in docsMode */}
          {!isDocsMode && (
            <div className="pointer-events-none fixed right-3 top-3 z-50">
              <div className="pointer-events-auto rounded-md border border-border bg-background/90 p-2 text-xs shadow-sm">
                <div className="flex items-center gap-2">
                  <label className="cursor-pointer rounded border border-border px-2 py-1">
                    Upload BG
                    <input className="hidden" type="file" accept="image/*" onChange={onPickBg} />
                  </label>
                  <button
                    type="button"
                    className="rounded border border-border px-2 py-1"
                    onClick={() => setBgImage(null)}
                    disabled={!bgImage}
                  >
                    Clear
                  </button>
                </div>
              </div>
            </div>
          )}
          <Story />
        </div>
      );
    },
  ],
};

export default preview;

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
      // Phase 131: default to Slate Developer ('a') so the public storybook
      // boots into a clean, IDE-aligned aesthetic. Pairs with the light
      // Slate Developer manager chrome defined in manager.ts. Visitors can
      // still flip themes via this toolbar. Supersedes Phase 13's earlier
      // Retro-Futurism default.
      defaultValue: 'a',
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
      description: 'Reserved for embedded docs-site previews via StoryEmbed',
      defaultValue: 'false',
      toolbar: {
        icon: 'eye',
        items: [
          { value: 'false', title: 'Dev Mode' },
          { value: 'true', title: 'Docs Mode (clean)' },
        ],
      },
    },
  },
  decorators: [
    (Story, context) => {
      const mode = context.globals.theme;
      const prepTheme = context.globals.prepTheme;

      React.useEffect(() => {
        document.documentElement.classList.toggle('dark', mode === 'dark');
        document.documentElement.setAttribute('data-theme', mode);

        if (prepTheme && prepTheme !== 'none') {
          document.documentElement.setAttribute('data-prep-theme', prepTheme);
        } else {
          document.documentElement.removeAttribute('data-prep-theme');
        }
      }, [mode, prepTheme]);

      return (
        <div className="min-h-screen w-full bg-background text-foreground font-sans transition-colors duration-200">
          <Story />
        </div>
      );
    },
  ],
};

export default preview;

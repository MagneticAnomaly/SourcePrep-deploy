import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  stories: ['../src/**/*.mdx', '../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  addons: [
    '@storybook/addon-links',
    '@storybook/addon-essentials',
    '@storybook/addon-interactions',
  ],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: {
    autodocs: 'tag',
  },
  viteFinal: async (config) => {
    // vite-plugin-dts emits .d.ts files into the Vite outDir, which during
    // `storybook build` is `storybook-static/` — leaking the full @prep/ui
    // type surface (including the ApiClient interface) into the public bundle.
    // Strip it from the Storybook build only; the library build (npm run build)
    // still emits declarations to `dist/`.
    config.plugins = (config.plugins ?? []).filter((plugin) => {
      if (!plugin || Array.isArray(plugin)) return true;
      const name = (plugin as { name?: string }).name;
      return name !== 'vite:dts';
    });
    return config;
  },
};

export default config;

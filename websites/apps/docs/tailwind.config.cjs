const preset = require('../../tailwind.preset.cjs');

module.exports = {
  presets: [preset],
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    '../../../packages/ui/src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      typography: (theme) => ({
        DEFAULT: {
          css: {
            '--tw-prose-body': theme('colors.text.muted'),
            '--tw-prose-headings': theme('colors.text.DEFAULT'),
            '--tw-prose-lead': theme('colors.text.muted'),
            '--tw-prose-links': theme('colors.primary.DEFAULT'),
            '--tw-prose-bold': theme('colors.text.DEFAULT'),
            '--tw-prose-counters': theme('colors.text.muted'),
            '--tw-prose-bullets': theme('colors.text.muted'),
            '--tw-prose-hr': theme('colors.border.DEFAULT'),
            '--tw-prose-quotes': theme('colors.text.muted'),
            '--tw-prose-quote-borders': theme('colors.primary.DEFAULT'),
            '--tw-prose-captions': theme('colors.text.subtle'),
            '--tw-prose-code': theme('colors.text.DEFAULT'),
            '--tw-prose-pre-code': theme('colors.text.DEFAULT'),
            '--tw-prose-pre-bg': theme('colors.surface.DEFAULT'),
            '--tw-prose-th-borders': theme('colors.border.DEFAULT'),
            '--tw-prose-td-borders': theme('colors.border.DEFAULT'),
            maxWidth: 'none',
            h1: {
              fontWeight: '700',
              letterSpacing: '-0.025em',
              color: theme('colors.text.DEFAULT'),
            },
            h2: {
              fontWeight: '600',
              letterSpacing: '-0.025em',
              marginTop: '2em',
              color: theme('colors.text.DEFAULT'),
            },
            h3: {
              fontWeight: '600',
              marginTop: '1.5em',
              color: theme('colors.text.DEFAULT'),
            },
            h4: {
              color: theme('colors.text.DEFAULT'),
            },
            'code::before': {
              content: '""',
            },
            'code::after': {
              content: '""',
            },
            code: {
              fontWeight: '400',
              backgroundColor: theme('colors.surface.DEFAULT'),
              border: `1px solid ${theme('colors.border.subtle')}`,
              borderRadius: '0.25rem',
              padding: '0.125rem 0.25rem',
              color: theme('colors.text.DEFAULT'),
            },
            pre: {
              backgroundColor: theme('colors.surface.DEFAULT'),
              border: `1px solid ${theme('colors.border.subtle')}`,
              borderRadius: '0.5rem',
              color: theme('colors.text.DEFAULT'),
            },
          },
        },
      }),
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};

import type { CliScript } from '@prep/ui';

export type DemoTool =
  | 'prep'
  | 'prep_search'
  | 'prep_impact'
  | 'prep_audit'
  | 'prep_observe'
  | 'prep_concepts'
  | 'ide';

export interface DemoVariant {
  id: string;
  tool: DemoTool;
  label: string;
  note?: string;
  script: CliScript;
}

const impactRename: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'rename `getUserData` to `fetchUserProfile`',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_impact',
      args: '"getUserData"',
      durationMs: 900,
      statusText: 'Tracing callers…',
    },
    {
      type: 'tool_result',
      text: '14 callers · 6 files · 1 in public API surface',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: '`getUserData` has 14 callers across 6 files — including `api/public/users.ts`, which looks like part of your public surface.\n\nSafer to add `fetchUserProfile` as an alias and deprecate `getUserData` with a JSDoc notice, rather than a naked rename. Want me to do that?',
      typewriterDelayMs: 12,
    },
  ],
};

export const variants: DemoVariant[] = [
  {
    id: 'impact-rename',
    tool: 'prep_impact',
    label: 'Rename with public API surface',
    note: 'Ordinary rename request — impact fires because the agent knows to check before renaming. Value shows up in the recommendation (alias vs. naked rename).',
    script: impactRename,
  },
];

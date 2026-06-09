import type { Meta, StoryObj } from '@storybook/react';
import { ToastProvider, useToast } from './Toast';

function Demo() {
  const { push } = useToast();
  return (
    <div className="p-6 space-x-2">
      <button
        className="px-3 py-1.5 rounded bg-slate-800 text-slate-100"
        onClick={() =>
          push({
            title: 'Run cancelled for SourcePrep',
            body: 'Auto is on — next file change or 5-min check will restart it.',
            action: { label: 'Switch to Manual', onClick: () => alert('switched') },
            variant: 'info',
          })
        }
      >
        info toast (B)
      </button>
      <button
        className="px-3 py-1.5 rounded bg-amber-800 text-amber-100"
        onClick={() =>
          push({
            title: 'Looks like this keeps restarting',
            body: "You've cancelled this project 2 times in the last 5 minutes. Switch to manual to break the loop?",
            action: { label: 'Switch to Manual', onClick: () => alert('switched') },
            variant: 'warn',
            durationMs: 0,
          })
        }
      >
        warn toast (heuristic)
      </button>
    </div>
  );
}

const meta: Meta<typeof Demo> = {
  title: 'Primitives/Toast',
  decorators: [
    (Story) => (
      <ToastProvider>
        <Story />
      </ToastProvider>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof Demo>;
export const Playground: Story = { render: () => <Demo /> };

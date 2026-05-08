import type { Meta, StoryObj } from '@storybook/react';

function KbdRow({ keys }: { keys: string[] }) {
  return (
    <div className="flex items-center gap-2">
      {keys.map((k, idx) => (
        <span key={`${k}-${idx}`} className="flex items-center gap-2">
          <kbd className="kbc-button">{k}</kbd>
          {idx < keys.length - 1 && <span className="text-sm text-gray-500">+</span>}
        </span>
      ))}
    </div>
  );
}

const meta: Meta = {
  title: 'Patterns/KeyboardShortcuts',
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;

type Story = StoryObj;

export const Examples: Story = {
  render: () => (
    <div className="space-y-6">
      <div>
        <div className="text-sm font-medium">Re-render page</div>
        <div className="mt-2">
          <KbdRow keys={['Ctrl', 'Shift', 'R']} />
        </div>
      </div>

      <div>
        <div className="text-sm font-medium">Search</div>
        <div className="mt-2">
          <KbdRow keys={['Cmd', 'K']} />
        </div>
      </div>

      <div>
        <div className="text-sm font-medium">Sizes</div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <kbd className="kbc-button kbc-button-xxs">XXS</kbd>
          <kbd className="kbc-button kbc-button-xs">XS</kbd>
          <kbd className="kbc-button kbc-button-sm">SM</kbd>
          <kbd className="kbc-button">MD</kbd>
          <kbd className="kbc-button kbc-button-lg">LG</kbd>
        </div>
      </div>
    </div>
  ),
};

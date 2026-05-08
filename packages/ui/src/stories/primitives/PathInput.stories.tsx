import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { PathInput } from '../../components/primitives/PathInput';

const meta: Meta<typeof PathInput> = {
  title: 'Primitives/PathInput',
  component: PathInput,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
  argTypes: {
    directory: {
      control: 'boolean',
      description: 'Whether to pick directories (true) or files (false)',
    },
    disabled: {
      control: 'boolean',
    },
  },
};

export default meta;
type Story = StoryObj<typeof PathInput>;

// Interactive wrapper that manages state
function PathInputDemo(props: Omit<React.ComponentProps<typeof PathInput>, 'value' | 'onChange'> & { initialValue?: string }) {
  const { initialValue = '', ...rest } = props;
  const [value, setValue] = useState(initialValue);
  return <PathInput value={value} onChange={setValue} {...rest} />;
}

export const Default: Story = {
  render: () => (
    <PathInputDemo
      label="Project Path"
      placeholder="/path/to/your/project"
      hint="Absolute path to the project root directory"
    />
  ),
};

export const WithValue: Story = {
  render: () => (
    <PathInputDemo
      label="Project Path"
      initialValue="/Users/dev/my-project"
      hint="Absolute path to the project root directory"
    />
  ),
};

export const CustomIndexPath: Story = {
  render: () => (
    <PathInputDemo
      label="Index Location"
      placeholder="/fast-drive/prep-indexes"
      hint="Path where the index database will be stored"
    />
  ),
};

export const FilePicker: Story = {
  render: () => (
    <PathInputDemo
      label="Select a File"
      placeholder="/path/to/file.ts"
      hint="Pick a specific file"
      directory={false}
    />
  ),
};

export const Disabled: Story = {
  render: () => (
    <PathInputDemo
      label="Read-only Path"
      initialValue="/locked/path"
      disabled
    />
  ),
};

export const DragAndDrop: Story = {
  render: () => (
    <div className="space-y-4">
      <p className="text-sm text-text-muted">
        Try dragging a folder from Finder / Explorer onto the input below.
        The border will highlight on hover.
      </p>
      <PathInputDemo
        label="Drop a Folder Here"
        placeholder="Drag a folder onto this input..."
        hint="Supports drag-and-drop from your file manager"
      />
    </div>
  ),
};

export const NoPicker: Story = {
  name: 'No Picker (Text Only)',
  render: () => (
    <div className="space-y-4">
      <p className="text-sm text-text-muted">
        When <code>pickerMode="none"</code>, the browse button is hidden.
        Useful for admin config screens or environments without file dialog support.
      </p>
      <PathInputDemo
        label="Index Storage Path"
        placeholder="/fast-drive/prep-indexes"
        hint="Manual text entry only — no file picker button"
        pickerMode="none"
      />
    </div>
  ),
};

export const CustomBrowse: Story = {
  name: 'Custom Browse Handler',
  render: () => {
    const Demo = () => {
      const [value, setValue] = useState('');
      return (
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            When <code>pickerMode="custom"</code>, clicking the browse button calls
            your <code>onBrowse</code> callback. Use this in VS Code WebViews to
            postMessage to the extension host.
          </p>
          <PathInput
            label="Custom Handler"
            value={value}
            onChange={setValue}
            placeholder="/path/from/custom/dialog"
            hint="Browse button delegates to onBrowse callback"
            pickerMode="custom"
            onBrowse={() => {
              // Simulate an async dialog returning a path
              setValue('/Users/team/projects/selected-via-custom');
            }}
          />
        </div>
      );
    };
    return <Demo />;
  },
};

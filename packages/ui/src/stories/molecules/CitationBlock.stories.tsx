import type { Meta, StoryObj } from '@storybook/react';
import { CitationBlock } from '../../components/context/CitationBlock';

const meta: Meta<typeof CitationBlock> = {
  title: 'Foundations/Molecules/CitationBlock',
  component: CitationBlock,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof CitationBlock>;

export const Default: Story = {
  render: () => (
    <div className="space-y-2 max-w-lg">
      <CitationBlock
        sourcePath="src/prep/core/indexer.py"
        span={{ start_line: 45, end_line: 78 }}
        score={0.92}
        showScore
      />
      <CitationBlock
        sourcePath="src/prep/api/routes.py"
        span={{ start_line: 120, end_line: 145 }}
      />
      <CitationBlock sourcePath="README.md" />
    </div>
  ),
};

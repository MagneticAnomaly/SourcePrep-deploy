import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { SymbolSearchInput } from '../../components/trace/SymbolSearchInput';
import { SymbolResultRow } from '../../components/trace/SymbolResultRow';
import type { TraceNode } from '../../types';

const meta: Meta = {
  title: 'Dashboard/Search/SymbolSearch',
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;

export const SearchInput: StoryObj<typeof SymbolSearchInput> = {
  render: () => {
    const [val, setVal] = useState('');
    return <SymbolSearchInput value={val} onChange={setVal} />;
  },
};

const mockResult: TraceNode = {
  id: '1',
  name: 'UserService',
  kind: 'symbol',
  file_path: 'src/services/user.ts',
  language: 'TypeScript',
  metadata: {
    symbol_type: 'class',
    is_public: true,
    docstring: 'Handles user authentication and profile management.',
  },
  span: { start_line: 10, end_line: 150 },
};

export const ResultRow: StoryObj<typeof SymbolResultRow> = {
  render: () => (
    <div className="w-96 space-y-2">
      <SymbolResultRow node={mockResult} />
      <SymbolResultRow node={mockResult} selected />
    </div>
  ),
};

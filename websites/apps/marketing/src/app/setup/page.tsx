import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'MCP Setup — Connect SourcePrep to Your AI Editor',
  description:
    'Copy-paste MCP configuration for Claude Code, Cursor, Windsurf, GitHub Copilot, Gemini CLI, Zed, and more. One command to give your AI assistant structural code intelligence.',
  keywords: [
    'SourcePrep MCP setup',
    'Claude Code MCP',
    'Cursor MCP config',
    'Windsurf MCP config',
    'GitHub Copilot MCP',
    'Gemini CLI MCP',
    'Model Context Protocol',
    'AI code context',
    'MCP server configuration',
  ],
  alternates: {
    canonical: 'https://sourceprep.io/setup',
  },
};

import ClientPage from './ClientPage';

export default function SetupPage() {
  return <ClientPage />;
}

/**
 * Agent Animation Event Types (Phase 69)
 *
 * These types define the scriptable events that drive the playback
 * engines for both the AnimatedCLI and AnimatedIDE components.
 */

export type CliEvent =
  | CliUserInput
  | CliAgentThinking
  | CliToolCall
  | CliToolResult
  | CliAgentOutput
  | CliFileOpen
  | CliCodeEdit
  | CliPause
  | CliClear;

export interface CliUserInput {
  type: 'user_input';
  text: string;
  typingDelayMs?: number;
}

export interface CliAgentThinking {
  type: 'agent_thinking';
  durationMs: number;
  label?: string;
}

export interface CliToolCall {
  type: 'tool_call';
  tool: string;
  args: string;
  durationMs: number;
  statusText?: string;
}

export interface CliToolResult {
  type: 'tool_result';
  text: string;
  status?: 'success' | 'error' | 'info';
}

export interface CliAgentOutput {
  type: 'agent_output';
  text: string;
  typewriter?: boolean;
  typewriterDelayMs?: number;
}

// IDE-specific events
export interface CliFileOpen {
  type: 'file_open';
  filePath: string;
  language: string;
  content: string;
  durationMs?: number;
}

export interface CliCodeEdit {
  type: 'code_edit';
  filePath: string;
  diffText?: string;     // For showing a side-by-side diff
  newContent?: string;   // For direct replacement
  durationMs: number;
}

export interface CliPause {
  type: 'pause';
  durationMs: number;
}

export interface CliClear {
  type: 'clear';
}

export interface CliScript {
  title?: string;
  events: CliEvent[];
  loop?: boolean;
  loopDelayMs?: number;
}

export type TerminalTheme = 'dark' | 'claude' | 'minimal';

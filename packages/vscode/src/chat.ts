import * as vscode from 'vscode';
import { CodragDaemonClient } from './client';

export function registerChatParticipant(context: vscode.ExtensionContext, client: CodragDaemonClient) {
  const handler: vscode.ChatRequestHandler = async (request, context, stream, token) => {
    stream.progress('Searching codebase...');
    
    try {
      // Basic RAG implementation for chat
      // 1. Search for relevant context
      const searchResp = await client.search('current', request.prompt, 5, 0.1);
      
      if (searchResp.results.length === 0) {
        stream.markdown('I couldn\'t find any relevant code in the index to answer that.');
        return;
      }

      // 2. Present findings
      stream.markdown('Here is what I found in the codebase:\n\n');
      
      for (const result of searchResp.results) {
        stream.markdown(`**${result.source_path}** (Lines ${result.span.start_line}-${result.span.end_line})\n`);
        stream.markdown('```typescript\n'); // Assuming TS for now, realistically need lang detection
        stream.markdown(result.preview);
        stream.markdown('\n```\n\n');
      }

      stream.markdown('\n_Note: This is a placeholder chat participant. Full LLM integration coming soon._');
      
    } catch (err) {
      stream.markdown(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const participant = vscode.chat.createChatParticipant('codrag.chat', handler);
  participant.iconPath = vscode.Uri.joinPath(context.extensionUri, 'media', 'codrag-icon.png');
  context.subscriptions.push(participant);
}

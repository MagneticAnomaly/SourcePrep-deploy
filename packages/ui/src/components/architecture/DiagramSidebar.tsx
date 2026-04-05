import { memo, useState, useCallback } from 'react';
import type { Node } from '@xyflow/react';
import type {
  ArchNote, ArchNoteCreate, ACR, LinkedIssue,
  ModuleNodeData, FileNodeData,
} from '../../types/architecture';

// ── Note card ─────────────────────────────────────────────────────

function SidebarNoteCard({ note, onUpdate, onDelete }: { note: ArchNote; onUpdate: (content: string) => void; onDelete: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.content);

  const handleSave = useCallback(() => {
    if (draft.trim() && draft !== note.content) {
      onUpdate(draft.trim());
    }
    setEditing(false);
  }, [draft, note.content, onUpdate]);

  return (
    <div className="mb-2 p-2 rounded bg-zinc-900 border border-zinc-800">
      <div className="flex justify-between items-start">
        <span className="text-[10px] text-zinc-500">
          {note.note_type === 'adr' ? '📌 ADR' : note.note_type === 'agent_note' ? '🤖 Agent' : '💬'}
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => { setEditing(!editing); setDraft(note.content); }}
            className="text-[10px] text-zinc-600 hover:text-zinc-300"
          >
            {editing ? 'cancel' : 'edit'}
          </button>
          <button onClick={onDelete} className="text-[10px] text-zinc-600 hover:text-red-400">
            delete
          </button>
        </div>
      </div>
      {editing ? (
        <>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleSave(); }}
            className="w-full mt-1 bg-transparent border border-zinc-600 rounded text-xs text-zinc-200 p-1 resize-none"
            rows={3}
            autoFocus
          />
          <button
            onClick={handleSave}
            className="mt-1 text-[10px] px-2 py-0.5 bg-zinc-700 rounded text-zinc-300 hover:bg-zinc-600"
          >
            Save
          </button>
        </>
      ) : (
        <p className="text-xs text-zinc-300 mt-1">{note.content}</p>
      )}
      <span className="text-[10px] text-zinc-600">— {note.author}</span>
    </div>
  );
}

// ── Add note form ─────────────────────────────────────────────────

function AddNoteForm({ nodeId, onCreateNote }: { nodeId: string; onCreateNote: (n: ArchNoteCreate) => void }) {
  const [content, setContent] = useState('');
  const [noteType, setNoteType] = useState<'comment' | 'adr'>('comment');

  const handleSubmit = useCallback(() => {
    if (!content.trim()) return;
    onCreateNote({ node_id: nodeId, content: content.trim(), note_type: noteType, author: 'user' });
    setContent('');
  }, [content, noteType, nodeId, onCreateNote]);

  return (
    <div className="mt-2">
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Add a note..."
        className="w-full bg-zinc-900 border border-zinc-700 rounded text-xs text-zinc-200 p-2 resize-none"
        rows={2}
      />
      <div className="flex items-center gap-2 mt-1">
        <select
          value={noteType}
          onChange={(e) => setNoteType(e.target.value as 'comment' | 'adr')}
          className="text-[10px] bg-zinc-800 border border-zinc-700 rounded px-1 py-0.5 text-zinc-400"
        >
          <option value="comment">Comment</option>
          <option value="adr">ADR</option>
        </select>
        <button
          onClick={handleSubmit}
          disabled={!content.trim()}
          className="text-[10px] px-2 py-0.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-white"
        >
          Add
        </button>
      </div>
    </div>
  );
}

// ── Main sidebar ──────────────────────────────────────────────────

export interface DiagramSidebarProps {
  selectedNode: Node;
  notes: ArchNote[];
  acrs: ACR[];
  issueLinks: LinkedIssue[];
  onClose: () => void;
  onCreateNote: (note: ArchNoteCreate) => void;
  onUpdateNote: (noteId: string, content: string) => void;
  onDeleteNote: (noteId: string) => void;
}

function DiagramSidebarInner({
  selectedNode, notes, acrs, issueLinks,
  onClose, onCreateNote, onUpdateNote, onDeleteNote,
}: DiagramSidebarProps) {
  const nodeNotes = notes.filter((n) => n.node_id === selectedNode.id);
  const nodeACRs = acrs.filter((a) => a.affected_nodes.includes(selectedNode.id));
  const nodeIssues = issueLinks.filter((l) => l.node_id === selectedNode.id);

  return (
    <div className="w-80 border-l border-zinc-800 bg-zinc-950/90 backdrop-blur-sm overflow-y-auto">
      <div className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-zinc-200 truncate">
            {(selectedNode.data as any).label}
          </h3>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300 text-xs"
          >
            {'x'}
          </button>
        </div>

        {/* Description */}
        {(selectedNode.data as any).description && (
          <p className="text-xs text-zinc-400 mb-4">{(selectedNode.data as any).description}</p>
        )}

        {/* Node metadata */}
        <div className="text-xs text-zinc-500 space-y-1 mb-4">
          {selectedNode.type === 'module' && (() => {
            const d = selectedNode.data as unknown as ModuleNodeData;
            return (
              <>
                <div>Files: {d.fileCount}</div>
                <div>Status: {d.componentStatus}</div>
                <div>Confidence: {(d.confidence * 100).toFixed(0)}%</div>
              </>
            );
          })()}
          {selectedNode.type === 'file' && (() => {
            const d = selectedNode.data as unknown as FileNodeData;
            return (
              <>
                <div>Path: {d.path}</div>
                <div>Language: {d.language}</div>
                <div>Lines: {d.lineCount}</div>
              </>
            );
          })()}
        </div>

        {/* Linked Issues */}
        {nodeIssues.length > 0 && (
          <div className="border-t border-zinc-800 pt-3 mb-3">
            <h4 className="text-xs font-medium text-zinc-400 mb-2">
              Issues ({nodeIssues.length})
            </h4>
            {nodeIssues.map((issue) => (
              <div key={issue.paperclip_issue_id} className="mb-1.5 p-2 rounded bg-zinc-900 border border-zinc-800">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold ${
                    issue.priority === 'P0' || issue.priority === 'P1' ? 'text-red-400' : 'text-amber-400'
                  }`}>
                    {issue.priority}
                  </span>
                  <span className="text-xs text-zinc-300 truncate">{issue.title}</span>
                </div>
                <span className="text-[10px] text-zinc-500">{issue.paperclip_issue_id} - {issue.status}</span>
              </div>
            ))}
          </div>
        )}

        {/* ACRs */}
        {nodeACRs.length > 0 && (
          <div className="border-t border-zinc-800 pt-3 mb-3">
            <h4 className="text-xs font-medium text-zinc-400 mb-2">
              ACRs ({nodeACRs.length})
            </h4>
            {nodeACRs.map((acr) => (
              <div key={acr.id} className="mb-1.5 p-2 rounded bg-zinc-900 border border-amber-800/50">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] text-amber-400">{'\u26a0\ufe0f'}</span>
                  <span className="text-xs text-zinc-200 truncate">{acr.title}</span>
                </div>
                <p className="text-[10px] text-zinc-400 mb-1">{acr.description}</p>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    acr.status === 'approved' ? 'bg-green-900/50 text-green-400' :
                    acr.status === 'rejected' ? 'bg-red-900/50 text-red-400' :
                    acr.status === 'completed' ? 'bg-blue-900/50 text-blue-400' :
                    'bg-amber-900/50 text-amber-400'
                  }`}>
                    {acr.status}
                  </span>
                  <span className="text-[10px] text-zinc-500">by {acr.source_agent}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Notes */}
        <div className="border-t border-zinc-800 pt-3">
          <h4 className="text-xs font-medium text-zinc-400 mb-2">
            Notes ({nodeNotes.length})
          </h4>
          {nodeNotes.map((note) => (
            <SidebarNoteCard
              key={note.id}
              note={note}
              onUpdate={(content) => onUpdateNote(note.id, content)}
              onDelete={() => onDeleteNote(note.id)}
            />
          ))}

          <AddNoteForm nodeId={selectedNode.id} onCreateNote={onCreateNote} />
        </div>
      </div>
    </div>
  );
}

export const DiagramSidebar = memo(DiagramSidebarInner);

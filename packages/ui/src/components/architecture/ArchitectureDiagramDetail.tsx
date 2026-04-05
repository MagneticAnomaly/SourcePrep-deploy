import { useCallback, useMemo, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  MiniMap,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  BackgroundVariant,
  type Viewport,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import ELK from 'elkjs/lib/elk.bundled.js';

import type {
  ArchGraphResponse, ArchNote,
  ModuleNodeData, FileNodeData, ExternalRefNodeData,
  ArchBreadcrumb, ArchNoteCreate,
} from '../../types/architecture';
import { ModuleNode } from './ModuleNode';
import { FileNode } from './FileNode';
import { ExternalRefNode } from './ExternalRefNode';
import { AnnotationNode } from './AnnotationNode';
import { EntryPointNode } from './EntryPointNode';
import { DependencyEdge } from './DependencyEdge';
import { BreadcrumbNav } from './BreadcrumbNav';
import { DiagramToolbar } from './DiagramToolbar';
import { DiagramSidebar } from './DiagramSidebar';

const elk = new ELK();

const nodeTypes: NodeTypes = {
  module: ModuleNode as any,
  file: FileNode as any,
  externalRef: ExternalRefNode as any,
  annotation: AnnotationNode as any,
  entryPoint: EntryPointNode as any,
};

const edgeTypes: EdgeTypes = {
  dependency: DependencyEdge as any,
};

export interface ArchitectureDiagramDetailProps {
  graph: ArchGraphResponse | null;
  notes: ArchNote[];
  layerPath: string[];
  loading: boolean;
  onDrillInto: (moduleId: string) => void;
  onNavigateToLayer: (path: string[]) => void;
  onSavePositions: (positions: Array<{ id: string; x: number; y: number }>, viewport: Viewport) => void;
  onCreateNote: (note: ArchNoteCreate) => void;
  onUpdateNote: (noteId: string, content: string) => void;
  onDeleteNote: (noteId: string) => void;
  onSelectNode: (nodeId: string | null) => void;
  selectedNodeId: string | null;
  savedPositions?: Array<{ id: string; x: number; y: number }>;
  savedViewport?: Viewport;
}

function noteCountForNode(nodeId: string, notes: ArchNote[]): number {
  return notes.filter((n) => n.node_id === nodeId).length;
}

function buildFlowNodes(
  graph: ArchGraphResponse,
  notes: ArchNote[],
  savedPositions?: Array<{ id: string; x: number; y: number }>,
): Node[] {
  const posMap = new Map(savedPositions?.map((p) => [p.id, p]) ?? []);
  const flowNodes: Node[] = [];

  for (const mod of graph.modules) {
    const pos = posMap.get(mod.id);
    flowNodes.push({
      id: mod.id,
      type: 'module',
      position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      data: {
        label: mod.name,
        description: mod.description,
        fileCount: mod.file_count,
        hubFiles: mod.hub_files ?? [],
        domainTags: mod.domain_tags ?? [],
        componentStatus: mod.component_status ?? 'complete',
        confidence: mod.avg_confidence ?? 0,
        noteCount: noteCountForNode(mod.id, notes),
        isHub: (mod.hub_files?.length ?? 0) > 0,
      } satisfies ModuleNodeData,
    });
  }

  for (const file of graph.files) {
    const pos = posMap.get(file.id);
    const name = file.path.split('/').pop() ?? file.path;
    flowNodes.push({
      id: file.id,
      type: 'file',
      position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      data: {
        label: name,
        path: file.path,
        language: file.language,
        hubScore: file.hub_score,
        confidence: file.confidence,
        summary: file.summary,
        lineCount: file.line_count,
        noteCount: noteCountForNode(file.id, notes),
        isHub: file.hub_score > 5,
      } satisfies FileNodeData,
    });
  }

  for (const ext of graph.external_refs) {
    const pos = posMap.get(ext.id);
    flowNodes.push({
      id: ext.id,
      type: 'externalRef',
      position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      data: {
        label: ext.summary || ext.id,
        moduleId: ext.module_id,
        description: ext.summary,
      } satisfies ExternalRefNodeData,
    });
  }

  return flowNodes;
}

function buildFlowEdges(graph: ArchGraphResponse): Edge[] {
  return graph.edges.map((e, i) => ({
    id: `edge-${i}`,
    source: e.source,
    target: e.target,
    type: 'dependency',
    data: { kind: e.kind, count: e.count },
  }));
}

async function autoLayout(nodes: Node[], edges: Edge[]): Promise<Node[]> {
  const elkGraph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '60',
      'elk.layered.spacing.nodeNodeBetweenLayers': '80',
    },
    children: nodes.map((n) => ({
      id: n.id,
      width: 220,
      height: n.type === 'module' ? 120 : n.type === 'annotation' || n.type === 'entryPoint' ? 80 : 60,
    })),
    edges: edges.map((e) => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  };

  const laid = await elk.layout(elkGraph);
  const posMap = new Map(laid.children?.map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]) ?? []);
  return nodes.map((n) => {
    const pos = posMap.get(n.id);
    return pos ? { ...n, position: pos } : n;
  });
}

function DiagramCanvas(props: ArchitectureDiagramDetailProps) {
  const {
    graph, notes, layerPath, loading,
    onDrillInto, onNavigateToLayer, onSavePositions,
    onCreateNote, onUpdateNote, onDeleteNote,
    onSelectNode, selectedNodeId,
    savedPositions, savedViewport,
  } = props;

  const initialNodes = useMemo(
    () => graph ? buildFlowNodes(graph, notes, savedPositions) : [],
    [graph, notes, savedPositions],
  );
  const initialEdges = useMemo(
    () => graph ? buildFlowEdges(graph) : [],
    [graph],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const needsLayoutRef = useRef(!savedPositions?.length);
  const viewportRef = useRef<Viewport>(savedViewport ?? { x: 0, y: 0, zoom: 0.8 });

  // Sync nodes/edges when graph data changes, then auto-layout if no saved positions
  useEffect(() => {
    const newNodes = graph ? buildFlowNodes(graph, notes, savedPositions) : [];
    const newEdges = graph ? buildFlowEdges(graph) : [];
    const shouldLayout = !savedPositions?.length && newNodes.length > 0;

    if (shouldLayout) {
      needsLayoutRef.current = true;
      autoLayout(newNodes, newEdges).then((laid) => {
        setNodes(laid);
        needsLayoutRef.current = false;
      });
    } else {
      setNodes(newNodes);
    }
    setEdges(newEdges);
  }, [graph, notes, savedPositions, setNodes, setEdges]);

  const handleAutoLayout = useCallback(async () => {
    const laid = await autoLayout(nodes, edges);
    setNodes(laid);
  }, [nodes, edges, setNodes]);

  // ── Layout persistence: save on drag end and viewport change ──
  const handleNodeDragStop = useCallback(() => {
    const positions = nodes.map((n) => ({ id: n.id, x: n.position.x, y: n.position.y }));
    onSavePositions(positions, viewportRef.current);
  }, [nodes, onSavePositions]);

  const handleMoveEnd = useCallback((_event: any, viewport: Viewport) => {
    viewportRef.current = viewport;
    // Save positions + viewport together
    const positions = nodes.map((n) => ({ id: n.id, x: n.position.x, y: n.position.y }));
    onSavePositions(positions, viewport);
  }, [nodes, onSavePositions]);

  const handleNodeDoubleClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.type === 'module') {
      onDrillInto(node.id);
    } else if (node.type === 'externalRef') {
      const data = node.data as unknown as ExternalRefNodeData;
      onNavigateToLayer([data.moduleId]);
    }
  }, [onDrillInto, onNavigateToLayer]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    onSelectNode(node.id);
  }, [onSelectNode]);

  const handlePaneClick = useCallback(() => {
    onSelectNode(null);
  }, [onSelectNode]);

  const breadcrumbs: ArchBreadcrumb[] = useMemo(() => {
    const crumbs: ArchBreadcrumb[] = [{ label: 'System Overview', layerPath: [] }];
    for (let i = 0; i < layerPath.length; i++) {
      crumbs.push({
        label: layerPath[i],
        layerPath: layerPath.slice(0, i + 1),
      });
    }
    return crumbs;
  }, [layerPath]);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500">
        Loading architecture diagram...
      </div>
    );
  }

  if (!graph || !graph.exists) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-zinc-500">
        <span className="text-lg">No architecture data</span>
        <span className="text-sm">Run the pipeline to generate module synthesis first.</span>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col">
        {/* Breadcrumb */}
        <BreadcrumbNav breadcrumbs={breadcrumbs} onNavigateToLayer={onNavigateToLayer} />

        {/* Toolbar */}
        <DiagramToolbar
          onAutoLayout={handleAutoLayout}
          onGoBack={layerPath.length > 0 ? () => onNavigateToLayer(layerPath.slice(0, -1)) : null}
          stats={graph.stats}
        />

        {/* React Flow Canvas */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeDoubleClick={handleNodeDoubleClick}
            onNodeClick={handleNodeClick}
            onNodeDragStop={handleNodeDragStop}
            onMoveEnd={handleMoveEnd}
            onPaneClick={handlePaneClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            defaultViewport={savedViewport ?? { x: 0, y: 0, zoom: 0.8 }}
            fitView={!savedViewport}
            colorMode="dark"
            minZoom={0.1}
            maxZoom={2}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#27272a" />
            <MiniMap
              nodeColor={(n) => n.type === 'module' ? '#3b82f6' : n.type === 'externalRef' ? '#6b7280' : '#a855f7'}
              className="!bg-zinc-900 !border-zinc-700"
            />
            <Controls className="!bg-zinc-900 !border-zinc-700 [&>button]:!bg-zinc-800 [&>button]:!border-zinc-700 [&>button]:!text-zinc-400" />

            <svg>
              <defs>
                <marker id="arch-diagram-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7280" />
                </marker>
              </defs>
            </svg>
          </ReactFlow>
        </div>
      </div>

      {/* Sidebar */}
      {selectedNode && (
        <DiagramSidebar
          selectedNode={selectedNode}
          notes={notes}
          acrs={[]}
          issueLinks={[]}
          onClose={() => onSelectNode(null)}
          onCreateNote={onCreateNote}
          onUpdateNote={onUpdateNote}
          onDeleteNote={onDeleteNote}
        />
      )}
    </div>
  );
}

export function ArchitectureDiagramDetail(props: ArchitectureDiagramDetailProps) {
  return (
    <ReactFlowProvider>
      <DiagramCanvas {...props} />
    </ReactFlowProvider>
  );
}

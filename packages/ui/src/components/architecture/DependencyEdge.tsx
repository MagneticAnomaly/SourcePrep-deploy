import { memo } from 'react';
import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react';

interface DependencyEdgeData {
  kind: 'imports' | 'calls' | 'inferred';
  count: number;
}

const KIND_STYLES: Record<string, { stroke: string; dashArray?: string }> = {
  imports: { stroke: '#3b82f6' },
  calls: { stroke: '#22c55e', dashArray: '6 3' },
  inferred: { stroke: '#f59e0b', dashArray: '3 3' },
};

function DependencyEdgeInner(props: EdgeProps & { data?: DependencyEdgeData }) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props;
  const kind = data?.kind ?? 'imports';
  const count = data?.count ?? 1;
  const style = KIND_STYLES[kind] ?? KIND_STYLES.imports;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition,
  });

  return (
    <>
      <BaseEdge
        path={edgePath}
        style={{
          stroke: style.stroke,
          strokeWidth: count > 5 ? 3 : count > 1 ? 2 : 1.5,
          strokeDasharray: style.dashArray,
        }}
        markerEnd="url(#arch-diagram-arrow)"
      />
      {count > 1 && (
        <foreignObject x={labelX - 12} y={labelY - 10} width={24} height={20} className="pointer-events-none">
          <div className="flex items-center justify-center w-full h-full">
            <span className="text-[10px] bg-zinc-800 text-zinc-400 px-1 rounded border border-zinc-700">
              {count}
            </span>
          </div>
        </foreignObject>
      )}
    </>
  );
}

export const DependencyEdge = memo(DependencyEdgeInner);

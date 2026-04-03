import { useState, useCallback, useEffect } from 'react'
import { useApiClient, type TreeNode, type PinnedTextFile, type DashboardLayoutApi } from '@codrag/ui'

// ── Constants ─────────────────────────────────────────────────

const PINNED_PREFIX = 'pinned:'

// ── Helpers ───────────────────────────────────────────────────

function findNode(nodes: TreeNode[], name: string): TreeNode | undefined {
  return nodes.find(n => n.name === name)
}

/**
 * Collects paths of siblings along the path from ancestor to target.
 * Used when breaking an ancestor selection to preserve other children.
 */
function getExplodedPaths(nodes: TreeNode[], ancestorPath: string, targetPath: string): string[] {
  const ancestorParts = ancestorPath.split('/')
  const targetParts = targetPath.split('/')
  
  // Navigate to ancestor node in the tree
  let currentNodes = nodes
  for (const part of ancestorParts) {
    const node = findNode(currentNodes, part)
    if (!node || !node.children) return [] // Should not happen if UI is consistent
    currentNodes = node.children
  }
  
  // Now currentNodes is the children of the ancestor
  // We need to traverse from ancestor end to target
  // ancestorPath = "src", targetPath = "src/a/b"
  // parts relative to ancestor: "a", "b"
  const relativeParts = targetParts.slice(ancestorParts.length)
  const result: string[] = []
  
  let currentBasePath = ancestorPath
  
  for (const part of relativeParts) {
    // Add all siblings that are NOT the current part
    for (const child of currentNodes) {
      if (child.name !== part && child.status !== 'ignored') {
         result.push(`${currentBasePath}/${child.name}`)
      }
    }
    
    // Move down
    const nextNode = findNode(currentNodes, part)
    if (!nextNode || !nextNode.children) break // Target reached or tree incomplete
    currentNodes = nextNode.children
    currentBasePath = `${currentBasePath}/${part}`
  }
  
  return result
}

// ── Dependencies ──────────────────────────────────────────────

interface UseFileSystemDeps {
  /** Ref to dashboard layout API for pinned panel management */
  layoutApiRef: React.RefObject<DashboardLayoutApi | null>
  /** AbortSignal from hydration controller — aborted on project switch */
  signal?: AbortSignal
}

// ── Hook ──────────────────────────────────────────────────────

/**
 * Manages file tree, path weights, knowledge scope (included paths),
 * and pinned files. Self-hydrates on project change.
 */
export function useFileSystem(selectedProjectId: string | null, deps: UseFileSystemDeps) {
  const api = useApiClient()

  // ── State ───────────────────────────────────────────────────

  const [pathWeights, setPathWeights] = useState<Record<string, number>>({})
  const [fileTree, setFileTree] = useState<TreeNode[]>([])
  const [includedPaths, setIncludedPaths] = useState<Set<string>>(() => {
    try {
      // Migration v2: clear stale data from before folder-aware toggle fix.
      const version = localStorage.getItem('codrag_included_paths_version')
      if (version !== '2') {
        localStorage.removeItem('codrag_included_paths')
        localStorage.setItem('codrag_included_paths_version', '2')
        return new Set()
      }
      const stored = localStorage.getItem('codrag_included_paths')
      return stored ? new Set(JSON.parse(stored)) : new Set()
    } catch { return new Set() }
  })
  const [pinnedPaths, setPinnedPaths] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem('codrag_pinned_files')
      return stored ? new Set(JSON.parse(stored)) : new Set()
    } catch { return new Set() }
  })
  const [pinnedFiles, setPinnedFiles] = useState<PinnedTextFile[]>([])

  // ── File tree handlers ──────────────────────────────────────

  const fetchFileTree = useCallback(async (projId: string, signal?: AbortSignal) => {
    try {
      const data = await api.getProjectFiles(projId)
      if (signal?.aborted) return
      const newRoots = data.tree as TreeNode[]

      setFileTree((prev) => {
        // Strip stale status/chunks from nodes (used when preserving old
        // children that were NOT refreshed by the API response).
        function stripStatus(nodes: TreeNode[]): TreeNode[] {
          return nodes.map(node => {
            const { status, chunks, ...rest } = node as TreeNode & { chunks?: number }
            if (rest.children) {
              return { ...rest, children: stripStatus(rest.children) }
            }
            return rest
          })
        }

        // Recursive Deep Merge: Preserve loaded children from previous state
        // if new state (roots) doesn't have them. This prevents wiping out
        // the loaded tree structure on background refreshes.
        function mergeNodes(oldNodes: TreeNode[], newNodes: TreeNode[]): TreeNode[] {
          return newNodes.map(newNode => {
            const oldNode = oldNodes.find(n => n.name === newNode.name && n.type === newNode.type)
            
            if (oldNode) {
              // If new node has explicit children, recursively merge them
              if (newNode.children && newNode.children.length > 0) {
                 return { 
                   ...newNode, 
                   children: mergeNodes(oldNode.children || [], newNode.children) 
                 }
              }
              // If new node has NO children (or empty) but old node had children,
              // preserve the old children structure but strip stale status/chunks
              // (backend didn't confirm their status in this response).
              if (oldNode.children && oldNode.children.length > 0) {
                return { ...newNode, children: stripStatus(oldNode.children) }
              }
            }
            return newNode
          })
        }
        return mergeNodes(prev, newRoots)
      })
    } catch {
      if (!signal?.aborted) setFileTree([])
    }
  }, [api])

  const handleLoadChildren = useCallback(async (path: string): Promise<TreeNode[]> => {
    if (!selectedProjectId) return []
    try {
      const data = await api.getProjectFiles(selectedProjectId, path, 2)
      const children = data.tree as TreeNode[]
      
      // Update local fileTree state with new children so we have full knowledge for selection logic
      setFileTree((prev) => {
        // Deep-clone and merge children into the node at path
        function mergeInto(nodes: TreeNode[], segments: string[], idx: number): TreeNode[] {
          return nodes.map((n) => {
            if (n.name === segments[idx]) {
              if (idx === segments.length - 1) {
                // Found target — set children, clear has_children flag
                return { ...n, children, has_children: undefined }
              }
              if (n.children) {
                return { ...n, children: mergeInto(n.children, segments, idx + 1) }
              }
            }
            return n
          })
        }
        const segments = path.split('/')
        return mergeInto(prev, segments, 0)
      })
      
      return children
    } catch {
      return []
    }
  }, [api, selectedProjectId])

  // ── Path weight handler ─────────────────────────────────────

  const handlePathWeightChange = useCallback((path: string, weight: number | null) => {
    if (!selectedProjectId) return
    setPathWeights((prev) => {
      const next = { ...prev }
      if (weight === null) {
        delete next[path]
      } else {
        next[path] = weight
      }
      // Persist to backend (fire-and-forget)
      api.updatePathWeights(selectedProjectId, next).catch(() => {})
      return next
    })
  }, [api, selectedProjectId])

  // ── Index inclusion handlers (knowledge scope) ──────────────

  const handleToggleInclude = useCallback((paths: string[], action: 'add' | 'remove') => {
    setIncludedPaths((prev) => {
      const next = new Set(prev)
      
      for (const path of paths) {
        if (action === 'add') {
          // Add the path
          next.add(path)
          
          // Remove any existing descendants (cleanup - parent covers them)
          const prefix = path + '/'
          for (const existing of next) {
            if (existing.startsWith(prefix)) {
              next.delete(existing)
            }
          }
        } else {
          // Action is remove
          
          // 1. Check for Ancestor (to explode if needed)
          // We always check this because even if the path itself is explicit,
          // it might be shadowed by an ancestor (though cleanup usually prevents this,
          // it's safer to check).
          // Primarily this handles the case where we are removing a child of a selected parent.
          let ancestorFound: string | null = null
          const parts = path.split('/')
          for (let i = parts.length - 1; i >= 1; i--) {
            const ancestor = parts.slice(0, i).join('/')
            if (next.has(ancestor)) {
              ancestorFound = ancestor
              break
            }
          }
          
          if (ancestorFound) {
            next.delete(ancestorFound)
            const pathsToKeep = getExplodedPaths(fileTree, ancestorFound, path)
            pathsToKeep.forEach(p => next.add(p))
          }
          
          // 2. Remove the path itself (always try)
          next.delete(path)
          
          // 3. Remove any descendants (always try)
          // This ensures that if we uncheck a folder that had explicit children
          // (partially selected), those children are removed.
          const prefix = path + '/'
          for (const existing of next) {
            if (existing.startsWith(prefix)) {
              next.delete(existing)
            }
          }
        }
      }
      
      localStorage.setItem('codrag_included_paths', JSON.stringify([...next]))

      // Persist full canonical set to server (fire-and-forget)
      if (selectedProjectId) {
        api.updateIncludedPaths(selectedProjectId, [...next]).catch(() => {})
      }

      return next
    })

    // Phase 24: Notify scope orchestrator about knowledge scope changes
    if (selectedProjectId && paths.length > 0) {
      if (action === 'add') {
        api.addScopeFiles(selectedProjectId, paths).catch(() => {})
      } else {
        api.removeScopeFiles(selectedProjectId, paths).catch(() => {})
      }
    }
  }, [api, selectedProjectId, fileTree])

  const clearIncludedPaths = useCallback(() => {
    setIncludedPaths(new Set())
    localStorage.removeItem('codrag_included_paths')
    if (selectedProjectId) {
      api.updateIncludedPaths(selectedProjectId, []).catch(() => {})
    }
  }, [api, selectedProjectId])

  // ── Pinned file handlers ────────────────────────────────────

  const handlePinFile = useCallback((path: string) => {
    setPinnedPaths((prev) => {
      const next = new Set(prev)
      next.add(path)
      localStorage.setItem('codrag_pinned_files', JSON.stringify([...next]))
      return next
    })
    // Add as a dashboard panel
    const panelId = `${PINNED_PREFIX}${path}`
    deps.layoutApiRef.current?.addPanel(panelId, { height: 8, w: 6 })
  }, [deps.layoutApiRef])

  const handleUnpinFile = useCallback((pathOrPanelId: string) => {
    const path = pathOrPanelId.startsWith(PINNED_PREFIX)
      ? pathOrPanelId.slice(PINNED_PREFIX.length)
      : pathOrPanelId
    const panelId = `${PINNED_PREFIX}${path}`
    setPinnedPaths((prev) => {
      const next = new Set(prev)
      next.delete(path)
      localStorage.setItem('codrag_pinned_files', JSON.stringify([...next]))
      return next
    })
    setPinnedFiles((prev) => prev.filter((f) => f.id !== path))
    deps.layoutApiRef.current?.removePanel(panelId)
  }, [deps.layoutApiRef])

  const handleLoadFileContent = useCallback(async (path: string): Promise<string> => {
    if (!selectedProjectId) throw new Error('No project selected')
    const data = await api.getProjectFileContent(selectedProjectId, path)
    return data.content
  }, [api, selectedProjectId])

  // ── Hydration: fetch tree + path weights + included paths on project change ──

  useEffect(() => {
    if (!selectedProjectId) return
    const signal = deps.signal
    void fetchFileTree(selectedProjectId, signal)
    api.getPathWeights(selectedProjectId).then((data) => {
      if (signal?.aborted) return
      setPathWeights(data.path_weights ?? {})
    }).catch(() => { if (!signal?.aborted) setPathWeights({}) })
    api.getIncludedPaths(selectedProjectId).then((data) => {
      if (signal?.aborted) return
      const serverPaths = new Set(data.included_paths ?? [])
      if (serverPaths.size > 0) {
        setIncludedPaths(serverPaths)
        localStorage.setItem('codrag_included_paths', JSON.stringify([...serverPaths]))
      }
    }).catch(() => { /* keep localStorage state as fallback */ })
  }, [api, selectedProjectId, fetchFileTree])

  // ── Sync pinned paths to dashboard layout ───────────────────

  useEffect(() => {
    if (!deps.layoutApiRef.current) return
    for (const path of pinnedPaths) {
      const panelId = `${PINNED_PREFIX}${path}`
      deps.layoutApiRef.current.addPanel(panelId, { height: 8, w: 6 })
    }
  }, [pinnedPaths, deps.layoutApiRef])

  // ── Fetch content for pinned files when paths or project change ──

  useEffect(() => {
    if (!selectedProjectId || pinnedPaths.size === 0) {
      setPinnedFiles([])
      return
    }
    let cancelled = false
    const fetchAll = async () => {
      const results: PinnedTextFile[] = []
      for (const path of pinnedPaths) {
        try {
          const data = await api.getProjectFileContent(selectedProjectId, path)
          if (cancelled) return
          results.push({
            id: path,
            path,
            name: path.split('/').pop() ?? path,
            content: data.content,
          })
        } catch {
          if (cancelled) return
          results.push({
            id: path,
            path,
            name: path.split('/').pop() ?? path,
            content: `// Failed to load ${path}`,
          })
        }
      }
      if (!cancelled) setPinnedFiles(results)
    }
    void fetchAll()
    return () => { cancelled = true }
  }, [api, selectedProjectId, pinnedPaths])

  // ── Return ──────────────────────────────────────────────────

  return {
    // State
    fileTree,
    pathWeights,
    includedPaths,
    pinnedPaths,
    pinnedFiles,
    // Handlers
    fetchFileTree,
    handleLoadChildren,
    handlePathWeightChange,
    handleToggleInclude,
    clearIncludedPaths,
    handlePinFile,
    handleUnpinFile,
    handleLoadFileContent,
  }
}

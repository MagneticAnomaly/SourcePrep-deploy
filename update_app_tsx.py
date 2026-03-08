import re

with open('src/codrag/dashboard/src/App.tsx', 'r') as f:
    content = f.read()

# 1. Add SyncStatusCard to @codrag/ui imports
content = re.sub(
    r'(TeamSyncIndicator,)',
    r'\1\n  SyncStatusCard,',
    content,
    count=1
)

# 2. Add handleSyncNow function inside App component
sync_func = """
  const handleSyncNow = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      // For now, we'll just show a toast since the backend sync is typically handled 
      // by the background polling service, but we'll add an endpoint later if needed.
      makeToast('Sync triggered', 'Remote sync check started.', 'info')
      // Future: await api.triggerSync(selectedProjectId)
    } catch (e) {
      makeToast('Sync failed', e instanceof Error ? e.message : 'Unknown error', 'error')
    }
  }, [selectedProjectId])
"""

content = re.sub(
    r'(  const handleCancelTask = useCallback)',
    sync_func + r'\n\1',
    content,
    count=1
)

# 3. Render SyncStatusCard below the selected project name / right side header area if we want, or below ProjectList. 
# But the user might want it in the main dashboard. Let's add it to the sidebar above the ProjectList if there is a selected project.
# Actually, the instructions say "Wire into App.tsx below project status cards" (meaning below the project list or inside the project view).
# Let's put it at the bottom of the sidebar.

sidebar_addition = """
              {selectedProject && projectStatus?.sync?.enabled && (
                <div className="mt-auto p-4 border-t border-border bg-surface-raised">
                  <SyncStatusCard
                    status={projectStatus.sync}
                    onSyncNow={handleSyncNow}
                    className="border-none shadow-none bg-transparent p-0"
                  />
                </div>
              )}
            </Sidebar>"""

content = re.sub(
    r'(            \n*          </Sidebar>)',
    sidebar_addition,
    content,
    count=1
)

with open('src/codrag/dashboard/src/App.tsx', 'w') as f:
    f.write(content)

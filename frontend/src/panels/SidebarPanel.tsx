import { Code2, Compass, Layers, Play } from 'lucide-react'
import { useWorkspaceStore } from '../stores/workspace.store'
import type { WorkspaceMode } from '../layouts/WorkspaceLayout'

interface SidebarPanelProps {
  activeView: WorkspaceMode
  onViewChange: (view: WorkspaceMode) => void
}

export default function SidebarPanel({ activeView, onViewChange }: SidebarPanelProps) {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore(s => s.workspaces)
  
  const ws = activeWorkspaceId ? workspaces[activeWorkspaceId] : null

  return (
    <div className="h-full w-56 bg-[#151518] border-r border-border flex flex-col text-[#cccccc] text-sm select-none shrink-0 z-20">
      <div className="border-b border-border px-4 py-4">
        <div className="text-[11px] uppercase tracking-widest text-gray-500">Project</div>
        <div className="mt-1 truncate text-sm font-medium text-gray-100">{ws?.name || 'No project'}</div>
      </div>

      <div className="flex-1 overflow-y-auto py-3">
        <SidebarSection title="Modes">
          <SidebarItem icon={<Layers className="w-4 h-4" />} label="Generate" testId="workspace-mode-generate" active={activeView === 'generate'} onClick={() => onViewChange('generate')} />
          <SidebarItem icon={<Compass className="w-4 h-4" />} label="Explore" testId="workspace-mode-explore" active={activeView === 'explore'} onClick={() => onViewChange('explore')} />
          <SidebarItem icon={<Code2 className="w-4 h-4" />} label="Edit Code" testId="workspace-mode-edit" active={activeView === 'edit'} onClick={() => onViewChange('edit')} />
          <SidebarItem icon={<Play className="w-4 h-4" />} label="Preview" testId="workspace-mode-preview" active={activeView === 'preview'} onClick={() => onViewChange('preview')} />
        </SidebarSection>
      </div>
    </div>
  )
}

function SidebarSection({ title, children }: { title: string, children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="px-4 py-1 text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-1">
        {title}
      </div>
      <div className="flex flex-col">
        {children}
      </div>
    </div>
  )
}

function SidebarItem({ icon, label, testId, active = false, onClick }: { icon: React.ReactNode, label: string, testId: string, active?: boolean, onClick?: () => void }) {
  return (
    <button
      data-testid={testId}
      onClick={onClick} 
      className={`w-full px-5 py-2.5 flex items-center space-x-3 cursor-pointer transition-colors border-l-2 text-left ${
        active 
          ? 'bg-blue-500/10 text-white border-blue-400'
          : 'hover:bg-white/5 border-transparent text-gray-400 hover:text-gray-200'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

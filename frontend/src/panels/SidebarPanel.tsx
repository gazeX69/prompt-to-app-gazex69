import { Code2, Layers, Play, LayoutDashboard, Archive, History, Terminal, Cpu, Bug, Settings, FolderKanban } from 'lucide-react'
import { useWorkspaceStore } from '../stores/workspace.store'
import type { WorkspaceMode } from '../stores/workspace.store'

interface SidebarPanelProps {
  activeView: WorkspaceMode
  onViewChange: (view: WorkspaceMode) => void
}

export default function SidebarPanel({ activeView, onViewChange }: SidebarPanelProps) {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore(s => s.workspaces)
  
  const ws = activeWorkspaceId ? workspaces[activeWorkspaceId] : null

  return (
    <div className="h-full w-60 bg-[#08080a] border-r border-[#1a1a22] flex flex-col text-[#b3b3b3] text-sm select-none shrink-0 z-20 shadow-[4px_0_24px_rgba(0,0,0,0.3)]">
      {/* Project Brand Box */}
      <div className="border-b border-[#1a1a22] px-5 py-5 flex items-center gap-3 bg-gradient-to-b from-[#0e0e12] to-transparent">
        <div className="h-8 w-8 rounded-lg bg-blue-500/10 border border-blue-500/25 flex items-center justify-center text-blue-400 shadow-[0_0_12px_-2px_rgba(59,130,246,0.25)]">
          <FolderKanban className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-gray-500 leading-none">Active Project</div>
          <div className="mt-1.5 truncate text-[13px] font-semibold text-gray-200 tracking-wide leading-tight">
            {ws?.name || 'Select Project'}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-5 space-y-5">
        <SidebarSection title="Core Modes">
          <SidebarItem icon={<Layers className="w-4 h-4" />} label="Generate" testId="workspace-mode-generate" active={activeView === 'generate'} onClick={() => onViewChange('generate')} />
          <SidebarItem icon={<Code2 className="w-4 h-4" />} label="Editor" testId="workspace-mode-edit" active={activeView === 'edit'} onClick={() => onViewChange('edit')} />
          <SidebarItem icon={<Play className="w-4 h-4" />} label="Preview" testId="workspace-mode-preview" active={activeView === 'preview'} onClick={() => onViewChange('preview')} />
        </SidebarSection>

        <SidebarSection title="Analytics & Logs">
          <SidebarItem icon={<LayoutDashboard className="w-4 h-4" />} label="Overview" testId="workspace-mode-overview" active={activeView === 'overview'} onClick={() => onViewChange('overview')} />
          <SidebarItem icon={<History className="w-4 h-4" />} label="History" testId="workspace-mode-history" active={activeView === 'history'} onClick={() => onViewChange('history')} />
          <SidebarItem icon={<Terminal className="w-4 h-4" />} label="Terminal" testId="workspace-mode-terminal" active={activeView === 'terminal'} onClick={() => onViewChange('terminal')} />
          <SidebarItem icon={<Archive className="w-4 h-4" />} label="Artifacts" testId="workspace-mode-artifacts" active={activeView === 'artifacts'} onClick={() => onViewChange('artifacts')} />
          <SidebarItem icon={<Cpu className="w-4 h-4" />} label="Skills" testId="workspace-mode-skills" active={activeView === 'skills'} onClick={() => onViewChange('skills')} />
          <SidebarItem icon={<Bug className="w-4 h-4" />} label="Debug Inspector" testId="workspace-mode-debug" active={activeView === 'debug'} onClick={() => onViewChange('debug')} />
        </SidebarSection>

        <SidebarSection title="Configuration">
          <SidebarItem icon={<Settings className="w-4 h-4" />} label="Settings" testId="workspace-mode-settings" active={activeView === 'settings'} onClick={() => onViewChange('settings')} />
        </SidebarSection>
      </div>
    </div>
  )
}

function SidebarSection({ title, children }: { title: string, children: React.ReactNode }) {
  return (
    <div className="mb-2">
      <div className="px-5 py-1 text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-2">
        {title}
      </div>
      <div className="flex flex-col space-y-[2px]">
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
      className={`w-full px-5 py-3 flex items-center space-x-3.5 cursor-pointer transition-all duration-200 border-l-[3px] text-left text-xs font-semibold ${
        active 
          ? 'bg-blue-600/10 text-white border-blue-500 shadow-[inset_4px_0_16px_-4px_rgba(59,130,246,0.2)] font-bold'
          : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/[0.02] hover:border-white/5'
      }`}
    >
      <span className={`transition-transform duration-200 ${active ? 'scale-110 text-blue-400' : 'opacity-85 group-hover:opacity-100'}`}>
        {icon}
      </span>
      <span className="tracking-wide">{label}</span>
    </button>
  )
}

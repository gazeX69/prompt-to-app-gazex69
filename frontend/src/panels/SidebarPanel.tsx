import { Clock, Activity, Layers, XCircle, Play, Code2 } from 'lucide-react'
import { useWorkspaceStore } from '../stores/workspace.store'
import { useAgentStore } from '../stores/agent.store'

interface SidebarPanelProps {
  activeView: string
  onViewChange: (view: string) => void
}

export default function SidebarPanel({ activeView, onViewChange }: SidebarPanelProps) {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore(s => s.workspaces)
  const closeWorkspace = useWorkspaceStore(s => s.closeWorkspace)
  const runtimeState = useAgentStore(s => s.runtimeState)
  
  const ws = activeWorkspaceId ? workspaces[activeWorkspaceId] : null

  return (
    <div className="h-full w-64 bg-[#1e1e1e] border-r border-[#333333] flex flex-col text-[#cccccc] text-sm select-none shrink-0 z-20 font-mono">
      {/* Workspace Header */}
      <div className="px-4 py-3 flex items-center justify-between border-b border-[#333333]">
        <div className="font-semibold text-gray-100 uppercase tracking-wider text-xs">
          {ws?.name || 'No Workspace'}
        </div>
        <button onClick={closeWorkspace} className="hover:text-red-400 transition-colors" title="Close Workspace">
          <XCircle className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto py-2">
        
        <SidebarSection title="Workspace">
          <SidebarItem icon={<Layers className="w-4 h-4" />} label="Generate" active={activeView === 'generate'} onClick={() => onViewChange('generate')} />
          <SidebarItem icon={<Play className="w-4 h-4" />} label="Preview" active={activeView === 'preview'} onClick={() => onViewChange('preview')} />
          <SidebarItem icon={<Code2 className="w-4 h-4" />} label="Source" active={activeView === 'source'} onClick={() => onViewChange('source')} />
          <SidebarItem icon={<Activity className="w-4 h-4" />} label="Runtime" active={activeView === 'runtime'} onClick={() => onViewChange('runtime')} />
          <SidebarItem icon={<Clock className="w-4 h-4" />} label="History" active={activeView === 'history'} onClick={() => onViewChange('history')} />
        </SidebarSection>

        {ws && (
          <SidebarSection title="Active Workspace">
            <div className="px-6 py-1 text-xs text-gray-400 flex flex-col space-y-2">
              <div className="flex justify-between">
                <span>Ecosystem:</span>
                <span className="text-blue-400">{ws.ecosystem}</span>
              </div>
              <div className="flex justify-between">
                <span>Runtime:</span>
                <span className={runtimeState === 'READY' ? 'text-green-400' : runtimeState === 'FAILED' ? 'text-red-400' : 'text-yellow-400'}>
                  {runtimeState}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Total Runs:</span>
                <span>{ws.runCount}</span>
              </div>
            </div>
          </SidebarSection>
        )}

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

function SidebarItem({ icon, label, active = false, onClick }: { icon: React.ReactNode, label: string, active?: boolean, onClick?: () => void }) {
  return (
    <div 
      onClick={onClick} 
      className={`px-6 py-1.5 flex items-center space-x-3 cursor-pointer transition-colors border-l-2 ${
        active 
          ? 'bg-[#37373d] text-white border-blue-500' 
          : 'hover:bg-[#2a2d2e] border-transparent'
      }`}
    >
      {icon}
      <span>{label}</span>
    </div>
  )
}

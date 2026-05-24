import { Folder, Clock, Activity, Box, Search, Layers, XCircle } from 'lucide-react'
import { useWorkspaceStore } from '../stores/workspace.store'

interface SidebarPanelProps {
  activeView: string
  onViewChange: (view: string) => void
}

export default function SidebarPanel({ activeView, onViewChange }: SidebarPanelProps) {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore(s => s.workspaces)
  const closeWorkspace = useWorkspaceStore(s => s.closeWorkspace)
  
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
        
        <SidebarSection title="Observability">
          <SidebarItem icon={<Activity className="w-4 h-4" />} label="Overview" active={activeView === 'overview'} onClick={() => onViewChange('overview')} />
          <SidebarItem icon={<Folder className="w-4 h-4" />} label="Repository" active={activeView === 'repository'} onClick={() => onViewChange('repository')} />
          <SidebarItem icon={<Layers className="w-4 h-4" />} label="Generate" active={activeView === 'generate'} onClick={() => onViewChange('generate')} />
          <SidebarItem icon={<Clock className="w-4 h-4" />} label="Run History" active={activeView === 'history'} onClick={() => onViewChange('history')} />
          <SidebarItem icon={<Box className="w-4 h-4" />} label="Artifact Explorer" active={activeView === 'artifacts'} onClick={() => onViewChange('artifacts')} />
          <SidebarItem icon={<Search className="w-4 h-4" />} label="Runtime Inspector" active={activeView === 'inspector'} onClick={() => onViewChange('inspector')} />
        </SidebarSection>

        {ws && (
          <SidebarSection title="Active Workspace">
            <div className="px-6 py-1 text-xs text-gray-400 flex flex-col space-y-2">
              <div className="flex justify-between">
                <span>Ecosystem:</span>
                <span className="text-blue-400">{ws.ecosystem}</span>
              </div>
              <div className="flex justify-between">
                <span>Health:</span>
                <span className={ws.runtimeHealth === 'healthy' ? 'text-green-400' : 'text-yellow-400'}>
                  {ws.runtimeHealth}
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

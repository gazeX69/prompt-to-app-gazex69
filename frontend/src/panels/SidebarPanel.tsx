import { FolderDot, Clock, LayoutTemplate, Settings, Zap } from 'lucide-react'

export default function SidebarPanel() {
  return (
    <div className="h-full w-[72px] bg-panel border-r border-border flex flex-col items-center py-4 select-none shrink-0 z-20">
      <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center mb-8 shrink-0">
        <Zap className="w-5 h-5" />
      </div>
      
      <div className="flex-1 flex flex-col items-center space-y-3 w-full">
        <SidebarItem icon={<FolderDot className="w-5 h-5" />} active />
        <SidebarItem icon={<Clock className="w-5 h-5" />} />
        <SidebarItem icon={<LayoutTemplate className="w-5 h-5" />} />
      </div>
      
      <div className="shrink-0 flex flex-col items-center space-y-4 w-full pb-2">
        <SidebarItem icon={<Settings className="w-5 h-5" />} />
        <div className="w-8 h-8 rounded-full flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-green-500 relative">
            <div className="absolute inset-0 rounded-full bg-green-400 animate-ping opacity-50" />
          </div>
        </div>
      </div>
    </div>
  )
}

function SidebarItem({ icon, active = false }: { icon: React.ReactNode, active?: boolean }) {
  return (
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center cursor-pointer transition-all relative ${
      active ? 'text-gray-100 bg-accent' : 'text-gray-500 hover:text-gray-300 hover:bg-accent/50'
    }`}>
      {active && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full" />
      )}
      {icon}
    </div>
  )
}

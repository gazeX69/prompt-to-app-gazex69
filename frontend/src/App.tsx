import { useEffect } from "react"
import { initSocket, cleanupSocket } from "./sockets/socketManager"
import WorkspaceLayout from "./layouts/WorkspaceLayout"

function App() {
  useEffect(() => {
    initSocket()
    return () => cleanupSocket()
  }, [])

  return <WorkspaceLayout />
}

export default App

from backend.graph.knowledge_graph import KnowledgeGraph
from backend.memory.reflection_memory import ReflectionMemory
from backend.memory.project_memory import ProjectMemory
from backend.memory.workspace_awareness import WorkspaceAwareness

class ContextCompressor:
    """Summarizes project state to prevent context window collapse."""
    
    @staticmethod
    def generate_architecture_summary(project_id: str, run_id: str = None) -> str:
        arch_map = KnowledgeGraph.build_architecture_map(project_id, run_id)
        project_state = ProjectMemory.get_project_state(project_id)
        
        summary = "## Current Architecture Summary\n"
        if project_state:
            summary += f"- Ecosystem: {project_state.get('ecosystem')}\n"
            summary += f"- Project Type: {project_state.get('project_type')}\n"
            features = project_state.get("features") or []
            if features:
                summary += "- Existing Features: " + ", ".join(features) + "\n"
            decisions = project_state.get("decisions") or {}
            if decisions:
                summary += "- Decisions: " + ", ".join(f"{k}={v}" for k, v in decisions.items()) + "\n"
        try:
            workspace_awareness = WorkspaceAwareness.load(project_id)
            if workspace_awareness:
                patterns = workspace_awareness.get("patterns") or {}
                architecture = workspace_awareness.get("architecture") or {}
                summary += f"- Workspace Stack: {', '.join(workspace_awareness.get('stack', {}).get('stack') or [])}\n"
                summary += f"- Workspace Flow: {' -> '.join(architecture.get('flow') or [])}\n"
                summary += f"- State Pattern: {', '.join(patterns.get('state_management') or [])}\n"
                summary += f"- API Pattern: {', '.join(patterns.get('api_layer') or [])}\n"
        except Exception:
            pass
        
        files = arch_map["files"]
        if len(files) > 20:
            summary += f"- Total Files: {len(files)} (Too many to list individually)\n"
            # Show just important dirs or root files
            core = [f for f in files if "/" not in f or f.startswith("src/")]
            summary += f"- Core Structure:\n" + "\n".join(f"  - {f}" for f in core[:15]) + "\n"
        else:
            summary += f"- Files:\n" + "\n".join(f"  - {f}" for f in files) + "\n"
            
        return summary

    @staticmethod
    def generate_reflection_summary(project_id: str) -> str:
        repairs = ReflectionMemory.get_past_repairs(project_id)
        if not repairs:
            return "## Known Issues\n- None historically recorded.\n"
            
        summary = "## Known Issues & Past Repairs\n"
        # Just summarize the top 3 recent failures to prevent bloat
        for r in repairs[:3]:
            summary += f"- Failure: {r['failure_type']}\n  - Fix applied: {r['patch_summary']}\n  - Success: {r['success']}\n"
        
        return summary
        
    @staticmethod
    def get_full_context(project_id: str, run_id: str = None) -> str:
        arch = ContextCompressor.generate_architecture_summary(project_id, run_id)
        refl = ContextCompressor.generate_reflection_summary(project_id)
        safety_rule = "\nIMPORTANT WARNING:\nHistorical memory is advisory only. The current user request is authoritative. Never reproduce a previous app unless the current user explicitly requests it.\n"
        return f"{arch}\n{refl}\n{safety_rule}"

from typing import List
from pydantic import BaseModel
from backend.planner.domain_analyzer import Subdomain

class VerticalSlice(BaseModel):
    name: str
    description: str
    target_components: List[str]
    dependencies: List[str]

def plan_vertical_slices(subdomains: List[Subdomain]) -> List[VerticalSlice]:
    """
    Creates a vertical slice implementation roadmap.
    Each slice delivers end-to-end value: UI + Logic + State.
    """
    slices = []
    
    # Slice 1: Core State & Persistence
    slices.append(VerticalSlice(
        name="Phase 1: LocalStorage State & Models",
        description="Scaffolding the TypeScript data structures, state stores, and browser persistence handlers.",
        target_components=["types.ts", "stateStore.ts", "persistence.ts"],
        dependencies=[]
    ))
    
    # Add subdomain-specific slices
    for idx, sub in enumerate(subdomains):
        entity_names = [e.name for e in sub.entities]
        slices.append(VerticalSlice(
            name=f"Phase {idx + 2}: {sub.name} UI & Actions",
            description=f"Building end-to-end screens and mutations for: {', '.join(entity_names)} ({sub.description}).",
            target_components=[f"{sub.name.replace(' ', '')}View.tsx", "App.tsx"],
            dependencies=["Phase 1: LocalStorage State & Models"]
        ))
        
    return slices

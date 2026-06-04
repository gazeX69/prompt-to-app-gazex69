"""
WorkspaceMemorySnapshot

Persists repository intelligence snapshots to disk.

Contents:
* repository maps
* dependency graphs
* symbol ownership
* recent investigation results

Location: .orchestration/
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class WorkspaceMemorySnapshot:
    """
    Manages persistence of workspace intelligence.
    
    Snapshots are stored in:
    - .orchestration/repo_map.json
    - .orchestration/dependency_graph.json
    - .orchestration/symbol_index.json
    - .orchestration/investigation_cache.json
    - .orchestration/metadata.json
    """

    ORCHESTRATION_DIR = ".orchestration"
    
    SNAPSHOT_FILES = {
        "repo_map": "repo_map.json",
        "dependency_graph": "dependency_graph.json",
        "symbol_index": "symbol_index.json",
        "investigation_cache": "investigation_cache.json",
        "metadata": "metadata.json",
        "dependency_ripples": "p85_dependency_ripples.json",  # P8.5
        "ownership_propagation": "p85_ownership_propagation.json",  # P8.5
        "structural_risks": "p85_structural_risks.json",  # P8.5
        "mutation_sequences": "p86_mutation_sequences.json",  # P8.6
        "prerequisite_chains": "p86_prerequisite_chains.json",  # P8.6
        "sequencing_risks": "p86_sequencing_risks.json",  # P8.6
    }

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.orchestration_dir = self.workspace_root / self.ORCHESTRATION_DIR
        self._ensure_dir()

    def _ensure_dir(self):
        """Create .orchestration directory if needed."""
        self.orchestration_dir.mkdir(exist_ok=True)
        logger.info(f"Orchestration directory: {self.orchestration_dir}")

    def save_repo_map(self, repo_map_dict: Dict[str, Any]) -> bool:
        """
        Save repository map snapshot.
        
        Args:
            repo_map_dict: Repository map as dict (from repo_map_to_dict)
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["repo_map"]
            with open(path, 'w') as f:
                json.dump(repo_map_dict, f, indent=2)
            logger.info(f"Saved repo map: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save repo map: {e}")
            return False

    def load_repo_map(self) -> Optional[Dict[str, Any]]:
        """Load repository map from snapshot."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["repo_map"]
            if not path.exists():
                logger.warning(f"Repo map not found: {path}")
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load repo map: {e}")
            return None

    def save_dependency_graph(self, graph: Dict[str, List[str]]) -> bool:
        """
        Save dependency graph.
        
        Args:
            graph: Dict[file_path -> [dependencies]]
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["dependency_graph"]
            with open(path, 'w') as f:
                json.dump(graph, f, indent=2)
            logger.info(f"Saved dependency graph: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save dependency graph: {e}")
            return False

    def load_dependency_graph(self) -> Optional[Dict[str, List[str]]]:
        """Load dependency graph from snapshot."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["dependency_graph"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load dependency graph: {e}")
            return None

    def save_symbol_index(self, symbols: Dict[str, List[Dict[str, Any]]]) -> bool:
        """
        Save symbol ownership index.
        
        Args:
            symbols: Dict[symbol_name -> [location_dicts]]
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["symbol_index"]
            with open(path, 'w') as f:
                json.dump(symbols, f, indent=2)
            logger.info(f"Saved symbol index: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save symbol index: {e}")
            return False

    def load_symbol_index(self) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Load symbol index from snapshot."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["symbol_index"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load symbol index: {e}")
            return None

    def save_investigation_cache(
        self,
        cache: Dict[str, Any],
        timestamp: Optional[str] = None,
    ) -> bool:
        """
        Save investigation results cache.
        
        Args:
            cache: Investigation results dict
            timestamp: Optional timestamp for versioning
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["investigation_cache"]
            
            # Add metadata
            cache_with_meta = {
                "timestamp": timestamp or datetime.now().isoformat(),
                "cache": cache,
            }
            
            with open(path, 'w') as f:
                json.dump(cache_with_meta, f, indent=2)
            logger.info(f"Saved investigation cache: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save investigation cache: {e}")
            return False

    def load_investigation_cache(self) -> Optional[Dict[str, Any]]:
        """Load investigation results cache."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["investigation_cache"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                data = json.load(f)
                return data.get("cache", data)
        except Exception as e:
            logger.error(f"Failed to load investigation cache: {e}")
            return None

    def save_snapshot(
        self,
        repo_map: Optional[Dict[str, Any]] = None,
        dependency_graph: Optional[Dict[str, List[str]]] = None,
        symbol_index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        investigation_cache: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save complete workspace snapshot.
        
        Args:
            repo_map: Repository map
            dependency_graph: Dependency graph
            symbol_index: Symbol ownership index
            investigation_cache: Investigation results
        
        Returns:
            True if all components saved
        """
        results = []
        
        if repo_map:
            results.append(self.save_repo_map(repo_map))
        
        if dependency_graph:
            results.append(self.save_dependency_graph(dependency_graph))
        
        if symbol_index:
            results.append(self.save_symbol_index(symbol_index))
        
        if investigation_cache:
            results.append(self.save_investigation_cache(investigation_cache))
        
        # Save metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "workspace_root": str(self.workspace_root),
            "snapshot_files": self.SNAPSHOT_FILES,
            "components_saved": {
                "repo_map": repo_map is not None,
                "dependency_graph": dependency_graph is not None,
                "symbol_index": symbol_index is not None,
                "investigation_cache": investigation_cache is not None,
            },
        }
        
        try:
            metadata_path = self.orchestration_dir / self.SNAPSHOT_FILES["metadata"]
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            results.append(True)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            results.append(False)
        
        success = all(results)
        if success:
            logger.info("Complete workspace snapshot saved")
        return success

    def load_snapshot(self) -> Dict[str, Any]:
        """
        Load complete workspace snapshot.
        
        Returns:
            Dict with loaded components (missing ones will be None)
        """
        return {
            "repo_map": self.load_repo_map(),
            "dependency_graph": self.load_dependency_graph(),
            "symbol_index": self.load_symbol_index(),
            "investigation_cache": self.load_investigation_cache(),
        }

    def get_snapshot_status(self) -> Dict[str, bool]:
        """Check which snapshot files exist."""
        return {
            "repo_map": (self.orchestration_dir / self.SNAPSHOT_FILES["repo_map"]).exists(),
            "dependency_graph": (self.orchestration_dir / self.SNAPSHOT_FILES["dependency_graph"]).exists(),
            "symbol_index": (self.orchestration_dir / self.SNAPSHOT_FILES["symbol_index"]).exists(),
            "investigation_cache": (self.orchestration_dir / self.SNAPSHOT_FILES["investigation_cache"]).exists(),
            "metadata": (self.orchestration_dir / self.SNAPSHOT_FILES["metadata"]).exists(),
        }

    def clear_snapshot(self, components: Optional[List[str]] = None) -> bool:
        """
        Clear snapshot files.
        
        Args:
            components: List of component names to clear. If None, clears all.
        
        Returns:
            True if successful
        """
        try:
            if components is None:
                components = list(self.SNAPSHOT_FILES.keys())
            
            for component in components:
                if component in self.SNAPSHOT_FILES:
                    path = self.orchestration_dir / self.SNAPSHOT_FILES[component]
                    if path.exists():
                        path.unlink()
                        logger.info(f"Cleared {component}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to clear snapshot: {e}")
            return False

    def get_snapshot_hash(self) -> Optional[str]:
        """
        Get hash of current snapshot (for change detection).
        
        Returns:
            MD5 hash of concatenated snapshot files
        """
        try:
            content = ""
            for file_key in self.SNAPSHOT_FILES:
                path = self.orchestration_dir / self.SNAPSHOT_FILES[file_key]
                if path.exists():
                    with open(path, 'r') as f:
                        content += f.read()
            
            if not content:
                return None
            
            return hashlib.md5(content.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to compute snapshot hash: {e}")
            return None

    def save_investigation_result(
        self,
        investigation_name: str,
        result: Dict[str, Any],
        query: str,
    ) -> bool:
        """
        Save individual investigation result.
        
        Args:
            investigation_name: Name of investigation (e.g., "find_components")
            result: Investigation result dict
            query: The query that was performed
        
        Returns:
            True if successful
        """
        try:
            # Load existing cache
            cache = self.load_investigation_cache() or {}
            
            # Add this result
            if investigation_name not in cache:
                cache[investigation_name] = []
            
            cache[investigation_name].append({
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "result": result,
            })
            
            # Limit cache size (keep last 100 per investigation)
            if len(cache[investigation_name]) > 100:
                cache[investigation_name] = cache[investigation_name][-100:]
            
            return self.save_investigation_cache(cache)
        except Exception as e:
            logger.error(f"Failed to save investigation result: {e}")
            return False

    def get_investigation_result(
        self,
        investigation_name: str,
        query: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached investigation result.
        
        Args:
            investigation_name: Name of investigation
            query: The query to look up
        
        Returns:
            Result dict if found, None otherwise
        """
        try:
            cache = self.load_investigation_cache() or {}
            results = cache.get(investigation_name, [])
            
            # Return most recent result matching query
            for result_entry in reversed(results):
                if result_entry.get("query") == query:
                    return result_entry.get("result")
            
            return None
        except Exception as e:
            logger.error(f"Failed to get investigation result: {e}")
            return None

    # ========== P8.5 Dependency Cognition Persistence ==========

    def save_dependency_ripples(self, ripples: Dict[str, Any]) -> bool:
        """
        Save P8.5 dependency ripple analysis.
        
        Args:
            ripples: Dict[module_path -> DependencyRipple (as dict)]
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["dependency_ripples"]
            with open(path, 'w') as f:
                json.dump(ripples, f, indent=2)
            logger.info(f"✓ Saved P8.5 dependency ripples: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save dependency ripples: {e}")
            return False

    def load_dependency_ripples(self) -> Optional[Dict[str, Any]]:
        """Load P8.5 dependency ripple analysis."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["dependency_ripples"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load dependency ripples: {e}")
            return None

    def save_ownership_propagation(self, ownership: Dict[str, Any]) -> bool:
        """
        Save P8.5 ownership propagation results.
        
        Args:
            ownership: Dict of ownership analysis
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["ownership_propagation"]
            with open(path, 'w') as f:
                json.dump(ownership, f, indent=2)
            logger.info(f"✓ Saved P8.5 ownership propagation: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save ownership propagation: {e}")
            return False

    def load_ownership_propagation(self) -> Optional[Dict[str, Any]]:
        """Load P8.5 ownership propagation results."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["ownership_propagation"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load ownership propagation: {e}")
            return None

    def save_structural_risks(self, risks: Dict[str, Any]) -> bool:
        """
        Save P8.5 structural mutation risk assessment.
        
        Args:
            risks: Dict of structural risks
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["structural_risks"]
            with open(path, 'w') as f:
                json.dump(risks, f, indent=2)
            logger.info(f"✓ Saved P8.5 structural risks: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save structural risks: {e}")
            return False

    def load_structural_risks(self) -> Optional[Dict[str, Any]]:
        """Load P8.5 structural mutation risk assessment."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["structural_risks"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load structural risks: {e}")
            return None

    # ========== P8.6 Mutation Sequencing Persistence ==========

    def save_mutation_sequences(self, sequences: Dict[str, Any]) -> bool:
        """
        Save P8.6 mutation sequence graphs.
        
        Args:
            sequences: Dict of mutation sequences
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["mutation_sequences"]
            with open(path, 'w') as f:
                json.dump(sequences, f, indent=2)
            logger.info(f"✓ Saved P8.6 mutation sequences: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save mutation sequences: {e}")
            return False

    def load_mutation_sequences(self) -> Optional[Dict[str, Any]]:
        """Load P8.6 mutation sequence graphs."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["mutation_sequences"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load mutation sequences: {e}")
            return None

    def save_prerequisite_chains(self, chains: Dict[str, Any]) -> bool:
        """
        Save P8.6 prerequisite analysis chains.
        
        Args:
            chains: Dict of prerequisite chains
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["prerequisite_chains"]
            with open(path, 'w') as f:
                json.dump(chains, f, indent=2)
            logger.info(f"✓ Saved P8.6 prerequisite chains: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save prerequisite chains: {e}")
            return False

    def load_prerequisite_chains(self) -> Optional[Dict[str, Any]]:
        """Load P8.6 prerequisite analysis chains."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["prerequisite_chains"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load prerequisite chains: {e}")
            return None

    def save_sequencing_risks(self, risks: Dict[str, Any]) -> bool:
        """
        Save P8.6 mutation sequencing risk assessment.
        
        Args:
            risks: Dict of sequencing risks
        
        Returns:
            True if successful
        """
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["sequencing_risks"]
            with open(path, 'w') as f:
                json.dump(risks, f, indent=2)
            logger.info(f"✓ Saved P8.6 sequencing risks: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save sequencing risks: {e}")
            return False

    def load_sequencing_risks(self) -> Optional[Dict[str, Any]]:
        """Load P8.6 mutation sequencing risk assessment."""
        try:
            path = self.orchestration_dir / self.SNAPSHOT_FILES["sequencing_risks"]
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sequencing risks: {e}")
            return None

def create_workspace_snapshot(workspace_root: str) -> WorkspaceMemorySnapshot:
    """Create a workspace memory snapshot manager."""
    return WorkspaceMemorySnapshot(workspace_root)


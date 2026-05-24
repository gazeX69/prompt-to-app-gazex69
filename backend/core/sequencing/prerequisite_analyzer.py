"""
Prerequisite Analysis Engine

Identifies required mutations for safe execution.

Analyzes:
- Required imports first
- Required providers first
- Required types first
- Required routes first
- Required symbols first

DRY-RUN ONLY — identifies prerequisites, does not execute.
"""

import logging
import re
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PrerequisiteType(str, Enum):
    """Types of prerequisites."""
    IMPORT = "import"                # Module/file must be imported
    EXPORT = "export"                # Symbol must be exported
    TYPE_DEFINITION = "type"         # Type/interface must be defined
    PROVIDER = "provider"            # DI provider must exist
    CONTEXT = "context"              # React context must exist
    HOOK = "hook"                    # Custom hook must be defined
    ROUTE = "route"                  # Route must be registered
    STYLESHEET = "stylesheet"        # CSS/style file must be imported
    CONFIG = "config"                # Configuration must be loaded
    DEPENDENCY = "dependency"        # npm/pip dependency must be in package


@dataclass(frozen=True)
class Prerequisite:
    """A single prerequisite for a mutation."""
    prereq_type: PrerequisiteType
    target: str                       # What must exist (file, symbol, etc.)
    reason: str                       # Why it's required
    target_file: Optional[str] = None # Where it should be imported/defined
    is_blocking: bool = True          # Blocks mutation if missing


class PrerequisiteAnalyzer:
    """
    Analyzes mutations to identify prerequisites.
    
    Methods scan code patterns to detect what must be set up first.
    """

    def __init__(self, repo_map: Optional[Any] = None):
        self.repo_map = repo_map

    def analyze_mutation(self, mutation: Any) -> List[Prerequisite]:
        """
        Analyze a single mutation to find prerequisites.
        
        Args:
            mutation: MutationEdit with target_file and code_to_insert
        
        Returns:
            List of prerequisites
        """
        target_file = getattr(mutation, 'target_file', '')
        code = getattr(mutation, 'code_to_insert', '')
        
        prerequisites = []
        
        # Analyze different code patterns
        prerequisites.extend(self._analyze_imports(code, target_file))
        prerequisites.extend(self._analyze_exports(code, target_file))
        prerequisites.extend(self._analyze_types(code, target_file))
        prerequisites.extend(self._analyze_providers(code, target_file))
        prerequisites.extend(self._analyze_hooks(code, target_file))
        prerequisites.extend(self._analyze_routes(code, target_file))
        prerequisites.extend(self._analyze_stylesheets(code, target_file))
        
        return prerequisites

    def _analyze_imports(self, code: str, target_file: str) -> List[Prerequisite]:
        """Extract import requirements."""
        prerequisites = []
        
        # Pattern: import { X } from 'path'
        import_pattern = r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]"
        matches = re.finditer(import_pattern, code)
        
        for match in matches:
            symbols = match.group(1)
            module_path = match.group(2)
            
            # Parse individual symbols
            for symbol in symbols.split(','):
                symbol = symbol.strip()
                if symbol:
                    prerequisites.append(Prerequisite(
                        prereq_type=PrerequisiteType.IMPORT,
                        target=f"{module_path}#{symbol}",
                        reason=f"Symbol '{symbol}' must be exported from '{module_path}'",
                        target_file=module_path,
                    ))
        
        # Pattern: import X from 'path'
        default_import_pattern = r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]"
        matches = re.finditer(default_import_pattern, code)
        
        for match in matches:
            symbol = match.group(1)
            module_path = match.group(2)
            
            prerequisites.append(Prerequisite(
                prereq_type=PrerequisiteType.IMPORT,
                target=f"{module_path}#{symbol}",
                reason=f"Default export '{symbol}' must exist in '{module_path}'",
                target_file=module_path,
            ))
        
        return prerequisites

    def _analyze_exports(self, code: str, target_file: str) -> List[Prerequisite]:
        """Extract export requirements (what this mutation provides)."""
        # This is informational — no prerequisites, but tracked for dependents
        return []

    def _analyze_types(self, code: str, target_file: str) -> List[Prerequisite]:
        """Extract type requirements."""
        prerequisites = []
        
        # Pattern: : TypeName or extends TypeName
        type_pattern = r":\s+(\w+)(?:\s*[<\|&]|\s*$|[,\)])"
        matches = re.finditer(type_pattern, code)
        
        types_found = set()
        for match in matches:
            type_name = match.group(1)
            if type_name and type_name not in ['string', 'number', 'boolean', 'any', 'void', 'never']:
                types_found.add(type_name)
        
        for type_name in types_found:
            prerequisites.append(Prerequisite(
                prereq_type=PrerequisiteType.TYPE_DEFINITION,
                target=type_name,
                reason=f"Type '{type_name}' must be defined before usage",
            ))
        
        # Pattern: extends Interface
        extends_pattern = r"extends\s+(\w+)"
        matches = re.finditer(extends_pattern, code)
        
        for match in matches:
            interface_name = match.group(1)
            prerequisites.append(Prerequisite(
                prereq_type=PrerequisiteType.TYPE_DEFINITION,
                target=interface_name,
                reason=f"Interface '{interface_name}' must be defined before extension",
            ))
        
        return prerequisites

    def _analyze_providers(self, code: str, target_file: str) -> List[Prerequisite]:
        """Extract provider/context requirements."""
        prerequisites = []
        
        # Pattern: useContext(XContext) or useXProvider
        context_pattern = r"useContext\((\w+Context)\)|use(\w+)Provider"
        matches = re.finditer(context_pattern, code)
        
        for match in matches:
            context_name = match.group(1) or match.group(2) + "Provider"
            prerequisites.append(Prerequisite(
                prereq_type=PrerequisiteType.PROVIDER,
                target=context_name,
                reason=f"Provider '{context_name}' must be wrapped at appropriate level",
            ))
        
        # Pattern: <XProvider> or Provider.create
        provider_pattern = r"<(\w+Provider|Suspense)>|Provider\.create\((\w+)\)"
        matches = re.finditer(provider_pattern, code)
        
        for match in matches:
            provider_name = match.group(1) or match.group(2)
            if 'Provider' in provider_name:
                prerequisites.append(Prerequisite(
                    prereq_type=PrerequisiteType.PROVIDER,
                    target=provider_name,
                    reason=f"Provider '{provider_name}' must be imported and available",
                ))
        
        return prerequisites

    def _analyze_hooks(self, code: str, target_file: str) -> List[Prerequisite]:
        """Extract custom hook requirements."""
        prerequisites = []
        
        # Pattern: use[A-Z] (custom hooks)
        hook_pattern = r"\b(use[A-Z][a-zA-Z]*)\("
        matches = re.finditer(hook_pattern, code)
        
        builtin_hooks = {'useState', 'useEffect', 'useContext', 'useReducer', 'useCallback', 
                         'useMemo', 'useRef', 'useLayoutEffect', 'useDebugValue'}
        
        for match in matches:
            hook_name = match.group(1)
            if hook_name not in builtin_hooks:
                prerequisites.append(Prerequisite(
                    prereq_type=PrerequisiteType.HOOK,
                    target=hook_name,
                    reason=f"Custom hook '{hook_name}' must be defined and exported",
                ))
        
        return prerequisites

    def _analyze_routes(self, code: str, target_file: str) -> List[Prerequisite]:
        """Extract route/navigation requirements."""
        prerequisites = []
        
        # Pattern: <Route ... component or path
        route_pattern = r"<Route\s+path=['\"]([^'\"]+)['\"]|useNavigate\(\)|useParams\(\)|useLocation\(\)"
        matches = re.finditer(route_pattern, code)
        
        for match in matches:
            if match.group(1):
                path = match.group(1)
                prerequisites.append(Prerequisite(
                    prereq_type=PrerequisiteType.ROUTE,
                    target=path,
                    reason=f"Route '{path}' must be registered in router config",
                ))
            else:
                # useNavigate, useParams, useLocation require routing setup
                prerequisites.append(Prerequisite(
                    prereq_type=PrerequisiteType.ROUTE,
                    target="router_setup",
                    reason="Router must be configured before using route hooks",
                ))
        
        return prerequisites

    def _analyze_stylesheets(self, code: str, target_file: str) -> List[Prerequisite]:
        """Extract stylesheet/CSS requirements."""
        prerequisites = []
        
        # Pattern: import '*.css' or className from module
        css_pattern = r"import\s+['\"]([^'\"]*\.css)['\"]|import\s+(\w+)\s+from\s+['\"]([^'\"]*\.module\.css)['\"]"
        matches = re.finditer(css_pattern, code)
        
        for match in matches:
            css_file = match.group(1) or match.group(3)
            if css_file:
                prerequisites.append(Prerequisite(
                    prereq_type=PrerequisiteType.STYLESHEET,
                    target=css_file,
                    reason=f"Stylesheet '{css_file}' must exist",
                ))
        
        return prerequisites


class PrerequisiteGraph:
    """
    Tracks all prerequisites across a set of mutations.
    
    Enables:
    - Prerequisite ordering
    - Dependency resolution
    - Missing prerequisite detection
    """

    def __init__(self):
        self.mutations: Dict[str, Any] = {}  # op_id -> mutation
        self.prerequisites: Dict[str, List[Prerequisite]] = {}  # op_id -> [prerequisites]
        self.provides: Dict[str, Set[str]] = {}  # op_id -> [symbols provided]

    def add_mutation(self, op_id: str, mutation: Any, prerequisites: List[Prerequisite]) -> None:
        """Register a mutation and its prerequisites."""
        self.mutations[op_id] = mutation
        self.prerequisites[op_id] = prerequisites
        self.provides[op_id] = set()

    def mark_provides(self, op_id: str, symbols: List[str]) -> None:
        """Mark what symbols this mutation provides."""
        self.provides[op_id] = set(symbols)

    def find_prerequisite_sources(self, op_id: str) -> Dict[Prerequisite, Optional[str]]:
        """
        Find which operations can satisfy each prerequisite.
        
        Returns: Dict[prerequisite -> source_op_id or None]
        """
        prereqs = self.prerequisites.get(op_id, [])
        sources = {}
        
        for prereq in prereqs:
            source = None
            
            # Look for mutations that provide this symbol
            for other_op_id, provides in self.provides.items():
                if other_op_id == op_id:
                    continue  # Skip self
                
                if prereq.target in provides or prereq.target.split('#')[1:][0] if '#' in prereq.target else False:
                    source = other_op_id
                    break
            
            sources[prereq] = source
        
        return sources

    def find_missing_prerequisites(self) -> Dict[str, List[Prerequisite]]:
        """Find prerequisites that are not provided by any mutation."""
        missing = {}
        
        for op_id in self.mutations.keys():
            sources = self.find_prerequisite_sources(op_id)
            missing_for_op = [p for p, source in sources.items() if source is None]
            
            if missing_for_op:
                missing[op_id] = missing_for_op
        
        return missing


def analyze_mutation_prerequisites(
    mutations: List[Any],
    repo_map: Optional[Any] = None,
) -> Tuple[Dict[str, List[Prerequisite]], PrerequisiteGraph]:
    """
    Analyze all mutations to extract prerequisites.
    
    Returns:
    - Dict mapping mutation index to prerequisites
    - PrerequisiteGraph for ordering
    """
    analyzer = PrerequisiteAnalyzer(repo_map)
    graph = PrerequisiteGraph()
    all_prerequisites = {}
    
    for i, mutation in enumerate(mutations):
        op_id = f"op_{i}"
        prerequisites = analyzer.analyze_mutation(mutation)
        all_prerequisites[op_id] = prerequisites
        graph.add_mutation(op_id, mutation, prerequisites)
    
    return all_prerequisites, graph


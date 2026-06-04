"""
SemanticSearchLayer

Implements semantic workspace search to locate:
- symbols
- components
- routes
- API handlers
- imports/usages
- dependency chains

Without relying only on filename matching.
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SymbolLocation:
    """Represents a symbol found in the workspace."""
    file_path: str
    symbol_name: str
    symbol_type: str  # 'function', 'class', 'component', 'route', 'const', 'export', etc.
    line_number: int
    context: str  # surrounding code context
    is_export: bool
    usages: List['SymbolUsage'] = field(default_factory=list)


@dataclass
class SymbolUsage:
    """Represents a usage of a symbol."""
    file_path: str
    line_number: int
    context: str


@dataclass
class ComponentLocation:
    """Represents a React/Vue component."""
    file_path: str
    component_name: str
    props: List[str]
    state: List[str]
    children: List[str]  # child components
    imports: List[str]
    line_number: int


@dataclass
class RouteDefinition:
    """Represents an API route."""
    file_path: str
    path: str
    method: str  # GET, POST, PUT, DELETE, etc.
    handler: str  # function name
    line_number: int
    middleware: List[str]


@dataclass
class ImportChain:
    """Represents a dependency chain."""
    source: str
    target: str
    path: List[str]  # breadcrumb trail


class SemanticSearchEngine:
    """
    Performs semantic analysis of workspace without relying only on filenames.
    """

    def __init__(self, root_path: str, module_index: Dict[str, any]):
        self.root_path = Path(root_path)
        self.module_index = module_index  # from RepositoryIntelligenceEngine.modules
        self._symbol_cache: Dict[str, List[SymbolLocation]] = {}
        self._usage_cache: Dict[str, List[SymbolUsage]] = {}

    def find_symbol(self, symbol_name: str, language: Optional[str] = None) -> List[SymbolLocation]:
        """
        Find a symbol definition by name.
        
        Args:
            symbol_name: Name of the symbol to find
            language: Optional language filter
        
        Returns:
            List of SymbolLocation objects
        """
        if symbol_name in self._symbol_cache:
            return self._symbol_cache[symbol_name]

        results = []
        
        for module_path, module in self.module_index.items():
            if language and module.language != language:
                continue
            
            if symbol_name in module.exports:
                try:
                    full_path = self.root_path / module_path
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    location = self._extract_symbol_location(
                        module_path, symbol_name, module.language, content
                    )
                    if location:
                        results.append(location)
                except Exception as e:
                    logger.warning(f"Failed to analyze {module_path}: {e}")
        
        self._symbol_cache[symbol_name] = results
        return results

    def find_usages(self, symbol_name: str) -> List[SymbolUsage]:
        """Find all usages of a symbol."""
        if symbol_name in self._usage_cache:
            return self._usage_cache[symbol_name]

        usages = []
        
        # Pattern to find the symbol being used
        patterns = {
            'python': [
                rf'\b{re.escape(symbol_name)}\s*\(',  # function call
                rf'from\s+\S+\s+import\s+.*{re.escape(symbol_name)}',  # import
            ],
            'javascript': [
                rf'\b{re.escape(symbol_name)}\s*[\(\.]',  # function call or property
                rf'import\s+.*{re.escape(symbol_name)}',  # import
            ],
            'typescript': [
                rf'\b{re.escape(symbol_name)}\s*[\(\.]',
                rf'import\s+.*{re.escape(symbol_name)}',
            ],
            'php': [
                rf'\${re.escape(symbol_name)}',  # variable
                rf'{re.escape(symbol_name)}\s*\(',  # function call
            ],
        }
        
        for module_path, module in self.module_index.items():
            if module.language not in patterns:
                continue
            
            try:
                full_path = self.root_path / module_path
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                for line_no, line in enumerate(lines, 1):
                    for pattern in patterns[module.language]:
                        if re.search(pattern, line):
                            usages.append(SymbolUsage(
                                file_path=module_path,
                                line_number=line_no,
                                context=line.strip()
                            ))
                            break
            except Exception as e:
                logger.warning(f"Failed to search usages in {module_path}: {e}")
        
        self._usage_cache[symbol_name] = usages
        return usages

    def find_components(self, language: str = 'typescript') -> List[ComponentLocation]:
        """
        Find React/Vue components.
        
        Args:
            language: 'typescript' for React/Vue components
        
        Returns:
            List of ComponentLocation objects
        """
        components = []
        
        # Patterns for React/Vue components
        react_patterns = [
            r'(?:export\s+)?(?:const|function|class)\s+(\w+)\s*(?:\([^)]*\)|\s*extends)',
            r'(?:export\s+)?function\s+(\w+)\s*\(',
        ]
        
        for module_path, module in self.module_index.items():
            if module.language not in ['typescript', 'javascript']:
                continue
            
            try:
                full_path = self.root_path / module_path
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check if file looks like a component
                if not self._is_component_file(content, module_path):
                    continue
                
                for match in re.finditer(react_patterns[0], content, re.MULTILINE):
                    comp_name = match.group(1)
                    # Filter out non-components (all caps = constants)
                    if not comp_name[0].isupper():
                        continue
                    
                    line_no = content[:match.start()].count('\n') + 1
                    
                    # Extract props and state
                    props = self._extract_props(content, comp_name)
                    state = self._extract_state(content)
                    children = self._extract_child_components(content)
                    imports = module.dependencies
                    
                    components.append(ComponentLocation(
                        file_path=module_path,
                        component_name=comp_name,
                        props=props,
                        state=state,
                        children=children,
                        imports=imports,
                        line_number=line_no,
                    ))
            except Exception as e:
                logger.warning(f"Failed to find components in {module_path}: {e}")
        
        return components

    def find_routes(self, framework: str = 'express') -> List[RouteDefinition]:
        """
        Find API routes.
        
        Args:
            framework: 'express' for Express.js, etc.
        
        Returns:
            List of RouteDefinition objects
        """
        routes = []
        
        # Express.js route patterns
        express_patterns = [
            r"(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
        ]
        
        for module_path, module in self.module_index.items():
            if module.language not in ['javascript', 'typescript']:
                continue
            
            try:
                full_path = self.root_path / module_path
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Skip non-route files
                if 'router' not in module_path.lower() and 'route' not in module_path.lower():
                    if not any(kw in content for kw in ['app.get', 'app.post', 'router.get']):
                        continue
                
                for pattern in express_patterns:
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        method = match.group(1).upper()
                        path = match.group(2)
                        line_no = content[:match.start()].count('\n') + 1
                        
                        # Try to find handler function name
                        handler_match = re.search(
                            rf"{re.escape(match.group(0))}\s*,\s*(\w+)",
                            content[match.start():match.start()+500]
                        )
                        handler = handler_match.group(1) if handler_match else 'unknown'
                        
                        routes.append(RouteDefinition(
                            file_path=module_path,
                            path=path,
                            method=method,
                            handler=handler,
                            line_number=line_no,
                            middleware=[],
                        ))
            except Exception as e:
                logger.warning(f"Failed to find routes in {module_path}: {e}")
        
        return routes

    def trace_dependency_chain(self, from_symbol: str, to_symbol: str) -> Optional[ImportChain]:
        """
        Trace how one symbol imports another.
        
        Args:
            from_symbol: Starting symbol name
            to_symbol: Target symbol name
        
        Returns:
            ImportChain or None if no path found
        """
        # BFS to find shortest path
        visited = set()
        queue = [(from_symbol, [from_symbol])]
        
        while queue:
            current, path = queue.pop(0)
            if current == to_symbol:
                return ImportChain(source=from_symbol, target=to_symbol, path=path)
            
            if current in visited:
                continue
            visited.add(current)
            
            # Find symbols that import current
            for module_path, module in self.module_index.items():
                if current in module.dependencies:
                    for export in module.exports:
                        if export not in visited:
                            queue.append((export, path + [export]))
        
        return None

    def find_api_handlers(self) -> List[str]:
        """Find all API handler functions."""
        handlers = []
        handler_patterns = [
            r'(?:async\s+)?function\s+(\w*(?:get|post|put|delete|patch|handler|middleware)\w*)\s*\(',
            r'(?:const|let|var)\s+(\w*(?:handler|middleware)\w*)\s*=',
        ]
        
        for module_path, module in self.module_index.items():
            if module.language not in ['javascript', 'typescript']:
                continue
            
            try:
                full_path = self.root_path / module_path
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern in handler_patterns:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        handler_name = match.group(1)
                        handlers.append(handler_name)
            except Exception as e:
                logger.warning(f"Failed to find handlers in {module_path}: {e}")
        
        return list(set(handlers))

    # ========== PRIVATE HELPERS ==========

    def _extract_symbol_location(
        self, module_path: str, symbol_name: str, language: str, content: str
    ) -> Optional[SymbolLocation]:
        """Extract line number and context for a symbol."""
        if language == 'python':
            pattern = r'^(?:class|def)\s+' + re.escape(symbol_name) + r'\s*[\(:]'
        elif language in ['javascript', 'typescript']:
            pattern = (
                r"(?:export\s+)?(?:const|function|class)\s+"
                + re.escape(symbol_name)
                + r"\s*[\(\{=]"
            )
        elif language == 'php':
            pattern = r'(?:class|function)\s+' + re.escape(symbol_name) + r'\s*[\(\{]'
        else:
            return None

        
        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            return None
        
        line_no = content[:match.start()].count('\n') + 1
        # Get surrounding context (5 lines)
        lines = content.split('\n')
        start = max(0, line_no - 3)
        end = min(len(lines), line_no + 3)
        context = '\n'.join(lines[start:end])
        
        # Determine symbol type
        if 'class' in match.group(0):
            symbol_type = 'class'
        elif 'function' in match.group(0):
            symbol_type = 'function'
        else:
            symbol_type = 'const'
        
        return SymbolLocation(
            file_path=module_path,
            symbol_name=symbol_name,
            symbol_type=symbol_type,
            line_number=line_no,
            context=context,
            is_export='export' in match.group(0),
        )

    def _is_component_file(self, content: str, module_path: str) -> bool:
        """Check if file looks like a React component."""
        # Component files typically:
        # 1. Have JSX syntax
        # 2. Export a default or named component
        # 3. Are in components/ or pages/ folder
        # 4. Have names starting with uppercase
        
        has_jsx = re.search(r'<\w+[^>]*>', content)
        has_export = 'export' in content
        is_component_dir = any(x in module_path.lower() for x in ['component', 'page', 'view'])
        
        return (has_jsx and has_export) or is_component_dir

    def _extract_props(self, content: str, comp_name: str) -> List[str]:
        """Extract component props."""
        # Find component definition
        pattern = r'(?:function|const)\s+' + re.escape(comp_name) + r'\s*\(({[^}]*}|[^)]*)\)'
        match = re.search(pattern, content)
        if not match:
            return []
        
        params = match.group(1)
        # Simple extraction of destructured props
        props = re.findall(r'\b(\w+)\s*:', params)
        return props

    def _extract_state(self, content: str) -> List[str]:
        """Extract useState declarations."""
        state = []
        # Pattern: const [state, setState] = useState(...)
        pattern = r'const\s+\[(\w+)(?:\s*,\s*\w+)?\]\s*=\s*useState'
        for match in re.finditer(pattern, content):
            state.append(match.group(1))
        return state

    def _extract_child_components(self, content: str) -> List[str]:
        """Extract child component references."""
        children = []
        # Pattern: <ComponentName ... />
        pattern = r'<(\w+)[^>]*/>'
        for match in re.finditer(pattern, content):
            comp = match.group(1)
            # Filter out built-in HTML elements
            if comp[0].isupper():
                children.append(comp)
        return list(set(children))


def create_semantic_search(
    root_path: str, module_index: Dict[str, any]
) -> SemanticSearchEngine:
    """Create a semantic search engine."""
    return SemanticSearchEngine(root_path, module_index)

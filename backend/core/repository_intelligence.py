"""
RepositoryIntelligenceEngine

Capabilities:
- recursive repo scan
- module ownership detection
- dependency graph extraction
- entrypoint detection
- framework detection
- build/test command detection
- config file discovery
- import graph mapping
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModuleInfo:
    """Represents a module/package with ownership metadata."""
    path: str
    name: str
    module_type: str  # 'file', 'directory', 'package'
    language: str  # 'python', 'javascript', 'typescript', 'php', etc.
    exports: List[str]  # symbols exported
    dependencies: List[str]  # internal imports/requires
    size_lines: int
    is_entry: bool = False
    is_framework: bool = False


@dataclass
class DependencyNode:
    """Represents a dependency in the graph."""
    name: str
    version: Optional[str]
    dep_type: str  # 'npm', 'pip', 'composer', 'internal'
    location: str  # package.json, requirements.txt, etc.


@dataclass
class DependencyRipple:
    """Mutation ripple analysis for a module."""
    module_path: str
    direct_dependents: List[str]  # modules that directly import this
    transitive_dependents: List[str]  # all modules transitively dependent
    ripple_depth: int  # max transitive depth
    ripple_breadth: int  # count of affected modules
    is_critical: bool  # high-dependency zone
    circular_deps: List[Tuple[str, str]]  # circular dependency pairs


@dataclass
class RepositoryMap:
    """Complete snapshot of repository structure."""
    root_path: str
    framework: str  # 'react', 'node', 'php', 'laravel', 'django', etc.
    language_mix: Dict[str, int]  # language -> count
    modules: Dict[str, ModuleInfo]  # path -> ModuleInfo
    entrypoints: List[str]  # main.js, index.php, __main__.py, etc.
    dependency_graph: Dict[str, List[str]]  # module -> [imports]
    external_dependencies: List[DependencyNode]
    build_commands: Dict[str, str]  # 'build', 'test', 'dev', etc.
    config_files: List[str]  # package.json, tsconfig.json, etc.
    ignore_patterns: List[str]  # .gitignore patterns loaded
    dependency_ripples: Dict[str, DependencyRipple] = None  # module -> ripple analysis
    reverse_dependency_graph: Dict[str, List[str]] = None  # module <- [dependents]


class RepositoryIntelligenceEngine:
    """
    Analyzes a repository to build deep understanding of:
    - Structure
    - Dependencies
    - Frameworks
    - Entry points
    - Build configuration
    """

    IGNORE_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', '.nuxt', '.pytest_cache',
        '.tox', 'coverage', '.egg-info', '.mypy_cache',
        '.vscode', '.idea', 'target', 'vendor', '.DS_Store'
    }

    LANGUAGE_EXTENSIONS = {
        'python': {'.py'},
        'javascript': {'.js', '.jsx'},
        'typescript': {'.ts', '.tsx'},
        'php': {'.php'},
        'java': {'.java'},
        'go': {'.go'},
        'rust': {'.rs'},
        'html': {'.html', '.htm'},
        'css': {'.css', '.scss', '.sass'},
        'json': {'.json'},
    }

    CONFIG_FILES = {
        'package.json', 'tsconfig.json', 'vite.config.js', 'vite.config.ts',
        'webpack.config.js', 'babel.config.js',
        'requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile',
        'composer.json', 'composer.lock',
        'Gemfile', '.env', '.env.local',
        'dockerfile', 'docker-compose.yml',
        'jest.config.js', 'vitest.config.ts',
    }

    ENTRYPOINT_FILES = {
        'index.js', 'index.ts', 'index.tsx', 'main.js', 'main.ts', 'main.tsx',
        'app.js', 'app.ts',
        'index.php', 'index.html', 'main.php',
        '__main__.py', 'main.py', 'app.py',
        'src/index.js', 'src/main.tsx',
    }

    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.framework = ''
        self.modules: Dict[str, ModuleInfo] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.external_deps: List[DependencyNode] = []
        self.build_commands: Dict[str, str] = {}
        self.config_files: List[str] = []
        self.entrypoints: List[str] = []
        self.ignore_patterns: List[str] = []
        self.language_mix: Dict[str, int] = {}

    def analyze(self) -> RepositoryMap:
        """Execute full repository analysis."""
        logger.info(f"Analyzing repository: {self.root_path}")
        
        self._load_ignore_patterns()
        self._scan_directory()
        self._detect_framework()
        self._extract_dependencies()
        self._detect_entrypoints()
        self._build_dependency_graph()
        self._detect_build_commands()
        self._compute_dependency_ripples()

        return RepositoryMap(
            root_path=str(self.root_path),
            framework=self.framework,
            language_mix=self.language_mix,
            modules=self.modules,
            entrypoints=self.entrypoints,
            dependency_graph=self.dependency_graph,
            external_dependencies=self.external_deps,
            build_commands=self.build_commands,
            config_files=self.config_files,
            ignore_patterns=self.ignore_patterns,
            dependency_ripples=self._build_ripples_map(),
            reverse_dependency_graph=self._build_reverse_graph(),
        )

    def _load_ignore_patterns(self):
        """Load patterns from .gitignore."""
        gitignore_path = self.root_path / '.gitignore'
        if gitignore_path.exists():
            try:
                with open(gitignore_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.ignore_patterns.append(line)
            except Exception as e:
                logger.warning(f"Failed to read .gitignore: {e}")

    def _should_ignore(self, path: Path) -> bool:
        """Check if path matches ignore patterns."""
        # Always ignore known directories
        for part in path.relative_to(self.root_path).parts:
            if part in self.IGNORE_DIRS:
                return True
        return False

    def _get_language(self, ext: str) -> Optional[str]:
        """Map file extension to language."""
        for lang, exts in self.LANGUAGE_EXTENSIONS.items():
            if ext.lower() in exts:
                return lang
        return None

    def _scan_directory(self):
        """Recursively scan directory structure."""
        logger.info("Scanning directory structure...")
        
        for path in self.root_path.rglob('*'):
            if self._should_ignore(path):
                continue

            if path.is_file():
                ext = path.suffix
                lang = self._get_language(ext)
                
                if lang:
                    self.language_mix[lang] = self.language_mix.get(lang, 0) + 1
                
                # Track config files
                if path.name in self.CONFIG_FILES:
                    rel_path = str(path.relative_to(self.root_path))
                    self.config_files.append(rel_path)
                
                # Index source files
                if lang in ['python', 'javascript', 'typescript', 'php']:
                    rel_path = str(path.relative_to(self.root_path))
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            lines = len(content.split('\n'))
                        
                        module = ModuleInfo(
                            path=rel_path,
                            name=path.stem,
                            module_type='file',
                            language=lang,
                            exports=self._extract_exports(content, lang),
                            dependencies=self._extract_imports(content, lang),
                            size_lines=lines,
                        )
                        self.modules[rel_path] = module
                    except Exception as e:
                        logger.warning(f"Failed to analyze {path}: {e}")

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from source."""
        imports = []
        
        if language in ['javascript', 'typescript']:
            # Match: import x from 'y', require('y')
            patterns = [
                r"import\s+.*from\s+['\"]([^'\"]+)['\"]",
                r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            ]
        elif language == 'python':
            # Match: import x, from x import y
            patterns = [
                r"^import\s+([\w\.]+)",
                r"^from\s+([\w\.]+)\s+import",
            ]
        elif language == 'php':
            # Match: require, include, namespace
            patterns = [
                r"(?:require|include)(?:_once)?\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
                r"namespace\s+([\w\\]+)",
            ]
        else:
            return imports
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                imports.append(match.group(1))
        
        return list(set(imports))

    def _extract_exports(self, content: str, language: str) -> List[str]:
        """Extract exported symbols."""
        exports = []
        
        if language in ['javascript', 'typescript']:
            # Match: export const x, export function x, export class X
            patterns = [
                r"export\s+(?:const|let|var)\s+(\w+)",
                r"export\s+(?:function|class)\s+(\w+)",
                r"export\s+\{([^}]+)\}",
            ]
        elif language == 'python':
            # Match: class X, def x
            patterns = [
                r"^(?:class|def)\s+(\w+)",
            ]
        elif language == 'php':
            # Match: class X, function x
            patterns = [
                r"(?:class|function)\s+(\w+)",
            ]
        else:
            return exports
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                symbol = match.group(1)
                if '{' not in symbol:  # Skip destructuring
                    exports.append(symbol.strip())
        
        return list(set(exports))

    def _detect_framework(self):
        """Detect framework from config files."""
        for config_file in self.config_files:
            if 'package.json' in config_file:
                try:
                    with open(self.root_path / config_file) as f:
                        pkg = json.load(f)
                        deps = pkg.get('dependencies', {})
                        devDeps = pkg.get('devDependencies', {})
                        all_deps = {**deps, **devDeps}
                        
                        if 'react' in all_deps:
                            self.framework = 'react'
                        elif 'vue' in all_deps:
                            self.framework = 'vue'
                        elif 'next' in all_deps:
                            self.framework = 'next'
                        elif 'express' in all_deps:
                            self.framework = 'express'
                        else:
                            self.framework = 'node'
                except Exception as e:
                    logger.warning(f"Failed to parse {config_file}: {e}")
            
            elif 'composer.json' in config_file:
                self.framework = 'php'
                try:
                    with open(self.root_path / config_file) as f:
                        composer = json.load(f)
                        if 'laravel' in str(composer.get('require', {})):
                            self.framework = 'laravel'
                except Exception as e:
                    logger.warning(f"Failed to parse {config_file}: {e}")
            
            elif config_file.endswith('requirements.txt'):
                self.framework = 'python'
                try:
                    with open(self.root_path / config_file) as f:
                        reqs = f.read()
                        if 'django' in reqs:
                            self.framework = 'django'
                        elif 'flask' in reqs:
                            self.framework = 'flask'
                except Exception as e:
                    logger.warning(f"Failed to parse {config_file}: {e}")

    def _extract_dependencies(self):
        """Extract external dependencies from config files."""
        for config_file in self.config_files:
            try:
                path = self.root_path / config_file
                
                if 'package.json' in config_file:
                    with open(path) as f:
                        pkg = json.load(f)
                        for name, version in pkg.get('dependencies', {}).items():
                            self.external_deps.append(DependencyNode(
                                name=name, version=version, dep_type='npm',
                                location=config_file
                            ))
                        for name, version in pkg.get('devDependencies', {}).items():
                            self.external_deps.append(DependencyNode(
                                name=name, version=version, dep_type='npm',
                                location=config_file
                            ))
                
                elif 'requirements.txt' in config_file:
                    with open(path) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                parts = re.split(r'[=<>!]', line)
                                name = parts[0].strip()
                                self.external_deps.append(DependencyNode(
                                    name=name, version=None, dep_type='pip',
                                    location=config_file
                                ))
                
                elif 'composer.json' in config_file:
                    with open(path) as f:
                        composer = json.load(f)
                        for name, version in composer.get('require', {}).items():
                            self.external_deps.append(DependencyNode(
                                name=name, version=version, dep_type='composer',
                                location=config_file
                            ))
            except Exception as e:
                logger.warning(f"Failed to extract deps from {config_file}: {e}")

    def _detect_entrypoints(self):
        """Identify entrypoint files."""
        for entry in self.ENTRYPOINT_FILES:
            path = self.root_path / entry
            if path.exists():
                self.entrypoints.append(entry)

    def _build_dependency_graph(self):
        """Build import graph for internal dependencies."""
        for module_path, module in self.modules.items():
            self.dependency_graph[module_path] = module.dependencies

    def _detect_build_commands(self):
        """Extract build/test commands from package.json or scripts."""
        for config_file in self.config_files:
            if 'package.json' in config_file:
                try:
                    with open(self.root_path / config_file) as f:
                        pkg = json.load(f)
                        scripts = pkg.get('scripts', {})
                        self.build_commands = {
                            k: v for k, v in scripts.items()
                            if any(kw in k for kw in ['build', 'test', 'dev', 'start', 'serve'])
                        }
                except Exception as e:
                    logger.warning(f"Failed to extract scripts from {config_file}: {e}")

    def _build_reverse_graph(self) -> Dict[str, List[str]]:
        """Build reverse dependency graph (module <- dependents)."""
        reverse = {module: [] for module in self.dependency_graph}
        
        for module, deps in self.dependency_graph.items():
            for dep in deps:
                # Normalize dependency to module path if possible
                dep_module = self._resolve_dependency_module(dep)
                if dep_module and dep_module in reverse:
                    reverse[dep_module].append(module)
        
        return reverse

    def _resolve_dependency_module(self, dep: str) -> Optional[str]:
        """Try to resolve a dependency string to an actual module path."""
        # Simple heuristic: match against module names
        for module_path, module_info in self.modules.items():
            if module_info.name == dep.split('/')[-1]:
                return module_path
        
        # Check if it matches a folder structure
        for module_path in self.modules.keys():
            if dep.replace('.', '/') in module_path or dep in module_path:
                return module_path
        
        return None

    def _build_ripples_map(self) -> Dict[str, DependencyRipple]:
        """Build ripple analysis for each module."""
        ripples = {}
        reverse_graph = self._build_reverse_graph() if hasattr(self, '_build_reverse_graph') else {}
        
        for module_path in self.modules.keys():
            # Compute transitive dependents
            direct_dependents = reverse_graph.get(module_path, [])
            transitive = self._compute_transitive_dependents(module_path, reverse_graph)
            
            # Detect circular dependencies
            circulars = self._detect_circular_dependencies(module_path, self.dependency_graph)
            
            # Calculate ripple metrics
            ripple_depth = self._calculate_ripple_depth(module_path, reverse_graph)
            is_critical = ripple_depth >= 3 or len(transitive) >= 5
            
            ripples[module_path] = DependencyRipple(
                module_path=module_path,
                direct_dependents=direct_dependents,
                transitive_dependents=transitive,
                ripple_depth=ripple_depth,
                ripple_breadth=len(transitive),
                is_critical=is_critical,
                circular_deps=circulars,
            )
        
        return ripples

    def _compute_transitive_dependents(
        self,
        module: str,
        reverse_graph: Dict[str, List[str]],
        visited: Optional[Set[str]] = None,
        max_depth: int = 10
    ) -> List[str]:
        """Recursively compute all modules that depend on this one."""
        if visited is None:
            visited = set()
        
        if module in visited or max_depth == 0:
            return []
        
        visited.add(module)
        transitive = []
        
        for dependent in reverse_graph.get(module, []):
            if dependent not in visited:
                transitive.append(dependent)
                transitive.extend(
                    self._compute_transitive_dependents(dependent, reverse_graph, visited, max_depth - 1)
                )
        
        return list(set(transitive))

    def _calculate_ripple_depth(self, module: str, reverse_graph: Dict[str, List[str]], depth: int = 0, max_depth: int = 10) -> int:
        """Calculate max depth of dependent chain."""
        if depth > max_depth or module not in reverse_graph or not reverse_graph[module]:
            return depth
        
        return max(
            self._calculate_ripple_depth(dep, reverse_graph, depth + 1, max_depth)
            for dep in reverse_graph[module]
        ) if reverse_graph[module] else depth

    def _detect_circular_dependencies(self, module: str, graph: Dict[str, List[str]], visited: Optional[Set[str]] = None, rec_stack: Optional[Set[str]] = None) -> List[Tuple[str, str]]:
        """Detect circular dependencies involving this module."""
        if visited is None:
            visited = set()
        if rec_stack is None:
            rec_stack = set()
        
        circulars = []
        visited.add(module)
        rec_stack.add(module)
        
        for dep in graph.get(module, []):
            resolved_dep = self._resolve_dependency_module(dep)
            if not resolved_dep:
                continue
            
            if resolved_dep not in visited:
                circulars.extend(
                    self._detect_circular_dependencies(resolved_dep, graph, visited, rec_stack)
                )
            elif resolved_dep in rec_stack:
                circulars.append((module, resolved_dep))
        
        rec_stack.remove(module)
        return list(set(circulars))


def analyze_repository(repo_path: str) -> RepositoryMap:
    """Convenience function to analyze a repository."""
    engine = RepositoryIntelligenceEngine(repo_path)
    return engine.analyze()


def repo_map_to_dict(repo_map: RepositoryMap) -> Dict:
    """Convert RepositoryMap to serializable dict."""
    ripples_dict = {}
    if repo_map.dependency_ripples:
        ripples_dict = {
            k: {
                'module_path': v.module_path,
                'direct_dependents': v.direct_dependents,
                'transitive_dependents': v.transitive_dependents,
                'ripple_depth': v.ripple_depth,
                'ripple_breadth': v.ripple_breadth,
                'is_critical': v.is_critical,
                'circular_deps': list(v.circular_deps),
            }
            for k, v in repo_map.dependency_ripples.items()
        }
    
    return {
        'root_path': repo_map.root_path,
        'framework': repo_map.framework,
        'language_mix': repo_map.language_mix,
        'modules': {k: asdict(v) for k, v in repo_map.modules.items()},
        'entrypoints': repo_map.entrypoints,
        'dependency_graph': repo_map.dependency_graph,
        'reverse_dependency_graph': repo_map.reverse_dependency_graph or {},
        'external_dependencies': [asdict(d) for d in repo_map.external_dependencies],
        'build_commands': repo_map.build_commands,
        'config_files': repo_map.config_files,
        'ignore_patterns': repo_map.ignore_patterns,
        'dependency_ripples': ripples_dict,
    }

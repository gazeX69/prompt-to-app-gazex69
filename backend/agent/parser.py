"""
Parses and validates raw AI responses into structured file lists using a deterministic delimiter protocol.
"""

from backend.models.schemas import GeneratedFile

class ParseError(Exception):
    """Raised when the AI response cannot be parsed into a valid file list."""

def parse_ai_response(raw: str) -> list[GeneratedFile]:
    """
    State machine parser for delimiter-based protocol:
    
    ===FILE:path/to/file.ext===
    content
    ===END===
    """
    files: list[GeneratedFile] = []
    
    # splitlines handles \r\n, \r, and \n gracefully without retaining the newline character itself
    lines = raw.splitlines()
    
    current_file_path = None
    current_content = []
    in_file = False
    
    for i, line in enumerate(lines):
        if line.startswith("===FILE:") and line.endswith("==="):
            if in_file:
                raise ParseError(f"Malformed delimiter at line {i+1}: Started a new file before closing the previous one (===END=== missing).")
                
            path_str = line[8:-3].strip()
            
            if not path_str:
                raise ParseError(f"Malformed delimiter at line {i+1}: Missing file path.")
                
            # Path validation: no path traversal or absolute paths
            if ".." in path_str or path_str.startswith("/") or path_str.startswith("\\"):
                raise ParseError(f"Invalid file path {path_str!r}: Absolute paths and path traversal (..) are forbidden.")
                
            current_file_path = path_str
            current_content = []
            in_file = True
            
        elif line.strip() == "===END===":
            if not in_file:
                # ignore dangling END blocks or log them
                continue
                
            content_str = "\n".join(current_content)
            files.append(GeneratedFile(path=current_file_path, content=content_str))
            
            current_file_path = None
            current_content = []
            in_file = False
            
        else:
            if in_file:
                current_content.append(line)
                
    if in_file:
        raise ParseError(f"Malformed delimiter: Reached end of output but ===END=== was missing for {current_file_path!r}")
         
    if not files:
        raise ParseError("No valid delimiter blocks found in AI response.")
        
    return files

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
    
    import re
    
    for i, line in enumerate(lines):
        # Strip common comment markers to support cases where LLM comments out the delimiter
        stripped = line.strip()
        clean = re.sub(r'^(?://|/\*|#|--)\s*', '', stripped).strip()
        clean = re.sub(r'\s*\*/$', '', clean).strip()
        
        if clean.startswith("===FILE:") and clean.endswith("==="):
            if in_file:
                # Resilient fallback: auto-close the previous file
                if current_content:
                    while current_content and not current_content[0].strip():
                        current_content.pop(0)
                    if current_content and current_content[0].strip().startswith("```"):
                        current_content.pop(0)
                    while current_content and not current_content[-1].strip():
                        current_content.pop()
                    if current_content and current_content[-1].strip() == "```":
                        current_content.pop()
                    while current_content and not current_content[0].strip():
                        current_content.pop(0)
                    while current_content and not current_content[-1].strip():
                        current_content.pop()
                    content_str = "\n".join(current_content)
                    files.append(GeneratedFile(path=current_file_path, content=content_str))
                in_file = False
                
            path_str = clean[8:-3].strip()
            
            if not path_str:
                raise ParseError(f"Malformed delimiter at line {i+1}: Missing file path.")
                
            # Path validation: no path traversal or absolute paths
            if ".." in path_str or path_str.startswith("/") or path_str.startswith("\\"):
                raise ParseError(f"Invalid file path {path_str!r}: Absolute paths and path traversal (..) are forbidden.")
                
            current_file_path = path_str
            current_content = []
            in_file = True
            
        elif clean == "===END===":
            if not in_file:
                # ignore dangling END blocks or log them
                continue
                
            # Strip markdown code block markers (like ```tsx ... ```)
            if current_content:
                while current_content and not current_content[0].strip():
                    current_content.pop(0)
                if current_content and current_content[0].strip().startswith("```"):
                    current_content.pop(0)
                while current_content and not current_content[-1].strip():
                    current_content.pop()
                if current_content and current_content[-1].strip() == "```":
                    current_content.pop()
                while current_content and not current_content[0].strip():
                    current_content.pop(0)
                while current_content and not current_content[-1].strip():
                    current_content.pop()

            content_str = "\n".join(current_content)
            files.append(GeneratedFile(path=current_file_path, content=content_str))
            
            current_file_path = None
            current_content = []
            in_file = False
            
        else:
            if in_file:
                current_content.append(line)
                
    if in_file:
        # Resilient fallback: auto-close the file at the end of input
        if current_content:
            while current_content and not current_content[0].strip():
                current_content.pop(0)
            if current_content and current_content[0].strip().startswith("```"):
                current_content.pop(0)
            while current_content and not current_content[-1].strip():
                current_content.pop()
            if current_content and current_content[-1].strip() == "```":
                current_content.pop()
            while current_content and not current_content[0].strip():
                current_content.pop(0)
            while current_content and not current_content[-1].strip():
                current_content.pop()
            content_str = "\n".join(current_content)
            files.append(GeneratedFile(path=current_file_path, content=content_str))
        in_file = False
         
    if not files:
        # Fallback: Parse markdown code blocks if delimiter protocol failed
        blocks = re.findall(r'(?:(?:^|\n)(?:###?|####?)\s*([a-zA-Z0-9_\-\./\\]+)\s*\n)?\s*```[a-zA-Z0-9_\-]*\n(.*?)\n```', raw, re.DOTALL)
        for header, content in blocks:
            path_str = header.strip() if header else ""
            if not path_str:
                # Try to extract from the first line of content if it's a comment
                content_lines = content.splitlines()
                first_line = content_lines[0].strip() if content_lines else ""
                match = re.match(r'^(?://|#|/\*|--)\s*([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)\s*(?:\*/)?$', first_line)
                if match:
                    path_str = match.group(1).strip()
            
            if path_str and ("." in path_str):
                # Clean path and exclude absolute or traversal paths
                path_str = path_str.replace("src/", "src/").strip()
                if not (path_str.startswith("/") or path_str.startswith("\\") or ".." in path_str):
                    content_lines = content.splitlines()
                    if not header and content_lines:
                        content_lines.pop(0)
                    content_str = "\n".join(content_lines)
                    files.append(GeneratedFile(path=path_str, content=content_str))
                    
    if not files:
        raise ParseError("No valid delimiter blocks found in AI response.")
        
    return files

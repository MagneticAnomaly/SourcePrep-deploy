import os
import re

directories_to_scan = ['src', 'packages', 'websites', 'engine', 'docs', 'tests', 'scripts']
file_extensions = {'.py', '.ts', '.tsx', '.js', '.json', '.md', '.rs', '.toml', '.yml', '.yaml', '.sh', '.html', '.css'}

codrag_pattern = re.compile(r'codrag', re.IGNORECASE)
total_files_with_codrag = 0
total_occurrences = 0

folder_counts = {folder: 0 for folder in directories_to_scan}
folder_files = {folder: 0 for folder in directories_to_scan}

for root, dirs, files in os.walk('.'):
    # Skip hidden dirs, node_modules, dist, build, target
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'dist', 'build', 'target', '.venv', '__pycache__')]
    
    for file in files:
        ext = os.path.splitext(file)[1].lower()
        if ext in file_extensions:
            filepath = os.path.join(root, file)
            # determine which top level folder this is in
            parts = filepath.split(os.sep)
            top_folder = parts[1] if len(parts) > 1 else None
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = codrag_pattern.findall(content)
                    if matches:
                        total_files_with_codrag += 1
                        total_occurrences += len(matches)
                        if top_folder in folder_counts:
                            folder_counts[top_folder] += len(matches)
                            folder_files[top_folder] += 1
            except Exception:
                pass

print(f"Total files containing 'codrag': {total_files_with_codrag}")
print(f"Total occurrences of 'codrag': {total_occurrences}")
print("\nBreakdown by top-level folder:")
for folder in directories_to_scan:
    print(f"  {folder}/: {folder_files[folder]} files, {folder_counts[folder]} occurrences")


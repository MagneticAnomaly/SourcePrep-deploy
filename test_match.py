from typing import List, Optional, Dict

def _best_project_match(projects: List[Dict[str, str]], paths: List[str]) -> Optional[str]:
    best_id: Optional[str] = None
    best_len = -1
    ambiguous = False

    for p in projects:
        pid = p.get("id")
        p_path = str(p.get("path") or "").rstrip("/")
        if not pid or not p_path:
            continue
        for check_path in paths:
            check = check_path.rstrip("/")
            if not check:
                check = "/"
                
            score = -1
            if check == p_path:
                score = 10000 + len(p_path)
            elif check.startswith(p_path + "/"):
                score = 1000 + len(p_path)
            elif p_path.startswith(check + "/"):
                score = len(check)
            elif check == "/" and p_path:
                score = 1

            if score > -1:
                if score > best_len:
                    best_id = str(pid)
                    best_len = score
                    ambiguous = False
                elif score == best_len and str(pid) != best_id:
                    ambiguous = True
                    
    print(f"best_id={best_id}, best_len={best_len}, ambiguous={ambiguous}")
    if ambiguous:
        return None
    return best_id

projects = [
    {"id": "root", "path": "/Volumes/4TB-BAD/HumanAI/CoDRAG"},
    {"id": "TEST", "path": "/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST"},
    {"id": "TEST2", "path": "/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST2"},
    {"id": "mini-redis", "path": "/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/real_repos/mini-redis-rust"},
]

print("Test: multiple paths (like Cursor sends)")
_best_project_match(projects, [
    "/Volumes/4TB-BAD/HumanAI/CoDRAG"
])


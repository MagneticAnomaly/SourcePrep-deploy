import re

with open('src/codrag/services/config_manager.py', 'r') as f:
    content = f.read()

# Make sure we add a hook to run ensure_compute_nodes
new_load_logic = """    # Try SQLite store first (Phase 24)
    try:
        from codrag.services.settings_store import settings
        store_data = settings.get_all()
        if store_data:
            _merge_config_data(cfg, store_data)
            
            # Phase 45: Ensure compute_nodes are populated on load for legacy clients
            _ensure_compute_nodes(cfg)
            
            return cfg
    except Exception:
        pass"""

content = re.sub(
    r'    # Try SQLite store first \(Phase 24\).*?except Exception:\n        pass',
    new_load_logic,
    content,
    flags=re.DOTALL
)

fallback_logic = """    from_json = _load_json_fallback(config)
    if from_json:
        _merge_config_data(cfg, from_json)
        
    # Phase 45: Ensure compute_nodes are populated on load for legacy clients
    _ensure_compute_nodes(cfg)
        
    return cfg"""

content = re.sub(
    r'    from_json = _load_json_fallback\(config\)\n    if from_json:\n        _merge_config_data\(cfg, from_json\)\n\n    return cfg',
    fallback_logic,
    content
)

ensure_func = """
def _ensure_compute_nodes(cfg: Dict[str, Any]) -> None:
    \"\"\"Phase 45: Auto-migrate existing configs to Multi-GPU structure.\"\"\"
    import uuid
    
    if "compute_nodes" not in cfg:
        cfg["compute_nodes"] = []
        
    if not cfg["compute_nodes"]:
        # We need to auto-create
        
        # 1. Local Node
        hw_profile = cfg.get("hardware_profile", "apple_silicon")
        concurrency = cfg.get("llm_concurrency", 1)
        
        local_node_id = f"node_{uuid.uuid4().hex[:8]}"
        local_node = {
            "id": local_node_id,
            "name": "Local Machine",
            "type": "local",
            "hardware_profile": hw_profile,
            "max_concurrent": concurrency,
            "endpoint_ids": []
        }
        
        endpoints = cfg.get("saved_endpoints", [])
        
        # Associate local endpoints
        for ep in endpoints:
            url = ep.get("url", "")
            if "localhost" in url or "127.0.0.1" in url:
                ep["compute_node_id"] = local_node_id
                local_node["endpoint_ids"].append(ep["id"])
                
        cfg["compute_nodes"].append(local_node)
        
        # 2. Cloud Node (if applicable)
        cloud_endpoints = [
            ep for ep in endpoints 
            if ep.get("provider") in ["openai", "anthropic", "google"] 
            or ("localhost" not in ep.get("url", "") and "127.0.0.1" not in ep.get("url", ""))
        ]
        
        if cloud_endpoints:
            cloud_node_id = f"node_{uuid.uuid4().hex[:8]}"
            cloud_node = {
                "id": cloud_node_id,
                "name": "Cloud",
                "type": "cloud",
                "hardware_profile": "cloud",
                "max_concurrent": 100,
                "endpoint_ids": []
            }
            
            for ep in cloud_endpoints:
                if not ep.get("compute_node_id"):
                    ep["compute_node_id"] = cloud_node_id
                    cloud_node["endpoint_ids"].append(ep["id"])
                    
            cfg["compute_nodes"].append(cloud_node)

def default_ui_config(config: Dict[str, Any]) -> Dict[str, Any]:
"""

content = content.replace("def default_ui_config(config: Dict[str, Any]) -> Dict[str, Any]:", ensure_func)

with open('src/codrag/services/config_manager.py', 'w') as f:
    f.write(content)

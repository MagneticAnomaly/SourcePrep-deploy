#!/usr/bin/env python3
"""
Generate a signed offline CoDRAG license key.

Usage:
  python scripts/generate_license.py --email user@example.com --tier pro

Options:
  --email    Email address of the licensee
  --tier     Tier (free, monthly, perpetual, team, enterprise)
  --priv     Hex encoded Ed25519 private key (or uses test key if omitted)
  --out      Output file (default: stdout)
"""

import argparse
import base64
import json
import time
import uuid
import sys
from typing import Dict, Any

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("Error: cryptography package is required. Run: pip install cryptography")
    sys.exit(1)


# The default test private key (matches the test public key in codrag.core.licensing)
# DO NOT USE IN PRODUCTION
DEFAULT_PRIV_KEY_HEX = "c6b3c439525def409ea605e0143ba2ab91d933f300c155c42e2e824b057da84f"


def _base64url_encode(data: bytes) -> str:
    """Helper to encode bytes to base64url string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_license(email: str, tier: str, priv_hex: str) -> str:
    """Generate a signed license string: payload.signature"""
    
    # 1. Construct payload
    now = int(time.time())
    payload_dict: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "issued_to": email,
        "issued_at": now,
        "tier": tier,
        "seats": 1,
        "features": [],
        "valid": True
    }
    
    # If it's a monthly license, we might want to set an expiry.
    # For now, we'll just generate perpetual-style keys that don't expire
    # for these manual overrides.
    
    payload_json = json.dumps(payload_dict, separators=(",", ":"))
    payload_b64 = _base64url_encode(payload_json.encode("utf-8"))
    
    # 2. Sign payload
    # Note: codrag.core.licensing.verify_license_key signs the base64 string
    # "payload_b64" (if 2 parts) or "header_b64.payload_b64" (if 3 parts).
    # We'll use the 2-part format.
    signing_input = payload_b64.encode("ascii")
    
    priv_key_bytes = bytes.fromhex(priv_hex)
    priv_key = Ed25519PrivateKey.from_private_bytes(priv_key_bytes)
    
    signature = priv_key.sign(signing_input)
    sig_b64 = _base64url_encode(signature)
    
    # 3. Combine
    return f"{payload_b64}.{sig_b64}"


def main():
    parser = argparse.ArgumentParser(description="Generate CoDRAG License Key")
    parser.add_argument("--email", required=True, help="Email address of the licensee")
    parser.add_argument("--tier", required=True, choices=["free", "monthly", "perpetual", "team", "enterprise"], help="License tier")
    parser.add_argument("--priv", help="Hex encoded Ed25519 private key (defaults to test key)")
    parser.add_argument("--out", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    priv_hex = args.priv or DEFAULT_PRIV_KEY_HEX
    
    if args.priv is None:
        print("WARNING: Using default test private key. Do not use for real licenses!", file=sys.stderr)
        
    license_key = generate_license(args.email, args.tier, priv_hex)
    
    if args.out:
        with open(args.out, "w") as f:
            f.write(license_key)
        print(f"License key written to {args.out}")
    else:
        print("\n=== CoDRAG License Key ===")
        print(license_key)
        print("==========================\n")


if __name__ == "__main__":
    main()

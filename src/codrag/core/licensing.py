from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
except ImportError:
    Ed25519PublicKey = None  # type: ignore
    InvalidSignature = None  # type: ignore

logger = logging.getLogger(__name__)

# Hardcoded public key for verifying licenses (Production)
# In a real scenario, this would be the public key corresponding to the private key used by the licensing server.
# For now, we'll use a placeholder or load it from config if needed.
# This is a random Ed25519 public key for demonstration/dev purposes.
# We will allow overriding this via env var CODRAG_LICENSE_PUBLIC_KEY for testing.
DEFAULT_PUBLIC_KEY_HEX = "3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29" 

def verify_license_key(key: str, public_key_hex: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Verify a signed license key.
    Format: header.payload.signature (JWT-like) or just payload.signature
    Payload is Base64URL-encoded JSON.
    Signature is Base64URL-encoded Ed25519 signature of the payload.
    
    Returns the payload dict if valid, None otherwise.
    """
    if Ed25519PublicKey is None:
        logger.error("cryptography library not installed, cannot verify license signatures")
        return None

    if not key or "." not in key:
        return None

    parts = key.split(".")
    # Support both {header}.{payload}.{signature} and {payload}.{signature}
    if len(parts) == 3:
        _, payload_b64, sig_b64 = parts
    elif len(parts) == 2:
        payload_b64, sig_b64 = parts
    else:
        return None

    try:
        # Decode payload
        payload_bytes = _base64url_decode(payload_b64)
        payload_str = payload_bytes.decode("utf-8")
        payload = json.loads(payload_str)
        
        # Decode signature
        sig_bytes = _base64url_decode(sig_b64)
        
        # Verify signature
        pub_hex = public_key_hex or DEFAULT_PUBLIC_KEY_HEX
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        
        # The signature covers the *encoded* payload string as bytes
        # Standard JWT signs "{header}.{payload}". 
        # Our custom format might sign just the payload string or the encoded payload.
        # Let's assume we sign the encoded payload string bytes for simplicity and standard-ish behavior.
        # Ideally, we verify what was signed. 
        # If we follow JWT EdDSA (RFC 8037), the input to sign is ASCII(BASE64URL(UTF8(JWS Protected Header)) || '.' || BASE64URL(JWS Payload))
        
        # For this implementation, let's assume we sign the `payload_b64` string bytes directly if it's 2 parts,
        # or `header_b64 + "." + payload_b64` if 3 parts.
        
        signing_input = ".".join(parts[:-1]).encode("ascii")
        
        public_key.verify(sig_bytes, signing_input)
        
        return payload
        
    except (InvalidSignature, ValueError, json.JSONDecodeError) as e:
        logger.warning(f"License verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during license verification: {e}")
        return None

def _base64url_decode(input: str) -> bytes:
    """Helper to decode base64url-encoded string."""
    rem = len(input) % 4
    if rem > 0:
        input += "=" * (4 - rem)
    return base64.urlsafe_b64decode(input)

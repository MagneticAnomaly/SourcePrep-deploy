import base64
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
priv = Ed25519PrivateKey.generate()
pub = priv.public_key()
print("Priv:", priv.private_bytes(
    encoding=__import__('cryptography.hazmat.primitives.serialization').hazmat.primitives.serialization.Encoding.Raw,
    format=__import__('cryptography.hazmat.primitives.serialization').hazmat.primitives.serialization.PrivateFormat.Raw,
    encryption_algorithm=__import__('cryptography.hazmat.primitives.serialization').hazmat.primitives.serialization.NoEncryption()
).hex())
print("Pub:", pub.public_bytes(
    encoding=__import__('cryptography.hazmat.primitives.serialization').hazmat.primitives.serialization.Encoding.Raw,
    format=__import__('cryptography.hazmat.primitives.serialization').hazmat.primitives.serialization.PublicFormat.Raw
).hex())

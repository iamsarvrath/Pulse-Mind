import os
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
from cryptography.fernet import Fernet

# Security Constants
# In production, these must be loaded from a secure vault
JWT_SECRET = os.getenv("JWT_SECRET", "pulsemind-super-secret-key-123")
JWT_ALGORITHM = "HS256"
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=60)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict]:
    """Decode and validate a JWT access token."""
    try:
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded_token if decoded_token["exp"] >= datetime.utcnow().timestamp() else None
    except Exception:
        return None

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data using AES-256 (Fernet)."""
    if not data:
        return ""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt data using AES-256 (Fernet)."""
    if not encrypted_data:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return "[DECRYPTION_FAILED]"

def anonymize_id(user_id: str) -> str:
    """Simple hash-based anonymization for logging."""
    import hashlib
    return hashlib.sha256(user_id.encode()).hexdigest()[:8] + "****"

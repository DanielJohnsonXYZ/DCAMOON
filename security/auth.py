"""Authentication and security utilities for DCAMOON trading system."""

import os
import json
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)


class SecurityManager:
    """Handles encryption, API key management, and security operations."""
    
    def __init__(self, master_key: Optional[str] = None):
        """Initialize security manager.
        
        Args:
            master_key: Master encryption key. If None, generates or loads from environment.
        """
        self._master_key = master_key or self._get_or_create_master_key()
        self._cipher = self._create_cipher(self._master_key)
    
    def _get_or_create_master_key(self) -> str:
        """Get master key from environment or create new one."""
        env_key = os.getenv('DCAMOON_MASTER_KEY')
        if env_key:
            return env_key
        
        # Generate new key
        key = Fernet.generate_key().decode()
        logger.warning(
            "No master key found in environment. Generated new key. "
            "Set DCAMOON_MASTER_KEY environment variable to: %s", 
            key
        )
        return key
    
    def _create_cipher(self, key: str) -> Fernet:
        """Create Fernet cipher from key."""
        try:
            # If key is already a valid Fernet key
            return Fernet(key.encode())
        except Exception:
            # Derive key from password using PBKDF2
            password = key.encode()
            salt = b'dcamoon_salt'  # In production, use random salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key_bytes = base64.urlsafe_b64encode(kdf.derive(password))
            return Fernet(key_bytes)
    
    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt an API key for secure storage.
        
        Args:
            api_key: Plain text API key
            
        Returns:
            Encrypted API key as base64 string
        """
        try:
            encrypted = self._cipher.encrypt(api_key.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Error encrypting API key: {e}")
            raise
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt an API key.
        
        Args:
            encrypted_key: Encrypted API key as base64 string
            
        Returns:
            Plain text API key
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Error decrypting API key: {e}")
            raise
    
    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password with salt
        """
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash.
        
        Args:
            password: Plain text password
            hashed: Hashed password with salt
            
        Returns:
            True if password matches
        """
        try:
            salt, password_hash = hashed.split(':')
            expected_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return secrets.compare_digest(password_hash, expected_hash)
        except ValueError:
            return False
    
    def generate_session_token(self) -> str:
        """Generate a secure session token."""
        return secrets.token_urlsafe(32)
    
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> str:
        """Encrypt sensitive data for storage.
        
        Args:
            data: Dictionary of sensitive data
            
        Returns:
            Encrypted data as base64 string
        """
        try:
            json_data = json.dumps(data)
            encrypted = self._cipher.encrypt(json_data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Error encrypting sensitive data: {e}")
            raise
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt sensitive data.
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted data dictionary
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Error decrypting sensitive data: {e}")
            raise


class APIKeyManager:
    """Manages API keys with secure storage."""
    
    def __init__(self, security_manager: SecurityManager):
        self.security = security_manager
        self._api_keys: Dict[str, str] = {}
    
    def store_api_key(self, service: str, api_key: str) -> None:
        """Store an API key securely.
        
        Args:
            service: Service name (e.g., 'openai', 'alpaca')
            api_key: Plain text API key
        """
        try:
            encrypted_key = self.security.encrypt_api_key(api_key)
            self._api_keys[service] = encrypted_key
            logger.info(f"API key stored for service: {service}")
        except Exception as e:
            logger.error(f"Error storing API key for {service}: {e}")
            raise
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Get an API key for a service.
        
        Args:
            service: Service name
            
        Returns:
            Plain text API key or None if not found
        """
        try:
            encrypted_key = self._api_keys.get(service)
            if not encrypted_key:
                # Try environment variable as fallback
                env_key = os.getenv(f"{service.upper()}_API_KEY")
                if env_key:
                    return env_key
                return None
            
            return self.security.decrypt_api_key(encrypted_key)
        except Exception as e:
            logger.error(f"Error retrieving API key for {service}: {e}")
            return None
    
    def remove_api_key(self, service: str) -> bool:
        """Remove an API key.
        
        Args:
            service: Service name
            
        Returns:
            True if key was removed
        """
        if service in self._api_keys:
            del self._api_keys[service]
            logger.info(f"API key removed for service: {service}")
            return True
        return False
    
    def list_services(self) -> list[str]:
        """List services with stored API keys."""
        return list(self._api_keys.keys())
    
    def save_to_file(self, filepath: str) -> None:
        """Save encrypted API keys to file.
        
        Args:
            filepath: Path to save file
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self._api_keys, f, indent=2)
            logger.info(f"API keys saved to: {filepath}")
        except Exception as e:
            logger.error(f"Error saving API keys to file: {e}")
            raise
    
    def load_from_file(self, filepath: str) -> None:
        """Load encrypted API keys from file.
        
        Args:
            filepath: Path to load file
        """
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    self._api_keys = json.load(f)
                logger.info(f"API keys loaded from: {filepath}")
            else:
                logger.info(f"API keys file not found: {filepath}")
        except Exception as e:
            logger.error(f"Error loading API keys from file: {e}")
            raise


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int, time_window: int):
        """Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: Dict[str, list[datetime]] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if a call is allowed for the identifier.
        
        Args:
            identifier: Unique identifier (e.g., API key, user ID)
            
        Returns:
            True if call is allowed
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.time_window)
        
        # Clean old calls
        if identifier in self.calls:
            self.calls[identifier] = [
                call_time for call_time in self.calls[identifier]
                if call_time > cutoff
            ]
        else:
            self.calls[identifier] = []
        
        # Check if limit exceeded
        if len(self.calls[identifier]) >= self.max_calls:
            return False
        
        # Record this call
        self.calls[identifier].append(now)
        return True
    
    def get_reset_time(self, identifier: str) -> Optional[datetime]:
        """Get when the rate limit resets for an identifier."""
        if identifier not in self.calls or not self.calls[identifier]:
            return None
        
        oldest_call = min(self.calls[identifier])
        return oldest_call + timedelta(seconds=self.time_window)


class SecurityAuditLogger:
    """Logs security-related events for auditing."""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or "security_audit.log"
        self.logger = logging.getLogger("security_audit")
        
        # Set up file handler for security logs
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_api_key_access(self, service: str, success: bool, ip_address: Optional[str] = None):
        """Log API key access attempt."""
        self.logger.info(
            f"API_KEY_ACCESS - Service: {service}, Success: {success}, IP: {ip_address or 'unknown'}"
        )
    
    def log_trade_execution(self, portfolio_id: str, ticker: str, trade_type: str, amount: float):
        """Log trade execution."""
        self.logger.info(
            f"TRADE_EXECUTION - Portfolio: {portfolio_id}, Ticker: {ticker}, "
            f"Type: {trade_type}, Amount: ${amount:.2f}"
        )
    
    def log_rate_limit_exceeded(self, identifier: str, endpoint: str):
        """Log rate limit exceeded."""
        self.logger.warning(
            f"RATE_LIMIT_EXCEEDED - Identifier: {identifier}, Endpoint: {endpoint}"
        )
    
    def log_authentication_failure(self, identifier: str, reason: str):
        """Log authentication failure."""
        self.logger.warning(
            f"AUTH_FAILURE - Identifier: {identifier}, Reason: {reason}"
        )
    
    def log_data_access(self, table: str, operation: str, user: Optional[str] = None):
        """Log database access."""
        self.logger.info(
            f"DATA_ACCESS - Table: {table}, Operation: {operation}, User: {user or 'system'}"
        )


# Global security instances
_security_manager: Optional[SecurityManager] = None
_api_key_manager: Optional[APIKeyManager] = None
_audit_logger: Optional[SecurityAuditLogger] = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager(get_security_manager())
        # Try to load existing keys
        try:
            _api_key_manager.load_from_file("api_keys.json")
        except Exception:
            pass
    return _api_key_manager


def get_audit_logger() -> SecurityAuditLogger:
    """Get the global security audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecurityAuditLogger()
    return _audit_logger


def setup_security(master_key: Optional[str] = None, api_keys_file: Optional[str] = None) -> None:
    """Setup security components.
    
    Args:
        master_key: Master encryption key
        api_keys_file: Path to API keys file
    """
    global _security_manager, _api_key_manager, _audit_logger
    
    _security_manager = SecurityManager(master_key)
    _api_key_manager = APIKeyManager(_security_manager)
    _audit_logger = SecurityAuditLogger()
    
    if api_keys_file:
        try:
            _api_key_manager.load_from_file(api_keys_file)
        except Exception as e:
            logger.error(f"Error loading API keys from {api_keys_file}: {e}")
    
    logger.info("Security components initialized")
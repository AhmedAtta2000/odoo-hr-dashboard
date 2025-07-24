# In backend/security.py
import os
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load the encryption key from environment variables
ENCRYPTION_KEY_STR = os.getenv("CREDENTIAL_ENCRYPTION_KEY")

if not ENCRYPTION_KEY_STR:
    raise ValueError("CREDENTIAL_ENCRYPTION_KEY environment variable not set. Cannot perform encryption/decryption.")

try:
    # Ensure the key is in bytes
    ENCRYPTION_KEY = ENCRYPTION_KEY_STR.encode()
    # Initialize Fernet with the key
    fernet = Fernet(ENCRYPTION_KEY)
except Exception as e:
     raise ValueError(f"Invalid CREDENTIAL_ENCRYPTION_KEY format: {e}")


def encrypt_data(data: str) -> str:
    """Encrypts a string using Fernet."""
    if not isinstance(data, str):
         raise TypeError("Input data must be a string")
    try:
        encrypted_data = fernet.encrypt(data.encode())
        # Return the encrypted data as a URL-safe string
        return encrypted_data.decode()
    except Exception as e:
        print(f"Encryption failed: {e}")
        # Handle error appropriately, maybe raise a custom exception
        raise ConnectionError("Encryption failed") from e # Use generic error to avoid leaking details


def decrypt_data(encrypted_data: str) -> str | None:
    """Decrypts a Fernet token string. Returns None if decryption fails."""
    if not isinstance(encrypted_data, str):
         print("Warning: Encrypted data received is not a string")
         return None # Or raise TypeError
    try:
        decrypted_data_bytes = fernet.decrypt(encrypted_data.encode())
        # Decode the bytes back to a string
        return decrypted_data_bytes.decode()
    except InvalidToken:
        print("Error: Invalid or tampered encryption token.")
        return None # Return None or raise a specific error
    except Exception as e:
        print(f"Decryption failed for an unknown reason: {e}")
        return None # Return None or raise a specific error
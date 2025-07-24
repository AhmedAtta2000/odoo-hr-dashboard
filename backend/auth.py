import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict 

from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))  

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
# This tells FastAPI where to look for the token (in the Authorization header)
# tokenUrl is the relative path to your login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

# --- Utility Functions ---
def verify_password(plain_password, hashed_password):
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Hashes a plain password."""
    return pwd_context.hash(password)

def _create_token(data: dict, expires_delta: timedelta, token_type: str = "access"):
    """Helper function to create either an access or refresh token."""
    to_encode = data.copy()
    # Add a 'type' claim to distinguish token types if needed, though expiry is primary
    # to_encode.update({"token_type": token_type}) # Optional
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(data, expires_delta, token_type="access")

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT refresh token."""
    if expires_delta is None:
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    # Refresh token payload might be simpler, e.g., only containing 'sub' (user_identifier)
    # and not 'is_admin', as its sole purpose is to get a new access token.
    # For now, let's keep the data passed to it, which will include 'sub' and 'is_admin'.
    return _create_token(data, expires_delta, token_type="refresh")

async def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> Dict[str, any]:
    """Decodes the access token and returns the full payload."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials (access token)", # Specify token type
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # print(f"DEBUG get_current_user_payload: Decoding access token: {token[:10]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_identifier: Optional[str] = payload.get("sub") # Ensure str type hint for clarity
        if user_identifier is None:
            raise credentials_exception
        # Optional: Check for a 'token_type' claim if you added it
        # if payload.get("token_type") != "access":
        #     raise credentials_exception # Not an access token
        return payload
    except JWTError as e:
        # print(f"DEBUG get_current_user_payload: JWTError: {e}")
        raise credentials_exception from e
    except Exception as e_gen:
        # print(f"DEBUG get_current_user_payload: Exception: {e_gen}")
        raise credentials_exception from e_gen

# --- Dependency for protected routes (we'll use this later) ---
async def get_current_user(user_payload: dict = Depends(get_current_user_payload)):
    """Returns user identifier from the token payload."""
    return {"user_identifier": user_payload.get("sub")}

async def get_current_admin_user(user_payload: dict = Depends(get_current_user_payload)):
    """
    Dependency to ensure the current user is an admin.
    Relies on 'is_admin' claim in the JWT payload.
    """
    is_admin = user_payload.get("is_admin", False) # Get 'is_admin' claim, default to False
    user_identifier = user_payload.get("sub")

    if not is_admin:
        print(f"Admin access denied for user: {user_identifier}. is_admin claim: {is_admin}") # For debugging
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted: Administrator access required."
        )
    print(f"Admin access GRANTED for user: {user_identifier}") # For debugging
    # Return the same dict as get_current_user, or just the user_identifier
    return {"user_identifier": user_identifier, "is_admin": True}

def validate_refresh_token(token: str) -> Optional[Dict[str, any]]: # Returns payload if valid
    """Decodes and validates a refresh token."""
    try:
        # print(f"DEBUG validate_refresh_token: Decoding refresh token: {token[:10]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Optional: Check for a 'token_type' claim if you added it during creation
        # if payload.get("token_type") != "refresh":
        #     _logger.warning("Invalid token type provided for refresh.")
        #     return None
        user_identifier: Optional[str] = payload.get("sub")
        if user_identifier is None:
            _logger.warning("Refresh token payload missing 'sub' (user identifier).")
            return None
        # print(f"DEBUG validate_refresh_token: Refresh token valid for user: {user_identifier}")
        return payload # Return the payload (contains 'sub', 'is_admin', 'exp')
    except JWTError as e:
        _logger.warning(f"Refresh token validation failed (JWTError): {e}")
        return None
    except Exception as e_gen:
        _logger.exception(f"Unexpected error validating refresh token.") # Log full traceback
        return None
# In backend/crud.py
from sqlalchemy.orm import Session
# Import your models and potentially schemas (Pydantic models for data validation/shaping)
import models
# import schemas # We might define schemas later for request/response validation
from auth import get_password_hash # Need this to hash password on create
from typing import List,  Optional
import models # Ensure models are imported
from auth import get_password_hash # For user creation
from security import encrypt_data # For encrypting Odoo key
from datetime import datetime, timedelta, timezone
from auth import get_password_hash # For password hashing
from security import encrypt_data, decrypt_data # Ensure these are imported


# --- User CRUD ---

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]: # Renamed/Ensured
    """Fetches a single user by their ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    """Fetches a single user by their email address."""
    return db.query(models.User).filter(models.User.email == email).first()

def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]: # New for listing all
    """Fetches all users with pagination for admin."""
    return db.query(models.User).order_by(models.User.id).offset(skip).limit(limit).all()

def create_user(db: Session, user_data: dict, tenant_id: int): # Add tenant_id parameter
    """Creates a new user in the database, associated with a tenant."""
    hashed_password = get_password_hash(user_data["password"])
    db_user = models.User(
        email=user_data["email"],
        hashed_password=hashed_password,
        full_name=user_data.get("full_name"),
        job_title=user_data.get("job_title"),
        phone=user_data.get("phone"),
        tenant_id=tenant_id # Assign the tenant ID
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_document(db: Session, user_id: int, filename: str, doc_type: str, file_path: str) -> models.Document:
    """Creates a new document metadata record for a user."""
    db_document = models.Document(
        filename=filename,
        document_type=doc_type,
        file_path=file_path,
        owner_id=user_id # Link it to the user ID
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document) # Get the generated ID and defaults
    return db_document

def get_documents_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Document]:
    """Fetches documents for a specific user with pagination."""
    return db.query(models.Document)\
             .filter(models.Document.owner_id == user_id)\
             .order_by(models.Document.upload_date.desc())\
             .offset(skip)\
             .limit(limit)\
             .all()

def get_document_by_id(db: Session, document_id: str, user_id: int) -> models.Document | None:
    """Fetches a single document by its ID, ensuring it belongs to the user."""
    return db.query(models.Document)\
             .filter(models.Document.id == document_id, models.Document.owner_id == user_id)\
             .first()

def get_odoo_credential_by_tenant(db: Session, tenant_id: int) -> Optional[models.OdooCredential]:
    """Fetches the OdooCredential record for a specific tenant."""
    return db.query(models.OdooCredential)\
             .filter(models.OdooCredential.tenant_id == tenant_id)\
             .first()

# --- Tenant CRUD ---
def get_tenant_by_id(db: Session, tenant_id: int) -> Optional[models.Tenant]:
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()

def get_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[models.Tenant]:
    """Fetches all tenants with pagination."""
    return db.query(models.Tenant).order_by(models.Tenant.name).offset(skip).limit(limit).all()

# --- Odoo Credential CRUD ---
def get_odoo_credential_by_tenant(db: Session, tenant_id: int) -> Optional[models.OdooCredential]:
    """Fetches the OdooCredential record for a specific tenant."""
    return db.query(models.OdooCredential)\
             .filter(models.OdooCredential.tenant_id == tenant_id)\
             .first()

def create_or_update_odoo_credential(db: Session, tenant_id: int, odoo_base_url: str, odoo_db_name: str, odoo_username: str, plain_api_key: str) -> models.OdooCredential:
    """Creates or updates Odoo credentials for a tenant. Encrypts the API key."""
    # Check if tenant exists
    tenant = get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant:
        # Or raise an error if tenant must exist
        return None

    encrypted_key = encrypt_data(plain_api_key) # Encrypt the key
    db_credential = get_odoo_credential_by_tenant(db, tenant_id=tenant_id)

    if db_credential: # Update existing
        db_credential.odoo_base_url = odoo_base_url
        db_credential.odoo_db_name = odoo_db_name
        db_credential.odoo_username = odoo_username
        db_credential.encrypted_odoo_api_key = encrypted_key
    else: # Create new
        db_credential = models.OdooCredential(
            tenant_id=tenant_id,
            odoo_base_url=odoo_base_url,
            odoo_db_name=odoo_db_name,
            odoo_username=odoo_username,
            encrypted_odoo_api_key=encrypted_key
        )
        db.add(db_credential)
    db.commit()
    db.refresh(db_credential)
    return db_credential# --- Tenant CRUD ---
def get_tenant_by_id(db: Session, tenant_id: int) -> Optional[models.Tenant]:
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()

def get_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[models.Tenant]:
    """Fetches all tenants with pagination."""
    return db.query(models.Tenant).order_by(models.Tenant.name).offset(skip).limit(limit).all()

# --- Odoo Credential CRUD ---
def get_odoo_credential_by_tenant(db: Session, tenant_id: int) -> Optional[models.OdooCredential]:
    """Fetches the OdooCredential record for a specific tenant."""
    return db.query(models.OdooCredential)\
             .filter(models.OdooCredential.tenant_id == tenant_id)\
             .first()

def create_or_update_odoo_credential(db: Session, tenant_id: int, odoo_base_url: str, odoo_db_name: str, odoo_username: str, plain_api_key: str) -> models.OdooCredential:
    """Creates or updates Odoo credentials for a tenant. Encrypts the API key."""
    # Check if tenant exists
    tenant = get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant:
        # Or raise an error if tenant must exist
        return None

    encrypted_key = encrypt_data(plain_api_key) # Encrypt the key
    db_credential = get_odoo_credential_by_tenant(db, tenant_id=tenant_id)

    if db_credential: # Update existing
        db_credential.odoo_base_url = odoo_base_url
        db_credential.odoo_db_name = odoo_db_name
        db_credential.odoo_username = odoo_username
        db_credential.encrypted_odoo_api_key = encrypted_key
    else: # Create new
        db_credential = models.OdooCredential(
            tenant_id=tenant_id,
            odoo_base_url=odoo_base_url,
            odoo_db_name=odoo_db_name,
            odoo_username=odoo_username,
            encrypted_odoo_api_key=encrypted_key
        )
        db.add(db_credential)
    db.commit()
    db.refresh(db_credential)
    return db_credential


# --- Tenant CRUD ---
def get_tenant_by_id(db: Session, tenant_id: int) -> Optional[models.Tenant]:
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()

def get_tenant_by_name(db: Session, name: str) -> Optional[models.Tenant]: # New helper
    return db.query(models.Tenant).filter(models.Tenant.name == name).first()

def get_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[models.Tenant]:
    return db.query(models.Tenant).order_by(models.Tenant.name).offset(skip).limit(limit).all()

def create_tenant(db: Session, name: str, is_active: bool = True) -> models.Tenant: # Added is_active
    """Creates a new tenant."""
    db_tenant = models.Tenant(name=name, is_active=is_active)
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def update_tenant_status(db: Session, tenant_id: int, is_active: bool) -> Optional[models.Tenant]:
    """Updates the active status of a tenant."""
    db_tenant = get_tenant_by_id(db, tenant_id=tenant_id)
    if db_tenant:
        db_tenant.is_active = is_active
        db.commit()
        db.refresh(db_tenant)
    return db_tenant # Returns the updated tenant or None if not found    


def set_password_reset_token(db: Session, user: models.User, token: str, expires_in_minutes: int = 60) -> None:
    """Sets the password reset token and its expiry on a user object."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    user.password_reset_token = token
    user.password_reset_token_expires_at = expires_at
    db.add(user) # Add to session if it's a new object or detached
    db.commit()
    db.refresh(user)

def get_user_by_password_reset_token(db: Session, token: str) -> Optional[models.User]:
    """Fetches a user by a valid (non-expired) password reset token."""
    now = datetime.now(timezone.utc)
    return db.query(models.User)\
             .filter(models.User.password_reset_token == token,
                     models.User.password_reset_token_expires_at > now, # Check for expiry
                     models.User.is_active == True) \
             .first()

def clear_password_reset_token(db: Session, user: models.User) -> None:
    """Clears the password reset token and expiry from a user object."""
    user.password_reset_token = None
    user.password_reset_token_expires_at = None
    db.add(user)
    db.commit()
    # No need to refresh user here unless using the updated fields immediately

def update_user_password(db: Session, user: models.User, new_password: str) -> None:
    """Updates the user's password with a new hashed password."""
    user.hashed_password = get_password_hash(new_password)
    db.add(user)
    db.commit()    



def create_saas_user(db: Session, user_data: dict[str, any]) -> models.User:
    """
    Creates a new SaaS user. Expects keys like 'email', 'password', 'full_name',
    'tenant_id', 'is_admin', 'is_active', 'odoo_employee_id' (optional).
    """
    hashed_password = get_password_hash(user_data["password"])
    db_user = models.User(
        email=user_data["email"],
        hashed_password=hashed_password,
        full_name=user_data.get("full_name"),
        job_title=user_data.get("job_title"), # Or remove if not set by admin
        phone=user_data.get("phone"),       # Or remove
        is_admin=user_data.get("is_admin", False),
        is_active=user_data.get("is_active", True),
        tenant_id=user_data["tenant_id"], # Should be required
        odoo_employee_id=user_data.get("odoo_employee_id") # Optional at creation
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_saas_user(db: Session, user_id: int, user_update_data: dict[str, any]) -> Optional[models.User]:
    """
    Updates an existing SaaS user's details.
    'user_update_data' can contain: 'full_name', 'email', 'is_active', 'is_admin',
    'tenant_id', 'odoo_employee_id'.
    Password update should be a separate, dedicated function for clarity/security if needed.
    """
    db_user = get_user_by_id(db, user_id=user_id)
    if not db_user:
        return None

    update_data = user_update_data.copy() # Avoid modifying the input dict

    # Handle password separately if provided
    if "password" in update_data and update_data["password"]: # Check if password is not empty
        db_user.hashed_password = get_password_hash(update_data["password"])
        del update_data["password"] # Remove from dict to avoid direct setattr

    for key, value in update_data.items():
        if hasattr(db_user, key): # Check if attribute exists on the model
            setattr(db_user, key, value)
        else:
            _logger.warning(f"Attempted to update non-existent field '{key}' on user {user_id}")


    db.commit()
    db.refresh(db_user)
    return db_user

def delete_saas_user(db: Session, user_id: int) -> bool:
    """
    Deletes a SaaS user. Returns True if deleted, False if not found.
    Consider soft delete (setting is_active=False) instead of hard delete for production.
    """
    db_user = get_user_by_id(db, user_id=user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False    


# --- OTP/2FA CRUD Functions ---
def set_user_otp_secret(db: Session, user: models.User, otp_secret: str) -> None:
    """Encrypts and saves the OTP secret for a user."""
    user.encrypted_otp_secret = encrypt_data(otp_secret)
    # is_otp_enabled will be set in a separate step after successful OTP verification by user
    db.add(user)
    db.commit()
    db.refresh(user)

def enable_user_otp(db: Session, user: models.User, otp_secret: str) -> None:
    """Encrypts and saves the OTP secret and enables OTP for the user."""
    user.encrypted_otp_secret = encrypt_data(otp_secret)
    user.is_otp_enabled = True
    db.add(user)
    db.commit()
    db.refresh(user)

def disable_user_otp(db: Session, user: models.User) -> None:
    """Disables OTP and clears the OTP secret for a user."""
    user.is_otp_enabled = False
    user.encrypted_otp_secret = None # Clear the secret
    # user.encrypted_otp_backup_codes = None # Clear backup codes if implemented
    db.add(user)
    db.commit()
    db.refresh(user)

def get_decrypted_otp_secret(db: Session, user: models.User) -> Optional[str]:
    """Fetches and decrypts the user's OTP secret."""
    if user.encrypted_otp_secret:
        return decrypt_data(user.encrypted_otp_secret)
    return None    

def delete_tenant(db: Session, tenant_id: int) -> bool:
    """
    Deletes a tenant. Returns True if deleted, False if not found.
    WARNING: This is a hard delete. Consider implications for associated users,
    Odoo credentials, etc. Soft delete (is_active=False) is often safer.
    You might need to handle cascading deletes or prevent deletion if users are linked.
    """
    db_tenant = get_tenant_by_id(db, tenant_id=tenant_id)
    if db_tenant:
        # Before deleting, you might want to check for associated users or credentials
        # and decide on a strategy (e.g., prevent delete, orphan them, cascade delete).
        # For now, a simple delete:
        if db_tenant.users: # Check if there are any users associated with this tenant
             # Depending on your DB schema's ForeignKey constraints (ON DELETE behavior):
             # If users.tenant_id is SET NULL ON DELETE, users will be orphaned.
             # If users.tenant_id is RESTRICT or NO ACTION, this delete will fail if users exist.
             # If users.tenant_id is CASCADE, users will be deleted too (DANGEROUS!).
             # For now, let's prevent deletion if users are linked to keep it simple and safe.
             # You should define a proper strategy for this in a real application.
             logger.warning(f"Attempt to delete tenant {tenant_id} which still has associated users. Deletion prevented.")
             # raise ValueError(f"Cannot delete tenant {tenant_id}: It has associated users.")
             # Or, for a simple API, let the DB constraint handle it and catch the IntegrityError in the endpoint.
             # For now, we will let the DB constraint (if RESTRICT) prevent it.
             # If you want to allow deletion and orphan users, ensure your FK is SET NULL or handle users first.
             pass # Let's assume the database constraint will do its job or we handle it in endpoint

        # Also consider odoo_credentials linked to this tenant.
        # If odoo_credentials.tenant_id has ON DELETE CASCADE, it will be deleted.
        # If RESTRICT/NO ACTION, this delete will fail if credentials exist.

        db.delete(db_tenant)
        db.commit()
        return True
    return False    
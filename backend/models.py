# In backend/models.py
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

# Import Base from database.py (ensure absolute import)
from database import Base

# --- Add Tenant Model ---
class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True, nullable=False) # e.g., company name
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to Users (one tenant has many users)
    users = relationship("User", back_populates="tenant")
    # Relationship to Odoo Credentials (one tenant has one credential set)
    odoo_credential = relationship("OdooCredential", back_populates="tenant", uselist=False) # uselist=False for one-to-one


# --- Add OdooCredential Model ---
class OdooCredential(Base):
    __tablename__ = "odoo_credentials"

    id = Column(Integer, primary_key=True, index=True)
    odoo_base_url = Column(String, nullable=False)
    odoo_db_name = Column(String, nullable=False)
    odoo_username = Column(String, nullable=False)
    # Store the API key/password encrypted - use Text for potentially long encrypted string
    encrypted_odoo_api_key = Column(Text, nullable=False)
    # Could add connector_module_installed flag, etc.

    # Foreign Key to Tenant
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False) # unique=True for one-to-one

    # Relationship back to Tenant
    tenant = relationship("Tenant", back_populates="odoo_credential")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, index=True)
    job_title = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    

    # --- ADD Foreign Key and Relationship to Tenant ---
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False) # Make non-nullable
    tenant = relationship("Tenant", back_populates="users")
    # ------------------------------------------------

    odoo_employee_id = Column(Integer, nullable=True, index=True) # Allow NULL initially

    documents = relationship("Document", back_populates="owner")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    document_type = Column(String, nullable=False, index=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    file_path = Column(Text, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="documents")
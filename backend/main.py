import os
import shutil
import uuid
import logging
from pathlib import Path
from datetime import date, datetime, timedelta, timezone # Combined datetime imports
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Form, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse, FileResponse # Added FileResponse
from pydantic import BaseModel, EmailStr, HttpUrl
from sqlalchemy.orm import Session

import secrets # For generating secure tokens
from fastapi_mail import FastMail, MessageSchema, MessageType # For sending email
from email_config import conf as email_conf, FRONTEND_URL # Import your email config
from pydantic import EmailStr, BaseModel # Ensure EmailStr and BaseModel are available

# --- Add/Modify Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, Request # Add Request for IP
# ... (other existing imports) ...
from slowapi import Limiter, _rate_limit_exceeded_handler # Core slowapi
from slowapi.util import get_remote_address # To get client IP
from slowapi.errors import RateLimitExceeded # Exception for rate limit
from slowapi.middleware import SlowAPIMiddleware # Middleware

from sqlalchemy.exc import IntegrityError # Import for catching DB constraint errors


# Project-specific imports
import models
import crud
from database import engine, get_db # Removed SessionLocal as get_db provides session
from auth import (
    verify_password,
    create_access_token, create_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user,
    get_current_admin_user, # Ensure this is correctly imported from auth.py
    validate_refresh_token
)
from security import decrypt_data
from odoo_client import call_odoo_api, stream_odoo_api_file, call_odoo_api_multipart

# Setup logger
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute", "2000/hour"])

# --- FastAPI App Initialization ---
app = FastAPI(title="ESS SaaS Portal API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Create database tables on startup (for development convenience)
# Use Alembic for production migrations.
models.Base.metadata.create_all(bind=engine)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- File Upload Configuration ---
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DOCUMENTS_UPLOAD_DIR = UPLOAD_DIR / "documents"
DOCUMENTS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# Note: You might want a separate EXPENSE_RECEIPTS_UPLOAD_DIR if you were saving them

# --- Pydantic Models (Data Shapes for API Request/Response) ---

class UserProfile(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    department: Optional[str] = None
    is_admin: bool = False # Default to False, will be overridden by actual data
    odoo_employee_id: Optional[int] = None
    class Config: from_attributes = True

class LeaveType(BaseModel):
    id: int
    name: str
    class Config: from_attributes = True # If ever mapped from ORM

class LeaveRequestPayload(BaseModel):
    leave_type_id: int
    from_date: date
    to_date: date
    note: Optional[str] = None

class LeaveSubmitResponse(BaseModel):
    message: str
    odoo_leave_id: Optional[int] = None
    state: Optional[str] = None

class PendingLeavesCountResponse(BaseModel):
    employee_id: int
    pending_leave_count: int

class NextDayOffResponse(BaseModel):
    employee_id: Optional[int] = None
    next_day_off: Optional[date] = None
    leave_name: Optional[str] = None
    message: Optional[str] = None

class PayslipListItem(BaseModel):
    id: int
    month: str
    total: float
    status: str
    pdf_available: bool
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    class Config: from_attributes = True

class ExpenseSubmitResponse(BaseModel):
    message: str
    odoo_expense_id: Optional[int] = None
    state: Optional[str] = None

class DocumentListItem(BaseModel): # Pydantic model for frontend display
    id: int # This will now be the Odoo ir.attachment ID
    filename: str
    document_type: Optional[str] = None # Was description in Odoo
    upload_date: datetime # Odoo create_date is datetime, Pydantic handles string conversion
    mimetype: Optional[str] = None
    size: Optional[int] = None # Odoo's file_size

    class Config:
        from_attributes = True # Useful if mapping from an ORM model if one existed

class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentListItem

class LiveAttendanceStatusResponse(BaseModel):
    status: str
    last_action_time: Optional[datetime] = None
    message: Optional[str] = None
    class Config: from_attributes = True

class AttendanceLogItem(BaseModel):
    id: int
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    worked_hours: Optional[float] = None
    class Config: from_attributes = True

class TodaysAttendanceLogResponse(BaseModel):
    employee_id: Optional[int] = None
    attendance_log: List[AttendanceLogItem] = []
    message: Optional[str] = None

# Admin Pydantic Models
class TenantListItem(BaseModel):
    id: int
    name: str
    is_active: bool
    class Config: from_attributes = True

class TenantCreate(BaseModel):
    name: str
    is_active: Optional[bool] = True # Default to active on creation

class TenantStatusUpdate(BaseModel):
    is_active: bool    

class OdooConfigDisplay(BaseModel):
    tenant_id: int
    odoo_base_url: Optional[HttpUrl] = None
    odoo_db_name: Optional[str] = None
    odoo_username: Optional[str] = None
    class Config: from_attributes = True

class OdooConfigUpdate(BaseModel):
    odoo_base_url: HttpUrl
    odoo_db_name: str
    odoo_username: str
    odoo_api_key: str # Plain text for admin input, will be encrypted

class OdooConnectionTestResponse(BaseModel):
    status: str # "success" or "failure"
    message: str
    odoo_user_login: Optional[str] = None # If successful    

class RequestPasswordResetPayload(BaseModel):
    email: EmailStr

class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str # Add validation later (e.g., min length)

class GenericMessageResponse(BaseModel): # Simple response for success messages
    message: str

class TokenResponse(BaseModel): # For login response
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenPayload(BaseModel): # For refresh request body
    refresh_token: str


class AdminSaaSUserCreate(BaseModel):
    email: EmailStr
    password: str # Admin sets initial password
    full_name: Optional[str] = None
    tenant_id: int
    is_admin: Optional[bool] = False
    is_active: Optional[bool] = True
    odoo_employee_id: Optional[int] = None # Admin can optionally link at creation
    job_title: Optional[str] = None
    phone: Optional[str] = None


class AdminSaaSUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None # For admin to reset password
    tenant_id: Optional[int] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    odoo_employee_id: Optional[int] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None


# Pydantic model for displaying users in admin list (might be similar to UserProfile)
class AdminUserListItem(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_admin: bool
    is_active: bool
    tenant_id: int
    odoo_employee_id: Optional[int] = None
    # Could add tenant_name by joining in CRUD or post-processing
    class Config: from_attributes = True

class OdooEmployeeSearchResultItem(BaseModel):
    id: int
    name: str
    work_email: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None

class OdooEmployeeSearchResultItem(BaseModel):
    id: int
    name: Optional[str] = None # Make optional if Odoo might return null
    work_email: Optional[EmailStr] = None # EmailStr will validate or fail if not email format
    job_title: Optional[str] = None
    department: Optional[str] = None
    work_phone: Optional[str] = None # Add this
    mobile_phone: Optional[str] = None # Add this

    # Pydantic V2: from_attributes=True; V1: orm_mode=True
    class Config:
        from_attributes = True

class OdooAttachmentResponseItem(BaseModel): # More specific for Odoo attachment details
    attachment_id: int
    filename: str
    document_type: str # This was description in Odoo attachment
    employee_id: int

class OdooDocumentUploadResponse(BaseModel):
    message: str
    document: Optional[OdooAttachmentResponseItem] = None # Make document part optional for flexibility

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {"message": "ESS SaaS Backend is running!"}

@app.post("/api/v1/login", response_model=TokenResponse) # Update response model
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    logger.info(f"Login attempt for username (email): {form_data.username}")
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Login failed: Incorrect email or password for {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        logger.warning(f"Login failed: User account {form_data.username} is inactive.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    token_data = {"sub": user.email, "is_admin": user.is_admin}
    
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data={"sub": user.email}) # Refresh token only needs 'sub'

    logger.info(f"Login successful for user: {user.email}, Admin: {user.is_admin}")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
        # token_type is defaulted in Pydantic model
    )

@app.get("/api/v1/users/me", response_model=UserProfile)
async def read_users_me(
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    user_email = current_user.get("user_identifier")
    db_user = crud.get_user_by_email(db, email=user_email)
    if not db_user:
        # This should ideally not happen if token is valid and user exists from login
        logger.error(f"User {user_email} found in token but not in SaaS DB.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in SaaS DB.")
    if not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is inactive.")

    # Prepare base profile data from SaaS DB
    profile_args = {
        "email": db_user.email,
        "full_name": db_user.full_name,
        "job_title": db_user.job_title, # From SaaS User model, might be overridden by Odoo
        "phone": db_user.phone,       # From SaaS User model, might be overridden by Odoo
        "is_admin": db_user.is_admin,
        "odoo_employee_id": db_user.odoo_employee_id
    }

    if not db_user.odoo_employee_id:
        logger.warning(f"User {user_email} has no Odoo Employee ID mapping. Returning basic SaaS info.")
        return UserProfile(**profile_args) # Pass all collected args

    # Fetch Odoo Credentials & Decrypt Key (common pattern)
    odoo_creds = crud.get_odoo_credential_by_tenant(db, tenant_id=db_user.tenant_id)
    if not odoo_creds:
        logger.error(f"Odoo credentials not found for tenant ID: {db_user.tenant_id} (User: {user_email})")
        # Return basic SaaS info if Odoo connection can't be established
        return UserProfile(**profile_args, address=None, department=None) # Explicitly None for Odoo fields

    decrypted_api_key = decrypt_data(odoo_creds.encrypted_odoo_api_key)
    if not decrypted_api_key:
        logger.error(f"Failed to decrypt Odoo API key for tenant ID: {db_user.tenant_id} (User: {user_email})")
        return UserProfile(**profile_args, address=None, department=None)

    odoo_endpoint = f"/ess/api/employee/{db_user.odoo_employee_id}"
    try:
        odoo_employee_data = await call_odoo_api(
            base_url=odoo_creds.odoo_base_url,
            endpoint=odoo_endpoint,
            method="GET",
            api_key=decrypted_api_key,
        )
        # Merge Odoo data with SaaS data, Odoo data takes precedence for shared fields
        profile_args.update({
            "full_name": odoo_employee_data.get('name', profile_args["full_name"]),
            "job_title": odoo_employee_data.get('job_title', profile_args["job_title"]),
            "phone": odoo_employee_data.get('work_phone') or odoo_employee_data.get('mobile_phone') or profile_args["phone"],
            "address": odoo_employee_data.get('address'),
            "department": odoo_employee_data.get('department'),
        })
        return UserProfile(**profile_args)

    except HTTPException as e:
        logger.warning(f"HTTP error fetching Odoo profile for {user_email} (Odoo Emp ID: {db_user.odoo_employee_id}): {e.detail}. Returning basic SaaS info.")
        # Fallback to SaaS data if Odoo call fails but was expected
        return UserProfile(**profile_args, address=None, department=None)
    except Exception as e:
        logger.exception(f"Unexpected error fetching Odoo profile for {user_email}. Returning basic SaaS info.")
        return UserProfile(**profile_args, address=None, department=None)

# --- Standard Helper for Odoo Calls ---
async def _perform_odoo_call(
    db_user: models.User, # Pass the SQLAlchemy User object
    db: Session,
    endpoint_template: str, # e.g., "/ess/api/some-endpoint/{employee_id}"
    method: str = "GET",
    payload: Optional[dict] = None,
    is_file_download: bool = False,
    multipart_data: Optional[dict] = None,
    multipart_files: Optional[list] = None
):
    """Helper function to make calls to Odoo, centralizing credential logic."""
    if not db_user.odoo_employee_id and "{employee_id}" in endpoint_template:
        logger.warning(f"User {db_user.email} has no Odoo Employee ID mapping for endpoint {endpoint_template}.")
        # Depending on context, might raise HTTPException or return default
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not linked to HR system for this operation.")

    odoo_creds = crud.get_odoo_credential_by_tenant(db, tenant_id=db_user.tenant_id)
    if not odoo_creds:
        logger.error(f"Odoo credentials not found for tenant {db_user.tenant_id} (User: {db_user.email})")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Odoo connection not configured.")

    decrypted_api_key = decrypt_data(odoo_creds.encrypted_odoo_api_key)
    if not decrypted_api_key:
        logger.error(f"Failed to decrypt Odoo API key for tenant {db_user.tenant_id} (User: {db_user.email})")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Security configuration error.")

    # Construct final endpoint if it depends on employee_id
    final_endpoint = endpoint_template
    if "{employee_id}" in endpoint_template:
        if not db_user.odoo_employee_id: # Should have been caught earlier but double check
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Odoo Employee ID for Odoo API call.")
        final_endpoint = endpoint_template.format(employee_id=db_user.odoo_employee_id)
    elif "{payslip_id}" in endpoint_template and payload and "payslip_id" in payload: # Specific case for payslip download
        final_endpoint = endpoint_template.format(payslip_id=payload["payslip_id"])


    logger.info(f"Calling Odoo for {db_user.email}: {method} {final_endpoint}")
    try:
        if is_file_download:
            return await stream_odoo_api_file(
                base_url=odoo_creds.odoo_base_url,
                endpoint=final_endpoint,
                api_key=decrypted_api_key,
            )
        elif multipart_data is not None or multipart_files is not None:
            return await call_odoo_api_multipart(
                base_url=odoo_creds.odoo_base_url,
                endpoint=final_endpoint,
                api_key=decrypted_api_key,
                data=multipart_data,
                files=multipart_files,
            )
        else:
            return await call_odoo_api(
                base_url=odoo_creds.odoo_base_url,
                endpoint=final_endpoint,
                method=method,
                api_key=decrypted_api_key,
                payload=payload,
            )
    except HTTPException as e_http: # Re-raise HTTPExceptions from odoo_client
        logger.error(f"Odoo call failed for {db_user.email} to {final_endpoint}: {e_http.status_code} - {e_http.detail}")
        raise e_http
    except Exception as e_gen: # Catch any other unexpected error
        logger.exception(f"Unexpected error during Odoo call for {db_user.email} to {final_endpoint}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal error communicating with HR system for endpoint {final_endpoint}.")

# --- Refactored Endpoints using _perform_odoo_call ---

@app.get("/api/v1/leave-types", response_model=List[LeaveType])
async def get_leave_types(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    # ... (user validation as in read_users_me)
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    return await _perform_odoo_call(db_user, db, "/ess/api/leave-types")

@app.post("/api/v1/leave-request", response_model=LeaveSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_leave_request(
    payload: LeaveRequestPayload, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if not db_user.odoo_employee_id: raise HTTPException(status_code=400, detail="User not linked to HR for leave request.")

    odoo_payload = {
        "employee_id": db_user.odoo_employee_id,
        "leave_type_id": payload.leave_type_id,
        "from_date": payload.from_date.isoformat(),
        "to_date": payload.to_date.isoformat(),
        "note": payload.note,
    }
    return await _perform_odoo_call(db_user, db, "/ess/api/leave", method="POST", payload=odoo_payload)

@app.get("/api/v1/dashboard/pending-leaves-count", response_model=PendingLeavesCountResponse)
async def get_dashboard_pending_leaves(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    try:
        return await _perform_odoo_call(db_user, db, "/ess/api/leaves/pending-count/{employee_id}")
    except HTTPException as e: # Graceful fallback for dashboard widget
         if e.status_code in [400, 403, 404, 503, 500]: # If user not linked, or Odoo issue
             logger.warning(f"Dashboard pending leaves: Odoo call failed for {db_user.email} ({e.status_code}). Returning 0.")
             return PendingLeavesCountResponse(employee_id=db_user.odoo_employee_id or 0, pending_leave_count=0)
         raise e


@app.get("/api/v1/dashboard/next-day-off", response_model=NextDayOffResponse)
async def get_dashboard_next_day_off(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    try:
        odoo_response = await _perform_odoo_call(db_user, db, "/ess/api/leaves/next-off/{employee_id}")
        if odoo_response.get("next_day_off"):
            return NextDayOffResponse(**odoo_response)
        else:
            return NextDayOffResponse(employee_id=odoo_response.get("employee_id"), message="No upcoming approved leave found.")
    except HTTPException as e:
         if e.status_code in [400, 403, 404, 503, 500]:
             logger.warning(f"Dashboard next day off: Odoo call failed for {db_user.email} ({e.status_code}). Returning message.")
             return NextDayOffResponse(employee_id=db_user.odoo_employee_id or 0, message="Could not retrieve leave information.")
         raise e


@app.get("/api/v1/payslips", response_model=List[PayslipListItem])
async def get_payslip_list(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if not db_user.odoo_employee_id: return [] # Return empty list if not linked
    return await _perform_odoo_call(db_user, db, "/ess/api/payslips/{employee_id}")

@app.get("/api/v1/payslip/{payslip_id}/download")
async def download_payslip_pdf(payslip_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    # Pass payslip_id in payload for endpoint formatting in helper
    return await _perform_odoo_call(db_user, db, "/ess/api/payslip/{payslip_id}/download", is_file_download=True, payload={"payslip_id": payslip_id})


@app.post("/api/v1/expenses", response_model=ExpenseSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_expense(
    description: str = Form(...), amount: float = Form(...), date: date = Form(...),
    receipt: UploadFile = File(...), current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if not db_user.odoo_employee_id: raise HTTPException(status_code=400, detail="User not linked to HR for expense submission.")

    try:
        receipt_content_bytes = await receipt.read()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not read uploaded receipt file.")
    finally:
        await receipt.close()

    form_data_for_odoo = {
        "employee_id": str(db_user.odoo_employee_id),
        "description": description, "amount": str(amount), "date": date.isoformat(),
    }
    files_for_odoo = [('receipt', (receipt.filename, receipt_content_bytes, receipt.content_type))]

    return await _perform_odoo_call(
        db_user, db, "/ess/api/expenses",
        multipart_data=form_data_for_odoo, multipart_files=files_for_odoo
    )

# --- GET Document List (Refactored to fetch from Odoo) ---
@app.get("/api/v1/documents", response_model=List[DocumentListItem])
async def list_user_documents_from_odoo( # Renamed function for clarity
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_email = current_user.get("user_identifier")
    db_user = crud.get_user_by_email(db, email=user_email)
    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized or inactive.")

    odoo_emp_id = db_user.odoo_employee_id
    if not odoo_emp_id:
        logger.warning(f"User {user_email} cannot list documents from Odoo: No Odoo Employee ID mapping.")
        return [] # Return empty list if not linked

    logger.info(f"User {user_email} (Odoo Emp ID: {odoo_emp_id}) requesting document list from Odoo.")

    # Fetch Odoo Credentials & Decrypt Key (Use the _perform_odoo_call helper)
    try:
        odoo_documents_data = await _perform_odoo_call(
            db_user=db_user,
            db=db,
            endpoint_template="/ess/api/employee/{employee_id}/documents", # Uses employee_id from db_user
            method="GET"
        )
        # Odoo connector returns a list of document metadata.
        # Pydantic's response_model will validate if list items match DocumentListItem.
        return odoo_documents_data

    except HTTPException as e:
         logger.error(f"Error listing documents from Odoo for user {user_email}: Status={e.status_code}, Detail={e.detail}")
         # If Odoo returns 403/404, or connection issue, return empty list gracefully for UI
         if e.status_code != status.HTTP_401_UNAUTHORIZED: # Don't mask auth issues
             return []
         raise e # Re-raise critical errors like 401 or unexpected 500s from helper
    except Exception as e:
         logger.exception(f"Unexpected error listing documents from Odoo for user {user_email}")
         return [] # Graceful fallback

@app.post("/api/v1/documents", response_model=OdooDocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_to_odoo( # Renamed function for clarity
    document_type: str = Form(...), # From frontend form
    file: UploadFile = File(...),    # From frontend form
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_email = current_user.get("user_identifier")
    db_user = crud.get_user_by_email(db, email=user_email)
    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized or inactive.")

    odoo_emp_id = db_user.odoo_employee_id
    if not odoo_emp_id:
        logger.warning(f"User {user_email} cannot upload document to Odoo: No Odoo Employee ID mapping.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot upload document: User profile not linked to HR system.")

    logger.info(f"User {user_email} (Odoo Emp ID: {odoo_emp_id}) uploading document '{file.filename}' of type '{document_type}' to Odoo.")

    # Fetch Odoo Credentials & Decrypt Key (Can use the _perform_odoo_call helper structure later if desired)
    odoo_creds = crud.get_odoo_credential_by_tenant(db, tenant_id=db_user.tenant_id)
    if not odoo_creds:
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Odoo connection not configured.")
    decrypted_api_key = decrypt_data(odoo_creds.encrypted_odoo_api_key)
    if not decrypted_api_key:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Security configuration error.")

    # Read file content
    try:
        file_content_bytes = await file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded document file '{file.filename}': {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not read uploaded document file.")
    finally:
        await file.close()

    # Prepare multipart data for Odoo connector
    form_data_for_odoo = {
        "document_type": document_type,
        # employee_id is in the URL for the Odoo connector endpoint
    }
    files_for_odoo = [
        ('file', (file.filename, file_content_bytes, file.content_type)) # 'file' is the expected field name in Odoo connector
    ]

    odoo_endpoint = f"/ess/api/employee/{odoo_emp_id}/document"
    try:
        odoo_response = await call_odoo_api_multipart(
            base_url=odoo_creds.odoo_base_url,
            endpoint=odoo_endpoint,
            api_key=decrypted_api_key,
            data=form_data_for_odoo, # Form fields
            files=files_for_odoo      # File part
        )
        # Odoo connector response:
        # {'message': '...', 'attachment_id': ..., 'filename': ..., 'document_type': ..., 'employee_id': ...}
        logger.info(f"Odoo response for document upload: {odoo_response}")
        return OdooDocumentUploadResponse(
            message=odoo_response.get("message", "Document processed by Odoo."),
            document=OdooAttachmentResponseItem(**odoo_response) if odoo_response.get("attachment_id") else None
        )

    except HTTPException as e:
         logger.error(f"Error uploading document to Odoo for user {user_email}: Status={e.status_code}, Detail={e.detail}")
         raise e # Re-raise Odoo/connection errors passed from call_odoo_api_multipart
    except Exception as e:
         logger.exception(f"Unexpected error uploading document to Odoo for user {user_email}")
         raise HTTPException(status_code=500, detail="Failed to upload document to HR system due to an internal error.")

# --- GET Document Download (Refactored to download from Odoo) ---
# The {document_id} in the path will now be the Odoo ir.attachment ID (integer)
@app.get("/api/v1/document/{document_id}/download")
async def download_document_from_odoo( # Renamed function for clarity
    document_id: int, # Changed from str to int
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_email = current_user.get("user_identifier")
    db_user = crud.get_user_by_email(db, email=user_email)
    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized or inactive.")

    # No direct odoo_emp_id check here, as the Odoo connector's download endpoint
    # will verify if the attachment belongs to an employee the API user can access.
    logger.info(f"User {user_email} requesting download for Odoo document (attachment ID): {document_id}")

    # Fetch Odoo Credentials & Decrypt Key (Use the _perform_odoo_call helper)
    try:
        # The endpoint template needs the document_id (attachment_id)
        # The _perform_odoo_call helper was designed for {employee_id} substitution.
        # We need to call stream_odoo_api_file directly here or adapt the helper.
        # Let's call stream_odoo_api_file directly for more control.

        odoo_creds = crud.get_odoo_credential_by_tenant(db, tenant_id=db_user.tenant_id)
        if not odoo_creds:
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Odoo connection not configured.")
        decrypted_api_key = decrypt_data(odoo_creds.encrypted_odoo_api_key)
        if not decrypted_api_key:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Security configuration error.")

        odoo_endpoint = f"/ess/api/attachment/{document_id}/download"

        streaming_response = await stream_odoo_api_file(
            base_url=odoo_creds.odoo_base_url,
            endpoint=odoo_endpoint,
            api_key=decrypted_api_key
        )
        return streaming_response

    except HTTPException as e:
         logger.error(f"Error downloading document {document_id} from Odoo for user {user_email}: Status={e.status_code}, Detail={e.detail}")
         raise e
    except Exception as e:
         logger.exception(f"Unexpected error downloading document {document_id} from Odoo for user {user_email}")
         raise HTTPException(status_code=500, detail="Failed to download document from HR system due to an internal error.")

# --- Refactored FastAPI Attendance Endpoints ---
@app.get("/api/v1/attendance/status", response_model=LiveAttendanceStatusResponse)
async def get_live_attendance_status(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if not db_user.odoo_employee_id: return LiveAttendanceStatusResponse(status="unknown", message="Not linked to HR system.")
    try:
        return await _perform_odoo_call(db_user, db, "/ess/api/attendance/status/{employee_id}")
    except HTTPException as e:
         if e.status_code in [403, 404, 503, 500]:
             return LiveAttendanceStatusResponse(status="error", message="Could not retrieve status from HR system.")
         raise e

@app.post("/api/v1/attendance/check-in", response_model=LiveAttendanceStatusResponse)
async def fastapi_attendance_check_in(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if not db_user.odoo_employee_id: raise HTTPException(status_code=400, detail="User not linked to HR for check-in.")
    payload_for_odoo = {"employee_id": str(db_user.odoo_employee_id)}
    return await _perform_odoo_call(db_user, db, "/ess/api/attendance/check-in", multipart_data=payload_for_odoo) # Sent as form data

@app.post("/api/v1/attendance/check-out", response_model=LiveAttendanceStatusResponse)
async def fastapi_attendance_check_out(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if not db_user.odoo_employee_id: raise HTTPException(status_code=400, detail="User not linked to HR for check-out.")
    payload_for_odoo = {"employee_id": str(db_user.odoo_employee_id)}
    return await _perform_odoo_call(db_user, db, "/ess/api/attendance/check-out", multipart_data=payload_for_odoo) # Sent as form data

@app.get("/api/v1/attendance/today-log", response_model=TodaysAttendanceLogResponse)
async def get_fastapi_todays_attendance_log(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=current_user.get("user_identifier"))
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if not db_user.odoo_employee_id: return TodaysAttendanceLogResponse(message="Not linked to HR system.")
    try:
        odoo_log_data = await _perform_odoo_call(db_user, db, "/ess/api/attendance/today/{employee_id}")
        return TodaysAttendanceLogResponse(employee_id=db_user.odoo_employee_id, attendance_log=odoo_log_data)
    except HTTPException as e:
         if e.status_code in [403, 404, 503, 500]:
             return TodaysAttendanceLogResponse(employee_id=db_user.odoo_employee_id, message="Could not retrieve attendance log.")
         raise e

# --- ADMIN Endpoints ---
@app.get("/api/v1/admin/tenants", response_model=List[TenantListItem])
async def admin_get_tenants(
    skip: int = 0, limit: int = 100,
    current_admin: dict = Depends(get_current_admin_user), db: Session = Depends(get_db)
):
    return crud.get_tenants(db, skip=skip, limit=limit)

@app.get("/api/v1/admin/tenant/{tenant_id}/odoo-config", response_model=Optional[OdooConfigDisplay])
async def admin_get_tenant_odoo_config(
    tenant_id: int, current_admin: dict = Depends(get_current_admin_user), db: Session = Depends(get_db)
):
    tenant = crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant: raise HTTPException(status_code=404, detail="Tenant not found.")
    odoo_config_orm = crud.get_odoo_credential_by_tenant(db, tenant_id=tenant_id)
    if not odoo_config_orm:
        return OdooConfigDisplay(tenant_id=tenant_id) # Return with None for optional fields
    return odoo_config_orm # Pydantic handles conversion

@app.put("/api/v1/admin/tenant/{tenant_id}/odoo-config", response_model=OdooConfigDisplay)
async def admin_update_tenant_odoo_config(
    tenant_id: int, config_data: OdooConfigUpdate,
    current_admin: dict = Depends(get_current_admin_user), db: Session = Depends(get_db)
):
    tenant = crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant: raise HTTPException(status_code=404, detail="Tenant not found.")
    updated_credential = crud.create_or_update_odoo_credential(
        db=db, tenant_id=tenant_id, odoo_base_url=str(config_data.odoo_base_url),
        odoo_db_name=config_data.odoo_db_name, odoo_username=config_data.odoo_username,
        plain_api_key=config_data.odoo_api_key
    )
    if not updated_credential: raise HTTPException(status_code=500, detail="Failed to save Odoo configuration.")
    # Return display model (without key)
    return OdooConfigDisplay(
        tenant_id=updated_credential.tenant_id, odoo_base_url=updated_credential.odoo_base_url,
        odoo_db_name=updated_credential.odoo_db_name, odoo_username=updated_credential.odoo_username
    )


# --- NEW: POST /api/v1/admin/tenants ---
@app.post("/api/v1/admin/tenants", response_model=TenantListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_tenant(
    tenant_data: TenantCreate,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} creating new tenant: {tenant_data.name}")
    db_tenant = crud.get_tenant_by_name(db, name=tenant_data.name)
    if db_tenant:
        raise HTTPException(status_code=400, detail=f"Tenant with name '{tenant_data.name}' already exists.")
    
    new_tenant = crud.create_tenant(db=db, name=tenant_data.name, is_active=tenant_data.is_active)
    return new_tenant


# GET /api/v1/admin/tenant/{tenant_id}/odoo-config (already exists, no change needed)
# async def admin_get_tenant_odoo_config(...)

# PUT /api/v1/admin/tenant/{tenant_id}/odoo-config (already exists, no change needed)
# async def admin_update_tenant_odoo_config(...)


@app.delete("/api/v1/admin/tenant/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_tenant(
    tenant_id: int,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} attempting to delete tenant ID: {tenant_id}")

    # Optional: Add checks like preventing deletion of a "default" or "system" tenant if you have one.
    # if tenant_id == 1: # Example: prevent deleting tenant with ID 1
    #     raise HTTPException(status_code=403, detail="This tenant cannot be deleted.")

    try:
        deleted = crud.delete_tenant(db=db, tenant_id=tenant_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Tenant not found for deletion.")
    except IntegrityError as e: # Catch foreign key constraint violations from DB
        logger.error(f"Integrity error deleting tenant {tenant_id}: {e}")
        # A more specific message could be crafted based on parsing e.orig (psycopg2 error)
        raise HTTPException(status_code=409, detail="Cannot delete tenant: It may have associated users or configurations. Please reassign or delete them first.")
    except Exception as e: # Catch other potential errors from CRUD
        logger.exception(f"Error during tenant deletion for ID {tenant_id}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while deleting the tenant.")

    logger.info(f"Tenant ID: {tenant_id} deleted successfully by admin {current_admin.get('user_identifier')}.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- NEW: GET /api/v1/admin/tenant/{tenant_id} (Optional - for single tenant view if needed) ---
@app.get("/api/v1/admin/tenant/{tenant_id}", response_model=TenantListItem)
async def admin_get_tenant_details(
    tenant_id: int,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} fetching details for tenant ID: {tenant_id}")
    db_tenant = crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return db_tenant


# --- NEW: PUT /api/v1/admin/tenant/{tenant_id}/status ---
@app.put("/api/v1/admin/tenant/{tenant_id}/status", response_model=TenantListItem)
async def admin_update_tenant_status(
    tenant_id: int,
    status_data: TenantStatusUpdate,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} updating status for tenant ID: {tenant_id} to active={status_data.is_active}")
    updated_tenant = crud.update_tenant_status(db=db, tenant_id=tenant_id, is_active=status_data.is_active)
    if not updated_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return updated_tenant    


# --- NEW: Test Odoo Connection Endpoint ---
@app.post("/api/v1/admin/tenant/{tenant_id}/test-odoo-connection", response_model=OdooConnectionTestResponse)
async def admin_test_odoo_connection(
    tenant_id: int,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} testing Odoo connection for tenant ID: {tenant_id}")
    tenant = crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    odoo_creds = crud.get_odoo_credential_by_tenant(db, tenant_id=tenant_id)
    if not odoo_creds:
        logger.warning(f"Cannot test Odoo connection for tenant {tenant_id}: No credentials configured.")
        return OdooConnectionTestResponse(status="failure", message="Odoo credentials are not configured for this tenant.")

    decrypted_api_key = decrypt_data(odoo_creds.encrypted_odoo_api_key)
    if not decrypted_api_key:
        logger.error(f"Failed to decrypt Odoo API key for tenant {tenant_id} during connection test.")
        return OdooConnectionTestResponse(status="failure", message="Security configuration error: Could not decrypt API key.")

    odoo_endpoint = "/ess/api/auth-test"
    try:
        odoo_response_data = await call_odoo_api(
            base_url=odoo_creds.odoo_base_url,
            endpoint=odoo_endpoint,
            method="GET",
            api_key=decrypted_api_key
        )
        # Odoo /auth-test returns something like:
        # {"status": "success", "message": "Authentication successful.", "authenticated_user_login": "admin", ...}
        if odoo_response_data.get("status") == "success":
            return OdooConnectionTestResponse(
                status="success",
                message=f"Connection successful. Authenticated as Odoo user: {odoo_response_data.get('authenticated_user_login', 'N/A')}",
                odoo_user_login=odoo_response_data.get('authenticated_user_login')
            )
        else: # Should not happen if Odoo endpoint is structured correctly
            return OdooConnectionTestResponse(status="failure", message="Odoo auth-test endpoint returned unexpected success format.")

    except HTTPException as e: # Errors from call_odoo_api (Odoo errors, connection issues, timeouts)
        logger.warning(f"Odoo connection test failed for tenant {tenant_id}: Status={e.status_code}, Detail={e.detail}")
        return OdooConnectionTestResponse(status="failure", message=f"Connection failed: {e.detail}")
    except Exception as e:
        logger.exception(f"Unexpected error during Odoo connection test for tenant {tenant_id}")
        return OdooConnectionTestResponse(status="failure", message="An unexpected error occurred during connection test.")


# --- Password Reset Endpoints ---

@app.post("/api/v1/auth/request-password-reset", response_model=GenericMessageResponse)
async def request_password_reset(
    payload: RequestPasswordResetPayload,
    db: Session = Depends(get_db)
):
    logger.info(f"Password reset requested for email: {payload.email}")
    user = crud.get_user_by_email(db, email=payload.email)

    if user and user.is_active:
        # Generate a secure, URL-safe token
        reset_token = secrets.token_urlsafe(32)
        # Store the token (or its hash) and expiry in the database for this user
        crud.set_password_reset_token(db, user=user, token=reset_token, expires_in_minutes=60) # Token valid for 1 hour

        # Construct the reset link
        reset_link = f"{FRONTEND_URL.rstrip('/')}/reset-password?token={reset_token}"
        logger.info(f"Generated password reset link for {payload.email}: {reset_link}") # Log link for dev/testing

        # Prepare and send the email
        email_subject = "Password Reset Request - ESS Portal"
        email_body_html = f"""
        <p>Hi {user.full_name or user.email},</p>
        <p>You requested a password reset for your ESS Portal account.</p>
        <p>Please click the link below to set a new password. This link is valid for 60 minutes:</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>If you did not request this, please ignore this email.</p>
        <p>Thanks,<br/>The ESS Portal Team</p>
        """
        message = MessageSchema(
            subject=email_subject,
            recipients=[payload.email], # Send to user's email
            body=email_body_html,
            subtype=MessageType.html
        )
        try:
            fm = FastMail(email_conf)
            await fm.send_message(message)
            logger.info(f"Password reset email sent successfully to {payload.email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {payload.email}: {e}", exc_info=True)
            # Don't expose detailed error to user, but crucial to log
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Could not send password reset email. Please try again later.")

    else:
        # If user not found or inactive, still return a generic success message
        # This prevents email enumeration (attackers guessing valid emails)
        logger.warning(f"Password reset requested for non-existent or inactive email: {payload.email}")

    # Always return a generic message to avoid revealing if an email is registered or not
    return GenericMessageResponse(message="If an account with that email exists, a password reset link has been sent.")


@app.post("/api/v1/auth/reset-password", response_model=GenericMessageResponse)
async def reset_password(
    payload: ResetPasswordPayload,
    db: Session = Depends(get_db)
):
    logger.info(f"Attempting password reset with token: {payload.token[:10]}...") # Log partial token

    # Validate the token and find the user
    user = crud.get_user_by_password_reset_token(db, token=payload.token)

    if not user:
        logger.warning(f"Invalid or expired password reset token used: {payload.token[:10]}...")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid or expired password reset token.")

    # TODO: Add password complexity validation for payload.new_password here if desired
    # e.g., if len(payload.new_password) < 8: raise HTTPException(...)

    # Update the user's password
    crud.update_user_password(db, user=user, new_password=payload.new_password)
    logger.info(f"Password successfully reset for user: {user.email}")

    # Invalidate the reset token after use
    crud.clear_password_reset_token(db, user=user)
    logger.info(f"Password reset token cleared for user: {user.email}")

    # Optionally, send a confirmation email that the password was changed
    # ... (email sending logic similar to above) ...

    return GenericMessageResponse(message="Your password has been successfully reset. You can now log in with your new password.") 


# CORS Configuration (Add SLOWAPI MIDDLEWARE BEFORE THIS)
app.add_middleware(SlowAPIMiddleware) # <<<<<<<<<<< ADDED MIDDLEWARE HERE
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic Models ---
# ... (all your Pydantic models) ...

# --- API Endpoints ---
# All your endpoints will now be subject to the default rate limits
# You might need to add `request: Request` as a parameter to endpoints if you
# were using @limiter.limit("...") decorators directly on them, but with
# global middleware and key_func=get_remote_address, it should work without modifying
# existing endpoint signatures unless slowapi's middleware has specific needs not documented here.
# Let's test without modifying signatures first.

@app.get("/")
# If you want to exempt a route from global limits or apply different one:
# @limiter.exempt # or @limiter.limit("10/second")
async def read_root(request: Request): # Add request: Request for limiter context
    return {"message": "ESS SaaS Backend is running!"}   


# --- NEW: Refresh Token Endpoint ---
@app.post("/api/v1/auth/refresh-token", response_model=TokenResponse) # Returns new set of tokens
async def refresh_access_token(
    payload: RefreshTokenPayload, # Expects {"refresh_token": "..."}
    # No db session needed if not storing refresh tokens or checking user against db here
):
    logger.info(f"Refresh token attempt with token: {payload.refresh_token[:10]}...")
    
    refresh_payload = validate_refresh_token(payload.refresh_token)
    if not refresh_payload:
        logger.warning("Invalid or expired refresh token provided.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_email = refresh_payload.get("sub")
    # is_admin_from_refresh = refresh_payload.get("is_admin", False) # Could get this if stored

    # Here, you might want to re-fetch user from DB to ensure they are still active
    # and to get the latest 'is_admin' status, rather than relying on potentially stale
    # 'is_admin' from an old refresh token's original data.
    # For simplicity now, we'll re-use the 'sub' directly.
    # If you stored more data (like is_admin) in the refresh token payload, you could use it.
    # For now, access tokens get 'is_admin' from the fresh DB lookup on login.
    # A refresh should ideally grant a token with up-to-date permissions.
    # Let's assume for now that if a refresh token is valid for a user,
    # we just need to issue a new access token for that user.
    # The `is_admin` for the *new access token* will be based on the original login.
    # To have up-to-date `is_admin`, the `create_access_token` would need to know it.
    # We'll simplify and assume the original `is_admin` status from the refresh token's
    # original data payload is sufficient for now, or that only 'sub' is in refresh token payload.

    # Create new tokens. New access token needs 'sub' and 'is_admin'.
    # The refresh_payload contains what was used to create the refresh token.
    # If it only had 'sub', then new_access_token_data would need is_admin from DB.
    # For simplicity, let's assume refresh_payload (from refresh token) has the necessary data
    # or we're okay if the refreshed access token doesn't have is_admin.
    # A better approach for refreshed access_token: fetch user from DB using 'sub'
    # and get current 'is_admin' status.

    # For now, let's assume the original refresh token payload had what's needed for new access token
    # OR that the access token generated by refresh doesn't need all the same claims as one from login.
    # A common pattern is the refresh token only has 'sub'.
    # Then, to create a new access token, you MUST fetch user from DB to get their current roles.
    # Let's stick to just 'sub' from refresh token to create new access token for now
    # and access token will also just have 'sub'. The 'is_admin' will be re-evaluated
    # by get_current_admin_user if it re-fetches user based on 'sub'.
    
    # For new access token, we only strictly need 'sub'.
    # The 'is_admin' status is checked by get_current_admin_user dependency,
    # which decodes the access token. So the access token MUST contain is_admin.
    # So, the refresh_payload *must* have 'is_admin' or we must look it up.
    # Let's assume create_refresh_token stored it initially.
    
    new_token_data = {
        "sub": user_email,
        "is_admin": refresh_payload.get("is_admin", False) # Get is_admin from refresh token payload
    }

    new_access_token = create_access_token(data=new_token_data)
    # Optional: Implement refresh token rotation (issue a new refresh token as well)
    new_refresh_token = create_refresh_token(data={"sub": user_email}) # Only needs 'sub'

    logger.info(f"Access token refreshed for user: {user_email}")
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token # Send new refresh token (rotation)
    )            



# --- ADMIN SAAS USER MANAGEMENT Endpoints ---

@app.get("/api/v1/admin/users", response_model=List[AdminUserListItem])
async def admin_get_all_users(
    skip: int = 0, limit: int = 100,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} fetching all SaaS users.")
    users = crud.get_all_users(db, skip=skip, limit=limit)
    return users # Pydantic will map from User ORM model


@app.post("/api/v1/admin/users", response_model=AdminUserListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_saas_user(
    user_data: AdminSaaSUserCreate,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} creating SaaS user: {user_data.email}")
    existing_user = crud.get_user_by_email(db, email=user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered by another SaaS user.")
    
    tenant = crud.get_tenant_by_id(db, tenant_id=user_data.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant with ID {user_data.tenant_id} not found.")

    # Password validation (example)
    if len(user_data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    new_user = crud.create_saas_user(db=db, user_data=user_data.model_dump()) # Use model_dump() for Pydantic v2+
    return new_user


@app.get("/api/v1/admin/user/{user_id}", response_model=AdminUserListItem)
async def admin_get_saas_user_details(
    user_id: int,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} fetching details for SaaS user ID: {user_id}")
    db_user = crud.get_user_by_id(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="SaaS User not found.")
    return db_user


@app.put("/api/v1/admin/user/{user_id}", response_model=AdminUserListItem)
async def admin_update_saas_user(
    user_id: int,
    user_update: AdminSaaSUserUpdate,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} updating SaaS user ID: {user_id}")
    db_user = crud.get_user_by_id(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="SaaS User not found to update.")

    # Prevent admin from changing their own admin status via this specific endpoint
    # if db_user.email == current_admin.get("user_identifier") and user_update.is_admin is False:
    #     raise HTTPException(status_code=403, detail="Administrators cannot revoke their own admin status via this endpoint.")

    # Check if new email is already taken by another user
    if user_update.email and user_update.email != db_user.email:
        existing_email_user = crud.get_user_by_email(db, email=user_update.email)
        if existing_email_user:
            raise HTTPException(status_code=400, detail="New email is already registered by another user.")
    
    # Ensure tenant exists if tenant_id is being updated
    if user_update.tenant_id is not None: # Check if tenant_id is part of the update
        tenant = crud.get_tenant_by_id(db, tenant_id=user_update.tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Target tenant with ID {user_update.tenant_id} not found.")

    # Use model_dump(exclude_unset=True) to only get fields that were actually sent in the PUT request
    update_data_dict = user_update.model_dump(exclude_unset=True)

    # Password validation for update
    if "password" in update_data_dict and update_data_dict["password"]:
        if len(update_data_dict["password"]) < 8:
             raise HTTPException(status_code=400, detail="New password must be at least 8 characters long.")


    updated_user = crud.update_saas_user(db=db, user_id=user_id, user_update_data=update_data_dict)
    return updated_user


@app.delete("/api/v1/admin/user/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_saas_user(
    user_id: int,
    current_admin: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {current_admin.get('user_identifier')} attempting to delete SaaS user ID: {user_id}")
    # Prevent admin from deleting themselves (important!)
    db_user_to_delete = crud.get_user_by_id(db, user_id=user_id)
    if db_user_to_delete and db_user_to_delete.email == current_admin.get("user_identifier"):
        raise HTTPException(status_code=403, detail="Administrators cannot delete their own account.")

    deleted = crud.delete_saas_user(db=db, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="SaaS User not found for deletion.")
    # No content to return on successful DELETE
    return Response(status_code=status.HTTP_204_NO_CONTENT)    


# In backend/main.py

# ... (other imports, Pydantic models like OdooEmployeeSearchResultItem, logger, crud, Depends, etc.)

@app.get("/api/v1/admin/odoo-employees/search", response_model=List[OdooEmployeeSearchResultItem])
async def admin_search_odoo_employees(
    tenant_id: int,                 # MOVED: Required, no default, now comes first among query params
    term: Optional[str] = None,     # Optional, has default
    limit: int = 10,                # Optional, has default
    current_admin: dict = Depends(get_current_admin_user), # FastAPI handles Depends order
    db: Session = Depends(get_db)                             # FastAPI handles Depends order
):
    logger.info(f"Admin {current_admin.get('user_identifier')} searching Odoo employees for tenant {tenant_id} with term: '{term}'")
    
    odoo_creds = crud.get_odoo_credential_by_tenant(db, tenant_id=tenant_id)
    if not odoo_creds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Odoo configuration not found for tenant ID {tenant_id}.")

    decrypted_api_key = decrypt_data(odoo_creds.encrypted_odoo_api_key)
    if not decrypted_api_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Security configuration error for tenant's Odoo connection.")

    # Construct query parameters for the Odoo endpoint
    # Use a dictionary to build params for httpx if call_odoo_api is updated to use it,
    # otherwise, manually build the query string.
    odoo_query_params = {}
    if term:
        odoo_query_params["term"] = term
    if limit is not None: # Ensure limit is passed if explicitly provided, even if it's the default
        odoo_query_params["limit"] = str(limit) # Odoo controller might expect string

    final_odoo_endpoint = "/ess/api/admin/employees/search"
    if odoo_query_params:
        from urllib.parse import urlencode # For robust query string generation
        query_string = urlencode(odoo_query_params)
        final_odoo_endpoint += f"?{query_string}"

    try:
        odoo_employee_list = await call_odoo_api(
            base_url=odoo_creds.odoo_base_url,
            endpoint=final_odoo_endpoint, # Endpoint now includes query string
            method="GET",
            api_key=decrypted_api_key
            # If call_odoo_api was updated to take a `params` dict for GET:
            # params=odoo_query_params
        )
        # Pydantic will validate if the list items match OdooEmployeeSearchResultItem
        return odoo_employee_list
    except HTTPException as e:
        logger.error(f"Error searching Odoo employees for tenant {tenant_id} (Odoo call): Status={e.status_code}, Detail={e.detail}")
        raise e # Re-raise HTTPExceptions from odoo_client (which includes Odoo errors)
    except Exception as e:
        logger.exception(f"Unexpected error searching Odoo employees for tenant {tenant_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to search employees in HR system due to an internal error.")

# --- NEW: DELETE Document Endpoint (integrates with Odoo) ---
@app.delete("/api/v1/document/{document_id}", response_model=GenericMessageResponse, status_code=status.HTTP_200_OK) # Or 204 if no body
async def delete_document_from_odoo(
    document_id: int, # Odoo ir.attachment ID
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_email = current_user.get("user_identifier")
    db_user = crud.get_user_by_email(db, email=user_email)
    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized or inactive.")

    # No direct odoo_emp_id check here as Odoo connector's delete endpoint handles
    # verifying if the attachment belongs to an employee the API user can manage/access.
    logger.info(f"User {user_email} requesting deletion of Odoo document (attachment ID): {document_id}")

    # Fetch Odoo Credentials & Decrypt Key (Can use the _perform_odoo_call helper structure)
    # For DELETE, which might not have a JSON body in Odoo response but a status,
    # call_odoo_api might need slight adjustment or we call httpx directly for more control.
    # Let's try with call_odoo_api first, assuming Odoo connector returns JSON like {"message": "..."}

    odoo_creds = crud.get_odoo_credential_by_tenant(db, tenant_id=db_user.tenant_id)
    if not odoo_creds:
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Odoo connection not configured.")
    decrypted_api_key = decrypt_data(odoo_creds.encrypted_odoo_api_key)
    if not decrypted_api_key:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Security configuration error.")

    odoo_endpoint = f"/ess/api/attachment/{document_id}" # No /download here
    try:
        odoo_response_data = await call_odoo_api( # Use the standard JSON expecting helper
            base_url=odoo_creds.odoo_base_url,
            endpoint=odoo_endpoint,
            method="DELETE", # Specify DELETE method
            api_key=decrypted_api_key
            # No payload for DELETE
        )
        # Odoo connector should return something like: {'message': 'Document deleted successfully.'}
        # and a 200 OK or 204 No Content status. call_odoo_api expects JSON.
        # If Odoo connector returns 204, response.json() in call_odoo_api will fail.
        # We need to ensure Odoo connector returns JSON for DELETE or adapt call_odoo_api.
        # Let's assume Odoo connector returns JSON as defined in its _json_response helper.

        if odoo_response_data and "message" in odoo_response_data:
            return GenericMessageResponse(message=odoo_response_data.get("message"))
        else: # Fallback if message key is missing but call was "successful" (e.g. 204 from Odoo)
            logger.warning(f"Odoo document delete for ID {document_id} returned success status but unexpected body: {odoo_response_data}")
            return GenericMessageResponse(message="Document deletion processed by Odoo.")


    except HTTPException as e:
         # This will catch 401, 403, 404, 500 etc. raised by call_odoo_api if Odoo returns error
         logger.error(f"Error deleting document {document_id} from Odoo for user {user_email}: Status={e.status_code}, Detail={e.detail}")
         raise e
    except Exception as e:
         logger.exception(f"Unexpected error deleting document {document_id} from Odoo for user {user_email}")
         raise HTTPException(status_code=500, detail="Failed to delete document from HR system due to an internal error.")
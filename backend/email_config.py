# In backend/email_config.py
import os
from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig

load_dotenv() # Load variables from .env

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)), # Default to 587 if not set
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "True").lower() == "true", # Convert string to bool
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "False").lower() == "true", # Convert string to bool
    USE_CREDENTIALS=True, # Set to True if MAIL_USERNAME and MAIL_PASSWORD are provided
    VALIDATE_CERTS=True # Set to False if using self-signed certs locally (not for production)
    # TEMPLATE_FOLDER=Path(__file__).parent / 'templates', # If using email templates
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
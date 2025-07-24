import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    print("Error: DATABASE_URL environment variable not set.")
    # Handle error appropriately, maybe exit or raise exception
    exit(1) # Or raise ValueError("DATABASE_URL not set")


# Create the SQLAlchemy engine
# connect_args is needed for SQLite, not typically needed for PostgreSQL
# engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}) # Use this for SQLite
engine = create_engine(DATABASE_URL) # Use this for PostgreSQL

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for our models to inherit from
Base = declarative_base()

# --- Dependency for FastAPI routes ---
# This function will provide a database session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base  # This now includes VerificationToken

SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables if they don't exist (includes VerificationToken)
Base.metadata.create_all(bind=engine) 
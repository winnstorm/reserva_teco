from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config.settings import Settings

settings = Settings()
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(String)  # PENDING, PROCESSING, COMPLETED, FAILED
    request_type = Column(String)  # "search" or "booking"
    request_data = Column(JSON)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error = Column(String, nullable=True)

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)
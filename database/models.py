import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, Float
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(32), unique=True, nullable=False)
    session_string = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class BroadcastTask(Base):
    __tablename__ = "broadcast_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False)
    total_chats = Column(Integer, nullable=False)
    chats_data = Column(Text, nullable=False) # JSON: [{id: 123, title: "Chat"}]
    delay_seconds = Column(Float, nullable=False)
    msg_per_chat = Column(Integer, nullable=False)
    send_type = Column(String(20), nullable=False) # "random" or "simultaneous"
    text_content = Column(Text, nullable=True) # HTML text
    photo_path = Column(String(500), nullable=True)
    status = Column(String(20), default="running") # "running", "paused", "stopped", "completed"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

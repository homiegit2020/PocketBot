from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    BigInteger,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id      = Column(BigInteger, primary_key=True)
    email            = Column(String(255), nullable=True)
    password         = Column(String(255), nullable=True)
    account_id       = Column(String(64), nullable=True)
    po_session       = Column(Text, nullable=True)
    po_uid           = Column(String(64), nullable=True)
    ssid             = Column(Text, nullable=True)
    demo_balance     = Column(Float, default=50000.00)
    real_balance     = Column(Float, default=0.00)
    mode             = Column(String(8), default="demo")
    trade_amount     = Column(Float, default=1.00)
    trade_time       = Column(Integer, default=60)
    martingale_steps = Column(Integer, default=5)
    trades_per_session = Column(Integer, default=10)
    sessions_completed = Column(Integer, default=0)
    is_banned        = Column(Boolean, default=False)
    ban_reason       = Column(Text, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    last_active      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Trade(Base):
    __tablename__ = "trades"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id    = Column(BigInteger, nullable=False)
    session_number = Column(Integer, default=1)
    trade_number   = Column(Integer, default=1)
    pair           = Column(String(32))
    direction      = Column(String(8))
    steps_taken    = Column(Integer, default=1)
    amount         = Column(Float)
    profit         = Column(Float, default=0.0)
    balance_after  = Column(Float, default=0.0)
    win            = Column(Boolean, default=False)
    timestamp      = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=True)
    event_type  = Column(String(64))
    details     = Column(Text, nullable=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)


class BotSettings(Base):
    __tablename__ = "bot_settings"

    key   = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)

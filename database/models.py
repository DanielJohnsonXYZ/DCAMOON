"""Database models for DCAMOON trading system.

This module defines SQLAlchemy models for portfolio management,
replacing the CSV-based storage with proper database relations.
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import uuid

Base = declarative_base()


class Portfolio(Base):
    """Main portfolio table storing portfolio metadata"""
    __tablename__ = 'portfolios'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, default="Main Portfolio")
    description = Column(Text)
    starting_cash = Column(Float, nullable=False, default=100.0)
    current_cash = Column(Float, nullable=False, default=100.0)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="portfolio", cascade="all, delete-orphan")
    snapshots = relationship("PortfolioSnapshot", back_populates="portfolio", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Portfolio(id='{self.id}', name='{self.name}', cash={self.current_cash})>"


class Position(Base):
    """Current stock positions in the portfolio"""
    __tablename__ = 'positions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id = Column(String(36), ForeignKey('portfolios.id'), nullable=False)
    ticker = Column(String(20), nullable=False)
    shares = Column(Float, nullable=False)
    average_cost = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    stop_loss = Column(Float)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="positions")
    
    def __repr__(self):
        return f"<Position(ticker='{self.ticker}', shares={self.shares}, avg_cost={self.average_cost})>"


class Trade(Base):
    """Trade execution log"""
    __tablename__ = 'trades'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id = Column(String(36), ForeignKey('portfolios.id'), nullable=False)
    ticker = Column(String(20), nullable=False)
    trade_type = Column(String(10), nullable=False)  # 'BUY' or 'SELL'
    shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    execution_type = Column(String(20), nullable=False)  # 'MARKET', 'LIMIT', 'STOP_LOSS'
    status = Column(String(20), nullable=False, default='PENDING')  # 'PENDING', 'FILLED', 'CANCELLED'
    reason = Column(Text)
    executed_at = Column(DateTime, nullable=False, default=func.now())
    
    # For tracking P&L
    cost_basis = Column(Float)  # For sells, the original cost basis
    realized_pnl = Column(Float)  # For sells, the realized profit/loss
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="trades")
    
    def __repr__(self):
        return f"<Trade(ticker='{self.ticker}', type='{self.trade_type}', shares={self.shares}, price={self.price})>"


class PortfolioSnapshot(Base):
    """Daily portfolio valuation snapshots"""
    __tablename__ = 'portfolio_snapshots'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id = Column(String(36), ForeignKey('portfolios.id'), nullable=False)
    snapshot_date = Column(DateTime, nullable=False)
    
    # Portfolio totals
    total_equity = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=False)
    total_positions_value = Column(Float, nullable=False)
    
    # Performance metrics
    daily_return = Column(Float)
    total_return = Column(Float)
    total_return_pct = Column(Float)
    
    # Risk metrics
    max_drawdown = Column(Float)
    volatility = Column(Float)
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="snapshots")
    position_snapshots = relationship("PositionSnapshot", back_populates="portfolio_snapshot", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PortfolioSnapshot(date={self.snapshot_date}, equity={self.total_equity})>"


class PositionSnapshot(Base):
    """Individual position values at snapshot time"""
    __tablename__ = 'position_snapshots'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_snapshot_id = Column(String(36), ForeignKey('portfolio_snapshots.id'), nullable=False)
    ticker = Column(String(20), nullable=False)
    shares = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    unrealized_pnl_pct = Column(Float, nullable=False)
    
    # Relationships
    portfolio_snapshot = relationship("PortfolioSnapshot", back_populates="position_snapshots")
    
    def __repr__(self):
        return f"<PositionSnapshot(ticker='{self.ticker}', value={self.market_value})>"


class MarketData(Base):
    """Cache for market data to reduce API calls"""
    __tablename__ = 'market_data'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticker = Column(String(20), nullable=False)
    date = Column(DateTime, nullable=False)
    
    # OHLCV data
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    adjusted_close = Column(Float)
    volume = Column(Integer)
    
    # Additional data
    source = Column(String(50), nullable=False)  # 'yahoo', 'stooq', etc.
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    def __repr__(self):
        return f"<MarketData(ticker='{self.ticker}', date={self.date}, close={self.close_price})>"


class AutomationLog(Base):
    """Log of automated trading decisions and executions"""
    __tablename__ = 'automation_logs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id = Column(String(36), ForeignKey('portfolios.id'), nullable=False)
    
    # LLM/AI decision data
    model_used = Column(String(50), nullable=False)
    prompt_hash = Column(String(64))  # SHA256 hash of the prompt for deduplication
    raw_response = Column(Text)
    parsed_decision = Column(Text)  # JSON string of parsed decision
    confidence_score = Column(Float)
    
    # Execution results
    trades_recommended = Column(Integer, default=0)
    trades_executed = Column(Integer, default=0)
    execution_errors = Column(Text)
    
    # Performance tracking
    portfolio_value_before = Column(Float)
    portfolio_value_after = Column(Float)
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    portfolio = relationship("Portfolio")
    
    def __repr__(self):
        return f"<AutomationLog(model='{self.model_used}', trades={self.trades_executed})>"


class SystemConfig(Base):
    """System configuration settings stored in database"""
    __tablename__ = 'system_config'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(20), nullable=False)  # 'string', 'float', 'int', 'bool', 'json'
    description = Column(Text)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemConfig(key='{self.key}', type='{self.value_type}')>"
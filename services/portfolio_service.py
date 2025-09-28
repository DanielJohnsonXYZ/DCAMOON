"""Portfolio service layer for DCAMOON trading system.

This service provides high-level portfolio operations, abstracting
database operations and business logic.
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database.models import Portfolio, Position, Trade, PortfolioSnapshot, PositionSnapshot
from database.database import db_session_scope
from .market_data_service import MarketDataService

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for portfolio management operations."""
    
    def __init__(self, market_data_service: Optional[MarketDataService] = None):
        self.market_data_service = market_data_service or MarketDataService()
    
    def create_portfolio(
        self, 
        name: str = "Main Portfolio", 
        description: Optional[str] = None,
        starting_cash: float = 100.0
    ) -> Portfolio:
        """Create a new portfolio.
        
        Args:
            name: Portfolio name
            description: Optional description
            starting_cash: Initial cash amount
            
        Returns:
            Created Portfolio instance
        """
        try:
            with db_session_scope() as session:
                portfolio = Portfolio(
                    name=name,
                    description=description,
                    starting_cash=starting_cash,
                    current_cash=starting_cash
                )
                session.add(portfolio)
                session.flush()  # Get the ID
                
                # Create initial snapshot
                self._create_portfolio_snapshot(session, portfolio, datetime.now())
                
                logger.info(f"Created portfolio: {portfolio.name} with ${starting_cash}")
                return portfolio
                
        except Exception as e:
            logger.error(f"Error creating portfolio: {e}")
            raise
    
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Get portfolio by ID."""
        try:
            with db_session_scope() as session:
                portfolio = session.query(Portfolio).filter(
                    Portfolio.id == portfolio_id,
                    Portfolio.is_active == True
                ).first()
                return portfolio
        except Exception as e:
            logger.error(f"Error getting portfolio {portfolio_id}: {e}")
            return None
    
    def get_default_portfolio(self) -> Optional[Portfolio]:
        """Get the default (first active) portfolio."""
        try:
            with db_session_scope() as session:
                portfolio = session.query(Portfolio).filter(
                    Portfolio.is_active == True
                ).order_by(Portfolio.created_at).first()
                return portfolio
        except Exception as e:
            logger.error(f"Error getting default portfolio: {e}")
            return None
    
    def get_positions(self, portfolio_id: str) -> List[Position]:
        """Get all positions for a portfolio."""
        try:
            with db_session_scope() as session:
                positions = session.query(Position).filter(
                    Position.portfolio_id == portfolio_id
                ).order_by(Position.ticker).all()
                return positions
        except Exception as e:
            logger.error(f"Error getting positions for portfolio {portfolio_id}: {e}")
            return []
    
    def get_position(self, portfolio_id: str, ticker: str) -> Optional[Position]:
        """Get a specific position."""
        try:
            with db_session_scope() as session:
                position = session.query(Position).filter(
                    Position.portfolio_id == portfolio_id,
                    Position.ticker == ticker.upper()
                ).first()
                return position
        except Exception as e:
            logger.error(f"Error getting position {ticker} for portfolio {portfolio_id}: {e}")
            return None
    
    def execute_trade(
        self,
        portfolio_id: str,
        ticker: str,
        trade_type: str,  # 'BUY' or 'SELL'
        shares: float,
        price: float,
        execution_type: str = 'MARKET',
        reason: Optional[str] = None
    ) -> Trade:
        """Execute a trade and update portfolio positions.
        
        Args:
            portfolio_id: Portfolio ID
            ticker: Stock ticker
            trade_type: 'BUY' or 'SELL'
            shares: Number of shares
            price: Execution price
            execution_type: Type of order ('MARKET', 'LIMIT', 'STOP_LOSS')
            reason: Optional reason for the trade
            
        Returns:
            Trade record
            
        Raises:
            ValueError: If trade is invalid
            RuntimeError: If execution fails
        """
        try:
            ticker = ticker.upper()
            trade_type = trade_type.upper()
            total_amount = shares * price
            
            with db_session_scope() as session:
                # Get portfolio
                portfolio = session.query(Portfolio).filter(
                    Portfolio.id == portfolio_id
                ).first()
                
                if not portfolio:
                    raise ValueError(f"Portfolio {portfolio_id} not found")
                
                # Validate trade
                if trade_type == 'BUY':
                    if total_amount > portfolio.current_cash:
                        raise ValueError(f"Insufficient cash: need ${total_amount:.2f}, have ${portfolio.current_cash:.2f}")
                elif trade_type == 'SELL':
                    position = session.query(Position).filter(
                        Position.portfolio_id == portfolio_id,
                        Position.ticker == ticker
                    ).first()
                    
                    if not position or position.shares < shares:
                        available_shares = position.shares if position else 0
                        raise ValueError(f"Insufficient shares: need {shares}, have {available_shares}")
                else:
                    raise ValueError(f"Invalid trade type: {trade_type}")
                
                # Create trade record
                trade = Trade(
                    portfolio_id=portfolio_id,
                    ticker=ticker,
                    trade_type=trade_type,
                    shares=shares,
                    price=price,
                    total_amount=total_amount,
                    execution_type=execution_type,
                    status='FILLED',
                    reason=reason
                )
                session.add(trade)
                
                # Update positions and cash
                if trade_type == 'BUY':
                    self._execute_buy(session, portfolio, ticker, shares, price, total_amount)
                else:  # SELL
                    realized_pnl = self._execute_sell(session, portfolio, ticker, shares, price, total_amount)
                    trade.realized_pnl = realized_pnl
                
                logger.info(f"Executed {trade_type} trade: {shares} shares of {ticker} at ${price:.2f}")
                return trade
                
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            raise
    
    def _execute_buy(
        self, 
        session: Session, 
        portfolio: Portfolio, 
        ticker: str, 
        shares: float, 
        price: float, 
        total_amount: float
    ) -> None:
        """Execute buy trade logic."""
        
        # Update cash
        portfolio.current_cash -= total_amount
        
        # Update or create position
        position = session.query(Position).filter(
            Position.portfolio_id == portfolio.id,
            Position.ticker == ticker
        ).first()
        
        if position:
            # Update existing position (weighted average cost)
            total_shares = position.shares + shares
            total_cost = position.cost_basis + total_amount
            position.average_cost = total_cost / total_shares
            position.shares = total_shares
            position.cost_basis = total_cost
        else:
            # Create new position
            position = Position(
                portfolio_id=portfolio.id,
                ticker=ticker,
                shares=shares,
                average_cost=price,
                cost_basis=total_amount
            )
            session.add(position)
    
    def _execute_sell(
        self, 
        session: Session, 
        portfolio: Portfolio, 
        ticker: str, 
        shares: float, 
        price: float, 
        total_amount: float
    ) -> float:
        """Execute sell trade logic and return realized P&L."""
        
        # Get position
        position = session.query(Position).filter(
            Position.portfolio_id == portfolio.id,
            Position.ticker == ticker
        ).first()
        
        if not position:
            raise ValueError(f"No position found for {ticker}")
        
        # Calculate realized P&L
        cost_basis_sold = (shares / position.shares) * position.cost_basis
        realized_pnl = total_amount - cost_basis_sold
        
        # Update cash
        portfolio.current_cash += total_amount
        
        # Update position
        if position.shares == shares:
            # Sell entire position
            session.delete(position)
        else:
            # Partial sell
            remaining_ratio = (position.shares - shares) / position.shares
            position.shares -= shares
            position.cost_basis *= remaining_ratio
        
        return realized_pnl
    
    def update_stop_loss(self, portfolio_id: str, ticker: str, stop_loss: Optional[float]) -> bool:
        """Update stop loss for a position."""
        try:
            with db_session_scope() as session:
                position = session.query(Position).filter(
                    Position.portfolio_id == portfolio_id,
                    Position.ticker == ticker.upper()
                ).first()
                
                if not position:
                    logger.warning(f"Position {ticker} not found for stop loss update")
                    return False
                
                position.stop_loss = stop_loss
                logger.info(f"Updated stop loss for {ticker}: {stop_loss}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating stop loss for {ticker}: {e}")
            return False
    
    def create_daily_snapshot(self, portfolio_id: str, snapshot_date: Optional[datetime] = None) -> PortfolioSnapshot:
        """Create a daily portfolio snapshot with current market values."""
        
        if snapshot_date is None:
            snapshot_date = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)  # Market close
        
        try:
            with db_session_scope() as session:
                portfolio = session.query(Portfolio).filter(
                    Portfolio.id == portfolio_id
                ).first()
                
                if not portfolio:
                    raise ValueError(f"Portfolio {portfolio_id} not found")
                
                # Get current positions
                positions = session.query(Position).filter(
                    Position.portfolio_id == portfolio_id
                ).all()
                
                # Calculate current values
                total_positions_value = 0.0
                position_snapshots = []
                
                for position in positions:
                    # Get current market price
                    current_price = self.market_data_service.get_current_price(position.ticker)
                    if current_price is None:
                        logger.warning(f"Could not get price for {position.ticker}, using cost basis")
                        current_price = position.average_cost
                    
                    market_value = position.shares * current_price
                    unrealized_pnl = market_value - position.cost_basis
                    unrealized_pnl_pct = (unrealized_pnl / position.cost_basis) * 100 if position.cost_basis > 0 else 0
                    
                    total_positions_value += market_value
                    
                    # Create position snapshot
                    pos_snapshot = PositionSnapshot(
                        ticker=position.ticker,
                        shares=position.shares,
                        current_price=current_price,
                        market_value=market_value,
                        cost_basis=position.cost_basis,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_pnl_pct=unrealized_pnl_pct
                    )
                    position_snapshots.append(pos_snapshot)
                
                total_equity = portfolio.current_cash + total_positions_value
                
                # Calculate returns
                total_return = total_equity - portfolio.starting_cash
                total_return_pct = (total_return / portfolio.starting_cash) * 100 if portfolio.starting_cash > 0 else 0
                
                # Get previous snapshot for daily return
                previous_snapshot = session.query(PortfolioSnapshot).filter(
                    PortfolioSnapshot.portfolio_id == portfolio_id
                ).order_by(desc(PortfolioSnapshot.snapshot_date)).first()
                
                daily_return = 0.0
                if previous_snapshot:
                    daily_return = ((total_equity - previous_snapshot.total_equity) / previous_snapshot.total_equity) * 100
                
                # Create snapshot
                snapshot = PortfolioSnapshot(
                    portfolio_id=portfolio_id,
                    snapshot_date=snapshot_date,
                    total_equity=total_equity,
                    cash_balance=portfolio.current_cash,
                    total_positions_value=total_positions_value,
                    daily_return=daily_return,
                    total_return=total_return,
                    total_return_pct=total_return_pct,
                    position_snapshots=position_snapshots
                )
                
                session.add(snapshot)
                logger.info(f"Created portfolio snapshot: ${total_equity:.2f} total equity")
                return snapshot
                
        except Exception as e:
            logger.error(f"Error creating portfolio snapshot: {e}")
            raise
    
    def _create_portfolio_snapshot(self, session: Session, portfolio: Portfolio, snapshot_date: datetime) -> None:
        """Helper to create initial portfolio snapshot."""
        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            snapshot_date=snapshot_date,
            total_equity=portfolio.current_cash,
            cash_balance=portfolio.current_cash,
            total_positions_value=0.0,
            daily_return=0.0,
            total_return=0.0,
            total_return_pct=0.0
        )
        session.add(snapshot)
    
    def get_portfolio_history(
        self, 
        portfolio_id: str, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[PortfolioSnapshot]:
        """Get portfolio snapshots for a date range."""
        try:
            with db_session_scope() as session:
                query = session.query(PortfolioSnapshot).filter(
                    PortfolioSnapshot.portfolio_id == portfolio_id
                )
                
                if start_date:
                    query = query.filter(PortfolioSnapshot.snapshot_date >= start_date)
                if end_date:
                    query = query.filter(PortfolioSnapshot.snapshot_date <= end_date)
                
                snapshots = query.order_by(PortfolioSnapshot.snapshot_date).all()
                return snapshots
                
        except Exception as e:
            logger.error(f"Error getting portfolio history: {e}")
            return []
    
    def get_trade_history(
        self, 
        portfolio_id: str, 
        ticker: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get trade history for a portfolio."""
        try:
            with db_session_scope() as session:
                query = session.query(Trade).filter(
                    Trade.portfolio_id == portfolio_id
                )
                
                if ticker:
                    query = query.filter(Trade.ticker == ticker.upper())
                
                trades = query.order_by(desc(Trade.executed_at)).limit(limit).all()
                return trades
                
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return []
    
    def get_portfolio_summary(self, portfolio_id: str) -> Dict[str, Any]:
        """Get comprehensive portfolio summary."""
        try:
            with db_session_scope() as session:
                portfolio = session.query(Portfolio).filter(
                    Portfolio.id == portfolio_id
                ).first()
                
                if not portfolio:
                    raise ValueError(f"Portfolio {portfolio_id} not found")
                
                # Get latest snapshot
                latest_snapshot = session.query(PortfolioSnapshot).filter(
                    PortfolioSnapshot.portfolio_id == portfolio_id
                ).order_by(desc(PortfolioSnapshot.snapshot_date)).first()
                
                # Get position count
                position_count = session.query(func.count(Position.id)).filter(
                    Position.portfolio_id == portfolio_id
                ).scalar() or 0
                
                # Get trade count
                trade_count = session.query(func.count(Trade.id)).filter(
                    Trade.portfolio_id == portfolio_id
                ).scalar() or 0
                
                summary = {
                    "portfolio_id": portfolio.id,
                    "name": portfolio.name,
                    "created_at": portfolio.created_at,
                    "starting_cash": portfolio.starting_cash,
                    "current_cash": portfolio.current_cash,
                    "position_count": position_count,
                    "trade_count": trade_count
                }
                
                if latest_snapshot:
                    summary.update({
                        "total_equity": latest_snapshot.total_equity,
                        "total_positions_value": latest_snapshot.total_positions_value,
                        "total_return": latest_snapshot.total_return,
                        "total_return_pct": latest_snapshot.total_return_pct,
                        "daily_return": latest_snapshot.daily_return,
                        "last_updated": latest_snapshot.snapshot_date
                    })
                else:
                    summary.update({
                        "total_equity": portfolio.current_cash,
                        "total_positions_value": 0.0,
                        "total_return": 0.0,
                        "total_return_pct": 0.0,
                        "daily_return": 0.0,
                        "last_updated": portfolio.created_at
                    })
                
                return summary
                
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            raise
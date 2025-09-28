"""Tests for database functionality."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from database.models import Portfolio, Position, Trade, PortfolioSnapshot, MarketData
from database.database import DatabaseManager


class TestDatabaseModels:
    """Test database model functionality."""
    
    def test_portfolio_creation(self, db_session):
        """Test creating a portfolio."""
        portfolio = Portfolio(
            name="Test Portfolio",
            description="A test portfolio",
            starting_cash=1000.0,
            current_cash=800.0
        )
        
        db_session.add(portfolio)
        db_session.commit()
        
        assert portfolio.id is not None
        assert portfolio.created_at is not None
        assert portfolio.updated_at is not None
        assert portfolio.is_active is True
    
    def test_portfolio_relationships(self, db_session):
        """Test portfolio relationships with positions and trades."""
        portfolio = Portfolio(
            name="Test Portfolio",
            starting_cash=1000.0,
            current_cash=800.0
        )
        db_session.add(portfolio)
        db_session.flush()  # Get the ID
        
        # Add position
        position = Position(
            portfolio_id=portfolio.id,
            ticker="AAPL",
            shares=10.0,
            average_cost=150.0,
            cost_basis=1500.0
        )
        db_session.add(position)
        
        # Add trade
        trade = Trade(
            portfolio_id=portfolio.id,
            ticker="AAPL",
            trade_type="BUY",
            shares=10.0,
            price=150.0,
            total_amount=1500.0,
            execution_type="MARKET",
            status="FILLED"
        )
        db_session.add(trade)
        
        db_session.commit()
        
        # Test relationships
        assert len(portfolio.positions) == 1
        assert len(portfolio.trades) == 1
        assert portfolio.positions[0].ticker == "AAPL"
        assert portfolio.trades[0].ticker == "AAPL"
    
    def test_position_constraints(self, db_session, sample_portfolio):
        """Test position model constraints."""
        # Valid position
        position = Position(
            portfolio_id=sample_portfolio.id,
            ticker="AAPL",
            shares=10.0,
            average_cost=150.0,
            cost_basis=1500.0
        )
        db_session.add(position)
        db_session.commit()
        
        # Position without portfolio_id should fail
        invalid_position = Position(
            ticker="GOOGL",
            shares=5.0,
            average_cost=2800.0,
            cost_basis=14000.0
        )
        db_session.add(invalid_position)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_trade_model(self, db_session, sample_portfolio):
        """Test trade model functionality."""
        trade = Trade(
            portfolio_id=sample_portfolio.id,
            ticker="MSFT",
            trade_type="BUY",
            shares=50.0,
            price=350.0,
            total_amount=17500.0,
            execution_type="LIMIT",
            status="FILLED",
            reason="Growth investment",
            cost_basis=17500.0,
            realized_pnl=0.0
        )
        
        db_session.add(trade)
        db_session.commit()
        
        assert trade.id is not None
        assert trade.executed_at is not None
        assert trade.ticker == "MSFT"
        assert trade.total_amount == 17500.0
    
    def test_portfolio_snapshot(self, db_session, sample_portfolio):
        """Test portfolio snapshot model."""
        snapshot = PortfolioSnapshot(
            portfolio_id=sample_portfolio.id,
            snapshot_date=datetime(2024, 1, 15, 16, 0, 0),
            total_equity=50000.0,
            cash_balance=10000.0,
            total_positions_value=40000.0,
            daily_return=2.5,
            total_return=5000.0,
            total_return_pct=11.11
        )
        
        db_session.add(snapshot)
        db_session.commit()
        
        assert snapshot.id is not None
        assert snapshot.created_at is not None
        assert snapshot.total_equity == 50000.0
    
    def test_market_data_model(self, db_session):
        """Test market data model."""
        market_data = MarketData(
            ticker="AAPL",
            date=datetime(2024, 1, 15),
            open_price=150.0,
            high_price=155.0,
            low_price=149.0,
            close_price=153.0,
            adjusted_close=153.0,
            volume=1000000,
            source="yahoo"
        )
        
        db_session.add(market_data)
        db_session.commit()
        
        assert market_data.id is not None
        assert market_data.ticker == "AAPL"
        assert market_data.close_price == 153.0


class TestDatabaseManager:
    """Test database manager functionality."""
    
    def test_database_manager_creation(self, test_database_url):
        """Test creating a database manager."""
        manager = DatabaseManager(test_database_url)
        
        assert manager.database_url == test_database_url
        assert manager.engine is not None
        assert manager.SessionLocal is not None
    
    def test_create_tables(self, test_database_url):
        """Test table creation."""
        manager = DatabaseManager(test_database_url)
        manager.create_tables()
        
        # Should not raise any exceptions
        assert True
    
    def test_session_scope(self, db_manager):
        """Test session scope context manager."""
        with db_manager.session_scope() as session:
            portfolio = Portfolio(
                name="Context Test",
                starting_cash=1000.0,
                current_cash=1000.0
            )
            session.add(portfolio)
            # Should auto-commit on successful exit
        
        # Verify the portfolio was saved
        with db_manager.session_scope() as session:
            found = session.query(Portfolio).filter(
                Portfolio.name == "Context Test"
            ).first()
            assert found is not None
    
    def test_session_scope_rollback(self, db_manager):
        """Test session scope rollback on exception."""
        try:
            with db_manager.session_scope() as session:
                portfolio = Portfolio(
                    name="Rollback Test",
                    starting_cash=1000.0,
                    current_cash=1000.0
                )
                session.add(portfolio)
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Verify the portfolio was NOT saved
        with db_manager.session_scope() as session:
            found = session.query(Portfolio).filter(
                Portfolio.name == "Rollback Test"
            ).first()
            assert found is None
    
    def test_health_check(self, db_manager):
        """Test database health check."""
        result = db_manager.health_check()
        assert result is True
    
    def test_get_db_info(self, db_manager):
        """Test getting database information."""
        info = db_manager.get_db_info()
        
        assert "type" in info
        assert "version" in info
        assert "url" in info
        assert "healthy" in info
        assert info["healthy"] is True


class TestDatabaseQueries:
    """Test complex database queries."""
    
    def test_portfolio_with_positions_query(self, db_session, sample_portfolio, sample_positions):
        """Test querying portfolio with positions."""
        # Query portfolio with positions
        portfolio = db_session.query(Portfolio).filter(
            Portfolio.id == sample_portfolio.id
        ).first()
        
        assert portfolio is not None
        assert len(portfolio.positions) == 2
        
        # Test querying positions directly
        positions = db_session.query(Position).filter(
            Position.portfolio_id == sample_portfolio.id
        ).all()
        
        assert len(positions) == 2
        tickers = [p.ticker for p in positions]
        assert "AAPL" in tickers
        assert "GOOGL" in tickers
    
    def test_trade_history_query(self, db_session, sample_portfolio, sample_trades):
        """Test querying trade history."""
        from sqlalchemy import desc
        
        # Get all trades for portfolio
        trades = db_session.query(Trade).filter(
            Trade.portfolio_id == sample_portfolio.id
        ).order_by(desc(Trade.executed_at)).all()
        
        assert len(trades) == 2
        
        # Get trades for specific ticker
        aapl_trades = db_session.query(Trade).filter(
            Trade.portfolio_id == sample_portfolio.id,
            Trade.ticker == "AAPL"
        ).all()
        
        assert len(aapl_trades) == 1
        assert aapl_trades[0].ticker == "AAPL"
    
    def test_portfolio_snapshot_query(self, db_session, sample_portfolio):
        """Test querying portfolio snapshots."""
        from sqlalchemy import desc
        
        # Create test snapshots
        dates = [
            datetime(2024, 1, 10, 16, 0, 0),
            datetime(2024, 1, 11, 16, 0, 0),
            datetime(2024, 1, 12, 16, 0, 0),
        ]
        
        for i, date in enumerate(dates):
            snapshot = PortfolioSnapshot(
                portfolio_id=sample_portfolio.id,
                snapshot_date=date,
                total_equity=10000.0 + (i * 100),  # Increasing value
                cash_balance=5000.0,
                total_positions_value=5000.0 + (i * 100),
                daily_return=1.0 if i > 0 else 0.0,
                total_return=i * 100,
                total_return_pct=(i * 100) / 10000.0 * 100
            )
            db_session.add(snapshot)
        
        db_session.commit()
        
        # Query latest snapshot
        latest = db_session.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.portfolio_id == sample_portfolio.id
        ).order_by(desc(PortfolioSnapshot.snapshot_date)).first()
        
        assert latest.total_equity == 10200.0  # Last one
        
        # Query date range
        start_date = datetime(2024, 1, 11)
        end_date = datetime(2024, 1, 12)
        
        range_snapshots = db_session.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.portfolio_id == sample_portfolio.id,
            PortfolioSnapshot.snapshot_date >= start_date,
            PortfolioSnapshot.snapshot_date <= end_date
        ).all()
        
        assert len(range_snapshots) == 2
    
    def test_market_data_query(self, db_session):
        """Test querying market data."""
        # Add test market data
        dates = [
            datetime(2024, 1, 10),
            datetime(2024, 1, 11),
            datetime(2024, 1, 12),
        ]
        
        for i, date in enumerate(dates):
            market_data = MarketData(
                ticker="AAPL",
                date=date,
                open_price=150.0 + i,
                high_price=155.0 + i,
                low_price=149.0 + i,
                close_price=153.0 + i,
                adjusted_close=153.0 + i,
                volume=1000000 + (i * 100000),
                source="yahoo"
            )
            db_session.add(market_data)
        
        db_session.commit()
        
        # Query latest price
        latest = db_session.query(MarketData).filter(
            MarketData.ticker == "AAPL"
        ).order_by(desc(MarketData.date)).first()
        
        assert latest.close_price == 155.0  # Last one (153 + 2)
        
        # Query date range
        start_date = datetime(2024, 1, 11)
        end_date = datetime(2024, 1, 12)
        
        range_data = db_session.query(MarketData).filter(
            MarketData.ticker == "AAPL",
            MarketData.date >= start_date,
            MarketData.date <= end_date
        ).all()
        
        assert len(range_data) == 2
"""Tests for portfolio service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from database.models import Portfolio, Position, Trade, PortfolioSnapshot
from services.portfolio_service import PortfolioService


class TestPortfolioService:
    """Test cases for PortfolioService."""
    
    def test_create_portfolio(self, portfolio_service):
        """Test creating a new portfolio."""
        portfolio = portfolio_service.create_portfolio(
            name="Test Portfolio",
            description="A test portfolio",
            starting_cash=5000.0
        )
        
        assert portfolio.name == "Test Portfolio"
        assert portfolio.description == "A test portfolio"
        assert portfolio.starting_cash == 5000.0
        assert portfolio.current_cash == 5000.0
        assert portfolio.is_active is True
        assert portfolio.id is not None
    
    def test_create_portfolio_with_defaults(self, portfolio_service):
        """Test creating portfolio with default values."""
        portfolio = portfolio_service.create_portfolio()
        
        assert portfolio.name == "Main Portfolio"
        assert portfolio.starting_cash == 100.0
        assert portfolio.current_cash == 100.0
    
    def test_get_portfolio(self, portfolio_service, sample_portfolio):
        """Test getting a portfolio by ID."""
        retrieved = portfolio_service.get_portfolio(sample_portfolio.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_portfolio.id
        assert retrieved.name == sample_portfolio.name
    
    def test_get_portfolio_nonexistent(self, portfolio_service):
        """Test getting a non-existent portfolio."""
        result = portfolio_service.get_portfolio("nonexistent-id")
        assert result is None
    
    def test_get_positions(self, portfolio_service, sample_portfolio, sample_positions):
        """Test getting positions for a portfolio."""
        positions = portfolio_service.get_positions(sample_portfolio.id)
        
        assert len(positions) == 2
        
        # Check AAPL position
        aapl_position = next(p for p in positions if p.ticker == "AAPL")
        assert aapl_position.shares == 100.0
        assert aapl_position.average_cost == 150.0
        assert aapl_position.stop_loss == 140.0
        
        # Check GOOGL position
        googl_position = next(p for p in positions if p.ticker == "GOOGL")
        assert googl_position.shares == 10.0
        assert googl_position.average_cost == 2800.0
        assert googl_position.stop_loss is None
    
    def test_get_position_specific(self, portfolio_service, sample_portfolio, sample_positions):
        """Test getting a specific position."""
        position = portfolio_service.get_position(sample_portfolio.id, "AAPL")
        
        assert position is not None
        assert position.ticker == "AAPL"
        assert position.shares == 100.0
        
        # Test case insensitive
        position_lower = portfolio_service.get_position(sample_portfolio.id, "aapl")
        assert position_lower is not None
        assert position_lower.ticker == "AAPL"
    
    def test_get_position_nonexistent(self, portfolio_service, sample_portfolio):
        """Test getting a non-existent position."""
        position = portfolio_service.get_position(sample_portfolio.id, "TSLA")
        assert position is None


class TestTradeExecution:
    """Test cases for trade execution."""
    
    def test_execute_buy_trade_new_position(self, portfolio_service, sample_portfolio):
        """Test executing a buy trade for a new position."""
        initial_cash = sample_portfolio.current_cash
        
        trade = portfolio_service.execute_trade(
            portfolio_id=sample_portfolio.id,
            ticker="MSFT",
            trade_type="BUY",
            shares=50.0,
            price=350.0,
            reason="Test buy"
        )
        
        # Check trade record
        assert trade.ticker == "MSFT"
        assert trade.trade_type == "BUY"
        assert trade.shares == 50.0
        assert trade.price == 350.0
        assert trade.total_amount == 17500.0
        assert trade.status == "FILLED"
        
        # Check position was created
        position = portfolio_service.get_position(sample_portfolio.id, "MSFT")
        assert position is not None
        assert position.shares == 50.0
        assert position.average_cost == 350.0
        assert position.cost_basis == 17500.0
        
        # Check cash was deducted
        updated_portfolio = portfolio_service.get_portfolio(sample_portfolio.id)
        assert updated_portfolio.current_cash == initial_cash - 17500.0
    
    def test_execute_buy_trade_existing_position(self, portfolio_service, sample_portfolio, sample_positions):
        """Test executing a buy trade for an existing position."""
        initial_cash = sample_portfolio.current_cash
        
        # Buy more AAPL (already have 100 shares at $150)
        trade = portfolio_service.execute_trade(
            portfolio_id=sample_portfolio.id,
            ticker="AAPL",
            trade_type="BUY",
            shares=50.0,
            price=160.0,
            reason="Add to position"
        )
        
        # Check trade record
        assert trade.ticker == "AAPL"
        assert trade.shares == 50.0
        assert trade.price == 160.0
        
        # Check position was updated (weighted average cost)
        position = portfolio_service.get_position(sample_portfolio.id, "AAPL")
        assert position.shares == 150.0  # 100 + 50
        assert position.cost_basis == 23000.0  # 15000 + 8000
        assert position.average_cost == pytest.approx(153.33, rel=1e-2)  # 23000 / 150
        
        # Check cash was deducted
        updated_portfolio = portfolio_service.get_portfolio(sample_portfolio.id)
        assert updated_portfolio.current_cash == initial_cash - 8000.0
    
    def test_execute_sell_trade_partial(self, portfolio_service, sample_portfolio, sample_positions):
        """Test executing a partial sell trade."""
        initial_cash = sample_portfolio.current_cash
        
        # Sell 50 AAPL shares (have 100 at $150 cost basis)
        trade = portfolio_service.execute_trade(
            portfolio_id=sample_portfolio.id,
            ticker="AAPL",
            trade_type="SELL",
            shares=50.0,
            price=160.0,
            reason="Take profits"
        )
        
        # Check trade record
        assert trade.ticker == "AAPL"
        assert trade.trade_type == "SELL"
        assert trade.shares == 50.0
        assert trade.price == 160.0
        assert trade.total_amount == 8000.0
        
        # Check realized P&L (sold 50% at $160, cost basis was $150)
        expected_cost_basis = 7500.0  # 50% of 15000
        expected_pnl = 8000.0 - 7500.0  # 500
        assert trade.realized_pnl == pytest.approx(expected_pnl, rel=1e-2)
        
        # Check position was updated
        position = portfolio_service.get_position(sample_portfolio.id, "AAPL")
        assert position.shares == 50.0
        assert position.cost_basis == 7500.0  # Remaining 50%
        assert position.average_cost == 150.0  # Same average cost
        
        # Check cash was added
        updated_portfolio = portfolio_service.get_portfolio(sample_portfolio.id)
        assert updated_portfolio.current_cash == initial_cash + 8000.0
    
    def test_execute_sell_trade_full(self, portfolio_service, sample_portfolio, sample_positions):
        """Test executing a full sell trade."""
        initial_cash = sample_portfolio.current_cash
        
        # Sell all AAPL shares (100 at $150 cost basis)
        trade = portfolio_service.execute_trade(
            portfolio_id=sample_portfolio.id,
            ticker="AAPL",
            trade_type="SELL",
            shares=100.0,
            price=155.0,
            reason="Exit position"
        )
        
        # Check trade record
        assert trade.realized_pnl == 500.0  # (155 - 150) * 100
        
        # Check position was removed
        position = portfolio_service.get_position(sample_portfolio.id, "AAPL")
        assert position is None
        
        # Check cash was added
        updated_portfolio = portfolio_service.get_portfolio(sample_portfolio.id)
        assert updated_portfolio.current_cash == initial_cash + 15500.0
    
    def test_execute_buy_insufficient_cash(self, portfolio_service, sample_portfolio):
        """Test buy trade with insufficient cash."""
        # Try to buy more than available cash
        with pytest.raises(ValueError, match="Insufficient cash"):
            portfolio_service.execute_trade(
                portfolio_id=sample_portfolio.id,
                ticker="EXPENSIVE",
                trade_type="BUY",
                shares=1000.0,
                price=100.0  # Would cost $100,000
            )
    
    def test_execute_sell_insufficient_shares(self, portfolio_service, sample_portfolio, sample_positions):
        """Test sell trade with insufficient shares."""
        # Try to sell more shares than owned
        with pytest.raises(ValueError, match="Insufficient shares"):
            portfolio_service.execute_trade(
                portfolio_id=sample_portfolio.id,
                ticker="AAPL",
                trade_type="SELL",
                shares=200.0,  # Only have 100
                price=150.0
            )
    
    def test_execute_sell_no_position(self, portfolio_service, sample_portfolio):
        """Test sell trade for non-existent position."""
        with pytest.raises(ValueError, match="Insufficient shares"):
            portfolio_service.execute_trade(
                portfolio_id=sample_portfolio.id,
                ticker="TSLA",
                trade_type="SELL",
                shares=10.0,
                price=800.0
            )
    
    def test_invalid_trade_type(self, portfolio_service, sample_portfolio):
        """Test invalid trade type."""
        with pytest.raises(ValueError, match="Invalid trade type"):
            portfolio_service.execute_trade(
                portfolio_id=sample_portfolio.id,
                ticker="AAPL",
                trade_type="INVALID",
                shares=10.0,
                price=150.0
            )


class TestStopLoss:
    """Test cases for stop loss management."""
    
    def test_update_stop_loss(self, portfolio_service, sample_portfolio, sample_positions):
        """Test updating stop loss for a position."""
        result = portfolio_service.update_stop_loss(
            sample_portfolio.id, 
            "AAPL", 
            145.0
        )
        
        assert result is True
        
        # Verify stop loss was updated
        position = portfolio_service.get_position(sample_portfolio.id, "AAPL")
        assert position.stop_loss == 145.0
    
    def test_update_stop_loss_remove(self, portfolio_service, sample_portfolio, sample_positions):
        """Test removing stop loss (set to None)."""
        result = portfolio_service.update_stop_loss(
            sample_portfolio.id,
            "AAPL",
            None
        )
        
        assert result is True
        
        # Verify stop loss was removed
        position = portfolio_service.get_position(sample_portfolio.id, "AAPL")
        assert position.stop_loss is None
    
    def test_update_stop_loss_nonexistent(self, portfolio_service, sample_portfolio):
        """Test updating stop loss for non-existent position."""
        result = portfolio_service.update_stop_loss(
            sample_portfolio.id,
            "TSLA",
            800.0
        )
        
        assert result is False


class TestPortfolioSnapshots:
    """Test cases for portfolio snapshots."""
    
    def test_create_daily_snapshot(self, portfolio_service, sample_portfolio, sample_positions):
        """Test creating a daily portfolio snapshot."""
        snapshot_date = datetime(2024, 1, 15, 16, 0, 0)
        
        snapshot = portfolio_service.create_daily_snapshot(
            sample_portfolio.id,
            snapshot_date
        )
        
        assert snapshot.portfolio_id == sample_portfolio.id
        assert snapshot.snapshot_date == snapshot_date
        assert snapshot.cash_balance == sample_portfolio.current_cash
        
        # Check calculated values (using mock prices: AAPL=155, GOOGL=2900)
        expected_aapl_value = 100 * 155.0  # 15500
        expected_googl_value = 10 * 2900.0  # 29000
        expected_total_positions = expected_aapl_value + expected_googl_value  # 44500
        expected_total_equity = sample_portfolio.current_cash + expected_total_positions
        
        assert snapshot.total_positions_value == expected_total_positions
        assert snapshot.total_equity == expected_total_equity
        
        # Check position snapshots
        assert len(snapshot.position_snapshots) == 2
        
        aapl_snap = next(ps for ps in snapshot.position_snapshots if ps.ticker == "AAPL")
        assert aapl_snap.current_price == 155.0
        assert aapl_snap.market_value == 15500.0
        assert aapl_snap.unrealized_pnl == 500.0  # 15500 - 15000
    
    def test_get_portfolio_history(self, portfolio_service, sample_portfolio):
        """Test getting portfolio history."""
        # Create a few snapshots
        dates = [
            datetime(2024, 1, 10, 16, 0, 0),
            datetime(2024, 1, 11, 16, 0, 0),
            datetime(2024, 1, 12, 16, 0, 0),
        ]
        
        for date in dates:
            portfolio_service.create_daily_snapshot(sample_portfolio.id, date)
        
        # Get all history
        history = portfolio_service.get_portfolio_history(sample_portfolio.id)
        assert len(history) >= 3  # At least our 3 + potentially the initial one
        
        # Get history for date range
        start_date = datetime(2024, 1, 11)
        end_date = datetime(2024, 1, 12)
        
        filtered_history = portfolio_service.get_portfolio_history(
            sample_portfolio.id,
            start_date,
            end_date
        )
        
        # Should have snapshots for 1/11 and 1/12
        assert len(filtered_history) == 2


class TestPortfolioSummary:
    """Test cases for portfolio summary."""
    
    def test_get_portfolio_summary(self, portfolio_service, sample_portfolio, sample_positions, sample_trades):
        """Test getting comprehensive portfolio summary."""
        # Create a snapshot
        portfolio_service.create_daily_snapshot(sample_portfolio.id)
        
        summary = portfolio_service.get_portfolio_summary(sample_portfolio.id)
        
        # Check basic info
        assert summary["portfolio_id"] == sample_portfolio.id
        assert summary["name"] == sample_portfolio.name
        assert summary["starting_cash"] == sample_portfolio.starting_cash
        assert summary["current_cash"] == sample_portfolio.current_cash
        
        # Check counts
        assert summary["position_count"] == 2
        assert summary["trade_count"] == 2
        
        # Check snapshot data
        assert "total_equity" in summary
        assert "total_return" in summary
        assert "total_return_pct" in summary
        assert "last_updated" in summary
    
    def test_get_trade_history(self, portfolio_service, sample_portfolio, sample_trades):
        """Test getting trade history."""
        trades = portfolio_service.get_trade_history(sample_portfolio.id)
        
        assert len(trades) == 2
        
        # Should be ordered by executed_at descending (most recent first)
        assert trades[0].executed_at >= trades[1].executed_at
        
        # Test filtering by ticker
        aapl_trades = portfolio_service.get_trade_history(
            sample_portfolio.id,
            ticker="AAPL"
        )
        assert len(aapl_trades) == 1
        assert aapl_trades[0].ticker == "AAPL"
        
        # Test limit
        limited_trades = portfolio_service.get_trade_history(
            sample_portfolio.id,
            limit=1
        )
        assert len(limited_trades) == 1
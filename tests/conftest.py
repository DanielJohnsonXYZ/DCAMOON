"""Pytest configuration and fixtures for DCAMOON tests."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Portfolio, Position, Trade, PortfolioSnapshot
from database.database import DatabaseManager
from services.portfolio_service import PortfolioService
from services.market_data_service import MarketDataService


@pytest.fixture(scope="session")
def test_database_url():
    """Provide a test database URL."""
    # Use in-memory SQLite for tests
    return "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_manager(test_database_url):
    """Provide a fresh database manager for each test."""
    manager = DatabaseManager(test_database_url)
    manager.create_tables()
    yield manager
    # Cleanup happens automatically with in-memory database


@pytest.fixture(scope="function")
def db_session(db_manager):
    """Provide a database session for tests."""
    session = db_manager.get_session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def sample_portfolio(db_session) -> Portfolio:
    """Create a sample portfolio for testing."""
    portfolio = Portfolio(
        name="Test Portfolio",
        description="Portfolio for testing",
        starting_cash=10000.0,
        current_cash=8000.0
    )
    db_session.add(portfolio)
    db_session.commit()
    return portfolio


@pytest.fixture(scope="function")
def sample_positions(db_session, sample_portfolio) -> list[Position]:
    """Create sample positions for testing."""
    positions = [
        Position(
            portfolio_id=sample_portfolio.id,
            ticker="AAPL",
            shares=100.0,
            average_cost=150.0,
            cost_basis=15000.0,
            stop_loss=140.0
        ),
        Position(
            portfolio_id=sample_portfolio.id,
            ticker="GOOGL",
            shares=10.0,
            average_cost=2800.0,
            cost_basis=28000.0
        )
    ]
    
    for position in positions:
        db_session.add(position)
    
    db_session.commit()
    return positions


@pytest.fixture(scope="function")
def sample_trades(db_session, sample_portfolio) -> list[Trade]:
    """Create sample trades for testing."""
    trades = [
        Trade(
            portfolio_id=sample_portfolio.id,
            ticker="AAPL",
            trade_type="BUY",
            shares=100.0,
            price=150.0,
            total_amount=15000.0,
            execution_type="MARKET",
            status="FILLED",
            reason="Initial purchase"
        ),
        Trade(
            portfolio_id=sample_portfolio.id,
            ticker="GOOGL", 
            trade_type="BUY",
            shares=10.0,
            price=2800.0,
            total_amount=28000.0,
            execution_type="LIMIT",
            status="FILLED",
            reason="Growth play"
        )
    ]
    
    for trade in trades:
        db_session.add(trade)
    
    db_session.commit()
    return trades


@pytest.fixture(scope="function")
def portfolio_service(db_manager):
    """Provide a portfolio service instance for testing."""
    # Mock market data service to avoid external API calls
    market_data_service = MockMarketDataService()
    return PortfolioService(market_data_service)


class MockMarketDataService:
    """Mock market data service for testing."""
    
    # Mock price data
    MOCK_PRICES = {
        "AAPL": 155.0,
        "GOOGL": 2900.0,
        "MSFT": 350.0,
        "TSLA": 800.0,
        "NVDA": 450.0
    }
    
    def get_current_price(self, ticker: str, use_cache: bool = True) -> float:
        """Return mock price for ticker."""
        return self.MOCK_PRICES.get(ticker.upper(), 100.0)
    
    def get_multiple_prices(self, tickers: list[str], use_cache: bool = True) -> dict[str, float]:
        """Return mock prices for multiple tickers."""
        return {ticker: self.get_current_price(ticker, use_cache) for ticker in tickers}


@pytest.fixture(scope="function")
def mock_market_data():
    """Provide mock market data for testing."""
    return MockMarketDataService()


# Test data helpers
@pytest.fixture
def sample_trade_data():
    """Sample trade data for testing."""
    return {
        "ticker": "AAPL",
        "trade_type": "BUY",
        "shares": 50.0,
        "price": 160.0,
        "execution_type": "MARKET",
        "reason": "Test trade"
    }


@pytest.fixture
def sample_position_data():
    """Sample position data for testing."""
    return {
        "ticker": "MSFT",
        "shares": 25.0,
        "average_cost": 350.0,
        "cost_basis": 8750.0,
        "stop_loss": 320.0
    }


# Utility fixtures
@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing."""
    fixed_time = datetime(2024, 1, 15, 16, 0, 0)  # Market close time
    return fixed_time


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing CSV migration."""
    import csv
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        # Write sample CSV data that matches the original format
        writer.writerow([
            "Date", "Ticker", "Shares", "Buy Price", "Cost Basis", "Stop Loss",
            "Current Price", "Total Value", "PnL", "Action", "Cash Balance", "Total Equity"
        ])
        writer.writerow([
            "2024-01-10", "AAPL", "100", "150.0", "15000.0", "140.0",
            "155.0", "15500.0", "500.0", "HOLD", "", ""
        ])
        writer.writerow([
            "2024-01-10", "GOOGL", "10", "2800.0", "28000.0", "",
            "2900.0", "29000.0", "1000.0", "HOLD", "", ""
        ])
        writer.writerow([
            "2024-01-10", "TOTAL", "", "", "", "",
            "", "44500.0", "1500.0", "", "2000.0", "46500.0"
        ])
        
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


# Performance testing helpers
@pytest.fixture
def large_portfolio_data():
    """Generate large portfolio data for performance testing."""
    import random
    import string
    
    tickers = []
    for _ in range(100):  # 100 random tickers
        ticker = ''.join(random.choices(string.ascii_uppercase, k=4))
        tickers.append(ticker)
    
    positions = []
    for ticker in tickers:
        positions.append({
            "ticker": ticker,
            "shares": random.uniform(1, 1000),
            "average_cost": random.uniform(10, 500),
            "stop_loss": None if random.random() < 0.3 else random.uniform(5, 400)
        })
    
    return {
        "tickers": tickers,
        "positions": positions,
        "starting_cash": 100000.0
    }


# Configuration for pytest
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
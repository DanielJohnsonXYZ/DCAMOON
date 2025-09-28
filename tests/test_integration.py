"""Integration tests for DCAMOON trading system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from services.portfolio_service import PortfolioService
from services.market_data_service import MarketDataService


@pytest.mark.integration
class TestPortfolioIntegration:
    """Integration tests for complete portfolio workflows."""
    
    def test_complete_trading_workflow(self, portfolio_service):
        """Test a complete trading workflow from portfolio creation to profit taking."""
        # 1. Create portfolio
        portfolio = portfolio_service.create_portfolio(
            name="Integration Test Portfolio",
            starting_cash=10000.0
        )
        
        assert portfolio.current_cash == 10000.0
        
        # 2. Execute initial buy trades
        apple_trade = portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            ticker="AAPL",
            trade_type="BUY",
            shares=50.0,
            price=150.0,
            reason="Initial position"
        )
        
        google_trade = portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            ticker="GOOGL",
            trade_type="BUY", 
            shares=5.0,
            price=2800.0,
            reason="Growth play"
        )
        
        # 3. Verify portfolio state
        updated_portfolio = portfolio_service.get_portfolio(portfolio.id)
        expected_cash = 10000.0 - (50 * 150.0) - (5 * 2800.0)  # 10000 - 7500 - 14000 = -11500
        
        # This should fail due to insufficient cash for the second trade
        with pytest.raises(ValueError, match="Insufficient cash"):
            portfolio_service.execute_trade(
                portfolio_id=portfolio.id,
                ticker="GOOGL",
                trade_type="BUY",
                shares=5.0,
                price=2800.0,
                reason="Growth play"
            )
        
        # 3. Buy smaller GOOGL position that fits budget
        google_trade = portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            ticker="GOOGL",
            trade_type="BUY",
            shares=1.0,
            price=2800.0,
            reason="Small growth position"
        )
        
        # 4. Verify final portfolio state
        updated_portfolio = portfolio_service.get_portfolio(portfolio.id)
        expected_cash = 10000.0 - (50 * 150.0) - (1 * 2800.0)  # -300
        assert updated_portfolio.current_cash == expected_cash
        
        # 5. Check positions
        positions = portfolio_service.get_positions(portfolio.id)
        assert len(positions) == 2
        
        aapl_position = next(p for p in positions if p.ticker == "AAPL")
        assert aapl_position.shares == 50.0
        
        googl_position = next(p for p in positions if p.ticker == "GOOGL")
        assert googl_position.shares == 1.0
        
        # 6. Set stop losses
        portfolio_service.update_stop_loss(portfolio.id, "AAPL", 140.0)
        portfolio_service.update_stop_loss(portfolio.id, "GOOGL", 2600.0)
        
        # 7. Create daily snapshot
        snapshot = portfolio_service.create_daily_snapshot(portfolio.id)
        
        # Expected values with mock prices (AAPL=155, GOOGL=2900)
        expected_aapl_value = 50 * 155.0  # 7750
        expected_googl_value = 1 * 2900.0  # 2900
        expected_total_positions = expected_aapl_value + expected_googl_value  # 10650
        expected_total_equity = updated_portfolio.current_cash + expected_total_positions  # -300 + 10650 = 10350
        
        assert snapshot.total_positions_value == expected_total_positions
        assert snapshot.total_equity == expected_total_equity
        
        # 8. Take some profits (sell partial AAPL)
        sell_trade = portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            ticker="AAPL",
            trade_type="SELL",
            shares=25.0,
            price=160.0,
            reason="Take profits"
        )
        
        # Check realized P&L
        expected_pnl = (160.0 - 150.0) * 25.0  # $250 profit
        assert sell_trade.realized_pnl == expected_pnl
        
        # 9. Verify final state
        final_positions = portfolio_service.get_positions(portfolio.id)
        final_aapl = next(p for p in final_positions if p.ticker == "AAPL")
        assert final_aapl.shares == 25.0  # Remaining shares
        
        final_portfolio = portfolio_service.get_portfolio(portfolio.id)
        expected_final_cash = updated_portfolio.current_cash + (25.0 * 160.0)  # -300 + 4000 = 3700
        assert final_portfolio.current_cash == expected_final_cash
    
    def test_portfolio_performance_tracking(self, portfolio_service):
        """Test portfolio performance tracking over time."""
        # Create portfolio
        portfolio = portfolio_service.create_portfolio(starting_cash=10000.0)
        
        # Execute some trades
        portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            ticker="AAPL",
            trade_type="BUY",
            shares=50.0,
            price=150.0
        )
        
        # Create snapshots over several days
        base_date = datetime(2024, 1, 10, 16, 0, 0)
        snapshots = []
        
        for i in range(5):
            snapshot_date = base_date + timedelta(days=i)
            snapshot = portfolio_service.create_daily_snapshot(
                portfolio.id,
                snapshot_date
            )
            snapshots.append(snapshot)
        
        # Get portfolio history
        history = portfolio_service.get_portfolio_history(portfolio.id)
        assert len(history) >= 5  # At least our 5 + potentially initial snapshot
        
        # Verify history is ordered by date
        for i in range(len(history) - 1):
            assert history[i].snapshot_date <= history[i + 1].snapshot_date
        
        # Test date range filtering
        start_date = base_date + timedelta(days=2)
        end_date = base_date + timedelta(days=4)
        
        filtered_history = portfolio_service.get_portfolio_history(
            portfolio.id,
            start_date,
            end_date
        )
        
        assert len(filtered_history) == 3  # Days 2, 3, 4
    
    def test_trade_history_and_analytics(self, portfolio_service):
        """Test trade history and basic analytics."""
        portfolio = portfolio_service.create_portfolio(starting_cash=20000.0)
        
        # Execute multiple trades
        trades_data = [
            ("AAPL", "BUY", 50.0, 150.0),
            ("GOOGL", "BUY", 5.0, 2800.0),
            ("AAPL", "BUY", 25.0, 155.0),  # Add to position
            ("AAPL", "SELL", 30.0, 160.0),  # Take profits
            ("MSFT", "BUY", 20.0, 350.0),
        ]
        
        executed_trades = []
        for ticker, trade_type, shares, price in trades_data:
            try:
                trade = portfolio_service.execute_trade(
                    portfolio_id=portfolio.id,
                    ticker=ticker,
                    trade_type=trade_type,
                    shares=shares,
                    price=price,
                    reason=f"{trade_type} {ticker}"
                )
                executed_trades.append(trade)
            except ValueError as e:
                # Some trades might fail due to insufficient cash/shares
                print(f"Trade failed: {e}")
        
        # Get complete trade history
        trade_history = portfolio_service.get_trade_history(portfolio.id)
        assert len(trade_history) == len(executed_trades)
        
        # Get AAPL-specific trade history
        aapl_trades = portfolio_service.get_trade_history(portfolio.id, ticker="AAPL")
        aapl_trade_count = len([t for t in executed_trades if t.ticker == "AAPL"])
        assert len(aapl_trades) == aapl_trade_count
        
        # Verify trade ordering (most recent first)
        for i in range(len(trade_history) - 1):
            assert trade_history[i].executed_at >= trade_history[i + 1].executed_at
        
        # Test portfolio summary
        summary = portfolio_service.get_portfolio_summary(portfolio.id)
        
        assert summary["portfolio_id"] == portfolio.id
        assert summary["starting_cash"] == 20000.0
        assert summary["trade_count"] == len(executed_trades)
        assert "total_equity" in summary
        assert "total_return" in summary


@pytest.mark.integration
class TestMarketDataIntegration:
    """Integration tests for market data service."""
    
    def test_market_data_caching(self, db_manager):
        """Test market data caching functionality."""
        market_service = MarketDataService(cache_duration_minutes=1)
        
        # This will use the real trading_script.download_price_data function
        # but we'll mock it to avoid external API calls in tests
        with patch('services.market_data_service.download_price_data') as mock_download:
            # Mock successful data fetch
            import pandas as pd
            mock_df = pd.DataFrame({
                'Open': [150.0],
                'High': [155.0], 
                'Low': [149.0],
                'Close': [153.0],
                'Adj Close': [153.0],
                'Volume': [1000000]
            })
            
            from trading_script import FetchResult
            mock_download.return_value = FetchResult(mock_df, "mock")
            
            # First call should fetch data
            price1 = market_service.get_current_price("AAPL")
            assert price1 == 153.0
            assert mock_download.call_count == 1
            
            # Second call should use cache
            price2 = market_service.get_current_price("AAPL", use_cache=True)
            assert price2 == 153.0
            assert mock_download.call_count == 1  # No additional call
            
            # Call with use_cache=False should fetch fresh data
            price3 = market_service.get_current_price("AAPL", use_cache=False)
            assert price3 == 153.0
            assert mock_download.call_count == 2  # Additional call made
    
    def test_multiple_ticker_pricing(self, db_manager):
        """Test getting prices for multiple tickers."""
        market_service = MarketDataService()
        
        with patch('services.market_data_service.download_price_data') as mock_download:
            import pandas as pd
            from trading_script import FetchResult
            
            # Mock different prices for different tickers
            def side_effect(ticker, **kwargs):
                prices = {"AAPL": 153.0, "GOOGL": 2900.0, "MSFT": 350.0}
                mock_df = pd.DataFrame({
                    'Close': [prices.get(ticker, 100.0)]
                })
                return FetchResult(mock_df, "mock")
            
            mock_download.side_effect = side_effect
            
            tickers = ["AAPL", "GOOGL", "MSFT"]
            prices = market_service.get_multiple_prices(tickers)
            
            assert len(prices) == 3
            assert prices["AAPL"] == 153.0
            assert prices["GOOGL"] == 2900.0
            assert prices["MSFT"] == 350.0
    
    def test_cache_cleanup(self, db_manager):
        """Test market data cache cleanup."""
        market_service = MarketDataService()
        
        # Add some old cached data directly to database
        from database.models import MarketData
        from database.database import db_session_scope
        
        old_date = datetime.now() - timedelta(days=60)
        recent_date = datetime.now() - timedelta(days=5)
        
        with db_session_scope() as session:
            # Add old data
            old_data = MarketData(
                ticker="OLD",
                date=old_date,
                close_price=100.0,
                source="test",
                created_at=old_date
            )
            session.add(old_data)
            
            # Add recent data
            recent_data = MarketData(
                ticker="NEW",
                date=recent_date,
                close_price=200.0,
                source="test",
                created_at=recent_date
            )
            session.add(recent_data)
        
        # Clean up data older than 30 days
        deleted_count = market_service.cleanup_old_cache(days_to_keep=30)
        assert deleted_count == 1  # Should delete the old record
        
        # Verify the recent data is still there
        with db_session_scope() as session:
            remaining = session.query(MarketData).filter(
                MarketData.ticker == "NEW"
            ).first()
            assert remaining is not None
            
            deleted = session.query(MarketData).filter(
                MarketData.ticker == "OLD"
            ).first()
            assert deleted is None


@pytest.mark.performance
class TestPerformance:
    """Performance tests for the system."""
    
    def test_large_portfolio_performance(self, portfolio_service, large_portfolio_data):
        """Test performance with a large number of positions."""
        import time
        
        # Create portfolio
        start_time = time.time()
        portfolio = portfolio_service.create_portfolio(
            starting_cash=large_portfolio_data["starting_cash"]
        )
        creation_time = time.time() - start_time
        
        assert creation_time < 1.0  # Should create portfolio in under 1 second
        
        # Execute many trades (simulate buying all positions)
        start_time = time.time()
        successful_trades = 0
        
        for position_data in large_portfolio_data["positions"][:10]:  # Test with first 10
            try:
                portfolio_service.execute_trade(
                    portfolio_id=portfolio.id,
                    ticker=position_data["ticker"],
                    trade_type="BUY",
                    shares=position_data["shares"],
                    price=position_data["average_cost"]
                )
                successful_trades += 1
            except ValueError:
                # Expected for some trades due to insufficient cash
                pass
        
        execution_time = time.time() - start_time
        
        # Should execute trades reasonably quickly
        avg_time_per_trade = execution_time / max(successful_trades, 1)
        assert avg_time_per_trade < 0.5  # Under 0.5 seconds per trade
        
        # Test snapshot creation performance
        start_time = time.time()
        snapshot = portfolio_service.create_daily_snapshot(portfolio.id)
        snapshot_time = time.time() - start_time
        
        assert snapshot_time < 2.0  # Should create snapshot in under 2 seconds
        assert snapshot is not None
    
    def test_query_performance(self, portfolio_service, sample_portfolio):
        """Test database query performance."""
        import time
        
        # Create many snapshots
        base_date = datetime(2024, 1, 1, 16, 0, 0)
        for i in range(100):  # 100 days of data
            snapshot_date = base_date + timedelta(days=i)
            portfolio_service.create_daily_snapshot(
                sample_portfolio.id,
                snapshot_date
            )
        
        # Test history query performance
        start_time = time.time()
        history = portfolio_service.get_portfolio_history(sample_portfolio.id)
        query_time = time.time() - start_time
        
        assert len(history) >= 100
        assert query_time < 1.0  # Should query history in under 1 second
        
        # Test filtered query performance
        start_time = time.time()
        start_date = base_date + timedelta(days=50)
        end_date = base_date + timedelta(days=75)
        
        filtered_history = portfolio_service.get_portfolio_history(
            sample_portfolio.id,
            start_date,
            end_date
        )
        filtered_query_time = time.time() - start_time
        
        assert len(filtered_history) == 26  # 26 days in range
        assert filtered_query_time < 0.5  # Should be even faster with filtering
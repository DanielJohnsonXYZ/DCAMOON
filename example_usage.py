#!/usr/bin/env python3
"""Example usage of the improved DCAMOON trading system.

This script demonstrates how to use the new database-backed portfolio system.
"""

import logging
from datetime import datetime, timedelta
from database.database import initialize_database
from services.portfolio_service import PortfolioService
from services.market_data_service import MarketDataService
from security.auth import setup_security, get_api_key_manager


def setup_example_logging():
    """Setup logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def example_portfolio_operations():
    """Demonstrate basic portfolio operations."""
    print("\n=== Portfolio Operations Example ===")
    
    # Initialize database (using SQLite for this example)
    db_manager = initialize_database("sqlite:///example.db")
    print(f"Database initialized: {db_manager.get_db_info()}")
    
    # Create services
    market_service = MarketDataService()
    portfolio_service = PortfolioService(market_service)
    
    # Create a new portfolio
    portfolio = portfolio_service.create_portfolio(
        name="Example Portfolio",
        description="Demonstration portfolio",
        starting_cash=10000.0
    )
    print(f"Created portfolio: {portfolio.name} (ID: {portfolio.id})")
    
    # Execute some trades
    print("\nExecuting trades...")
    
    # Buy AAPL
    trade1 = portfolio_service.execute_trade(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        trade_type="BUY",
        shares=50.0,
        price=150.0,
        reason="Growth investment"
    )
    print(f"Trade 1: {trade1.trade_type} {trade1.shares} {trade1.ticker} @ ${trade1.price}")
    
    # Buy GOOGL
    trade2 = portfolio_service.execute_trade(
        portfolio_id=portfolio.id,
        ticker="GOOGL",
        trade_type="BUY", 
        shares=5.0,
        price=2800.0,
        reason="Tech exposure"
    )
    print(f"Trade 2: {trade2.trade_type} {trade2.shares} {trade2.ticker} @ ${trade2.price}")
    
    # Set stop losses
    portfolio_service.update_stop_loss(portfolio.id, "AAPL", 140.0)
    portfolio_service.update_stop_loss(portfolio.id, "GOOGL", 2600.0)
    print("Stop losses set")
    
    # View current positions
    positions = portfolio_service.get_positions(portfolio.id)
    print(f"\nCurrent positions ({len(positions)}):")
    for position in positions:
        print(f"  {position.ticker}: {position.shares} shares @ ${position.average_cost:.2f} avg cost")
        if position.stop_loss:
            print(f"    Stop loss: ${position.stop_loss:.2f}")
    
    # Create daily snapshot
    snapshot = portfolio_service.create_daily_snapshot(portfolio.id)
    print(f"\nPortfolio snapshot created:")
    print(f"  Total equity: ${snapshot.total_equity:.2f}")
    print(f"  Cash balance: ${snapshot.cash_balance:.2f}")
    print(f"  Positions value: ${snapshot.total_positions_value:.2f}")
    
    # Get portfolio summary
    summary = portfolio_service.get_portfolio_summary(portfolio.id)
    print(f"\nPortfolio summary:")
    print(f"  Name: {summary['name']}")
    print(f"  Total equity: ${summary['total_equity']:.2f}")
    print(f"  Total return: ${summary['total_return']:.2f} ({summary['total_return_pct']:.2f}%)")
    print(f"  Positions: {summary['position_count']}")
    print(f"  Trades: {summary['trade_count']}")
    
    return portfolio.id


def example_security_operations():
    """Demonstrate security features."""
    print("\n=== Security Operations Example ===")
    
    # Setup security
    setup_security()
    api_manager = get_api_key_manager()
    
    # Store API keys securely
    print("Storing API keys...")
    api_manager.store_api_key("openai", "sk-example-openai-key-12345")
    api_manager.store_api_key("alpaca", "PK-example-alpaca-key-67890")
    
    # Retrieve API keys
    openai_key = api_manager.get_api_key("openai")
    print(f"Retrieved OpenAI key: {openai_key[:10]}...")
    
    # List stored services
    services = api_manager.list_services()
    print(f"Services with stored keys: {services}")
    
    # Save to file
    api_manager.save_to_file("example_api_keys.json")
    print("API keys saved to file")


def example_migration():
    """Demonstrate data migration from CSV."""
    print("\n=== Migration Example ===")
    
    # This would typically be run with real CSV files
    print("Migration example (would run with real CSV files):")
    print("  python3 migrate.py --portfolio-csv portfolio.csv --trade-log-csv trades.csv --dry-run")
    print("  python3 migrate.py --portfolio-csv portfolio.csv --trade-log-csv trades.csv --backup --validate")


def example_testing():
    """Show how to run tests."""
    print("\n=== Testing Example ===")
    
    print("Running tests:")
    print("  pytest tests/ -v                    # Run all tests")
    print("  pytest tests/test_portfolio.py -v   # Run portfolio tests")
    print("  pytest -m unit                      # Run only unit tests")
    print("  pytest -m integration               # Run only integration tests")
    print("  pytest -m 'not slow'                # Skip slow tests")


def example_performance_comparison():
    """Compare old vs new system performance."""
    print("\n=== Performance Comparison ===")
    
    import time
    
    # Simulate old system (CSV operations)
    print("Old system (CSV-based):")
    start_time = time.time()
    
    # Simulate multiple CSV reads/writes
    for i in range(10):
        # In the old system, each operation would read/write entire CSV
        pass  # Simulated work
    
    old_time = time.time() - start_time
    print(f"  Simulated 10 operations: {old_time:.3f} seconds")
    
    # New system (database operations)
    print("New system (database-based):")
    start_time = time.time()
    
    db_manager = initialize_database("sqlite:///perf_test.db")
    portfolio_service = PortfolioService()
    
    # Create portfolio
    portfolio = portfolio_service.create_portfolio(starting_cash=10000.0)
    
    # Perform 10 operations
    for i in range(5):
        portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            ticker=f"TEST{i}",
            trade_type="BUY",
            shares=10.0,
            price=100.0 + i
        )
        
        portfolio_service.get_portfolio_summary(portfolio.id)
    
    new_time = time.time() - start_time
    print(f"  Real 10 operations: {new_time:.3f} seconds")
    
    speedup = old_time / new_time if new_time > 0 else float('inf')
    print(f"  Performance improvement: {speedup:.1f}x faster")


def main():
    """Run all examples."""
    setup_example_logging()
    
    print("DCAMOON Trading System - Improved Version Examples")
    print("=" * 60)
    
    try:
        # Basic portfolio operations
        portfolio_id = example_portfolio_operations()
        
        # Security features
        example_security_operations()
        
        # Migration example
        example_migration()
        
        # Testing example
        example_testing()
        
        # Performance comparison
        example_performance_comparison()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Run tests: pytest tests/ -v")
        print("3. Migrate your CSV data: python3 migrate.py --help")
        print("4. Start using the new portfolio service in your applications")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
"""Weekly deposit script for DCAMOON trading system.

This script adds a weekly deposit to the portfolio cash balance.
Improved with proper error handling and configuration support.
"""

import pandas as pd
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def add_weekly_deposit(
    csv_path: str = "Scripts and CSV Files/chatgpt_portfolio_update.csv",
    deposit_amount: float = 10.0,
    currency_symbol: str = "$"
) -> bool:
    """Add weekly deposit to portfolio with improved error handling
    
    Args:
        csv_path: Path to portfolio CSV file
        deposit_amount: Amount to deposit
        currency_symbol: Currency symbol for display
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate inputs
        if deposit_amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        csv_file = Path(csv_path)
        if not csv_file.exists():
            logger.error(f"Portfolio file not found: {csv_path}")
            return False
        
        # Load portfolio data
        logger.info(f"Loading portfolio data from {csv_path}")
        df = pd.read_csv(csv_path)
        
        if df.empty:
            logger.error("Portfolio file is empty")
            return False
        
        today = pd.to_datetime(datetime.today().date()).strftime("%Y-%m-%d")
        logger.info(f"Processing deposit for date: {today}")
        
        # Define expected columns
        expected_cols = [
            "Date", "Ticker", "Shares", "Buy Price", "Cost Basis", "Stop Loss", 
            "Action", "Current Price", "Total Value", "PnL", "Cash Balance", "Total Equity"
        ]
        
        # Ensure all expected columns exist
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
                logger.warning(f"Added missing column: {col}")
        
        def ensure_row(ticker: str) -> None:
            """Ensure a row exists for the given ticker and today's date"""
            mask = (df["Date"] == today) & (df["Ticker"] == ticker)
            if not mask.any():
                new_row = {col: "" for col in expected_cols}
                new_row.update({"Date": today, "Ticker": ticker})
                df.loc[len(df)] = new_row
                logger.info(f"Created new row for {ticker}")
        
        # Ensure required rows exist
        ensure_row("CASH")
        ensure_row("TOTAL")
        
        # Add deposit to CASH and TOTAL Cash Balance
        rows_updated = 0
        for ticker in ["CASH", "TOTAL"]:
            mask = (df["Date"] == today) & (df["Ticker"] == ticker)
            if mask.any():
                current_balance = pd.to_numeric(
                    df.loc[mask, "Cash Balance"], 
                    errors="coerce"
                ).fillna(0).iloc[0]
                
                new_balance = current_balance + deposit_amount
                df.loc[mask, "Cash Balance"] = new_balance
                rows_updated += 1
                logger.info(f"Updated {ticker} balance: {current_balance} -> {new_balance}")
        
        if rows_updated == 0:
            logger.warning("No rows were updated")
            return False
        
        # Create backup before saving
        backup_path = csv_file.parent / f"{csv_file.stem}_backup_{today}.csv"
        try:
            df_original = pd.read_csv(csv_path)
            df_original.to_csv(backup_path, index=False)
            logger.info(f"Backup created: {backup_path}")
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")
        
        # Save updated data
        df.to_csv(csv_path, index=False)
        logger.info(f"Portfolio updated successfully")
        
        print(f"{currency_symbol}{deposit_amount} deposit added on {today}")
        return True
        
    except pd.errors.EmptyDataError:
        logger.error("Portfolio CSV file is empty or corrupted")
        return False
    except pd.errors.ParserError as e:
        logger.error(f"Error parsing CSV file: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error adding deposit: {e}")
        return False


def main():
    """Main function with command line argument support"""
    parser = argparse.ArgumentParser(description="Add weekly deposit to DCAMOON portfolio")
    parser.add_argument(
        "--csv-path", 
        default="Scripts and CSV Files/chatgpt_portfolio_update.csv",
        help="Path to portfolio CSV file"
    )
    parser.add_argument(
        "--amount", 
        type=float, 
        default=10.0,
        help="Deposit amount (default: 10.0)"
    )
    parser.add_argument(
        "--currency", 
        default="$",
        help="Currency symbol for display (default: $)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Update logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Execute deposit
    success = add_weekly_deposit(
        csv_path=args.csv_path,
        deposit_amount=args.amount,
        currency_symbol=args.currency
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
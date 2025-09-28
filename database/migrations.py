"""Database migration utilities for DCAMOON trading system.

This module provides functionality to migrate data from the existing
CSV-based storage to the new database structure.
"""

import os
import logging
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from .database import DatabaseManager, db_session_scope
from .models import Portfolio, Position, Trade, PortfolioSnapshot, PositionSnapshot

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages data migration from CSV to database."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def migrate_csv_to_database(
        self,
        portfolio_csv_path: str,
        trade_log_csv_path: str,
        portfolio_name: str = "Migrated Portfolio",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Migrate CSV data to database.
        
        Args:
            portfolio_csv_path: Path to portfolio CSV file
            trade_log_csv_path: Path to trade log CSV file
            portfolio_name: Name for the migrated portfolio
            dry_run: If True, don't actually save to database
            
        Returns:
            Migration summary
        """
        try:
            logger.info("Starting CSV to database migration")
            
            # Validate files exist
            if not os.path.exists(portfolio_csv_path):
                raise FileNotFoundError(f"Portfolio CSV not found: {portfolio_csv_path}")
            if not os.path.exists(trade_log_csv_path):
                raise FileNotFoundError(f"Trade log CSV not found: {trade_log_csv_path}")
            
            # Load and parse CSV data
            portfolio_data = self._load_portfolio_csv(portfolio_csv_path)
            trade_data = self._load_trade_log_csv(trade_log_csv_path)
            
            # Extract portfolio info
            portfolio_info = self._extract_portfolio_info(portfolio_data)
            positions = self._extract_positions(portfolio_data)
            snapshots = self._extract_snapshots(portfolio_data)
            
            if dry_run:
                logger.info("DRY RUN - Migration would create:")
                logger.info(f"  Portfolio: {portfolio_name}")
                logger.info(f"  Positions: {len(positions)}")
                logger.info(f"  Trades: {len(trade_data)}")
                logger.info(f"  Snapshots: {len(snapshots)}")
                
                return {
                    "dry_run": True,
                    "portfolio_name": portfolio_name,
                    "positions_count": len(positions),
                    "trades_count": len(trade_data),
                    "snapshots_count": len(snapshots)
                }
            
            # Perform actual migration
            with db_session_scope() as session:
                # Create portfolio
                portfolio = Portfolio(
                    name=portfolio_name,
                    description="Migrated from CSV data",
                    starting_cash=portfolio_info["starting_cash"],
                    current_cash=portfolio_info["current_cash"]
                )
                session.add(portfolio)
                session.flush()  # Get the ID
                
                # Create positions
                position_objects = []
                for pos_data in positions:
                    position = Position(
                        portfolio_id=portfolio.id,
                        ticker=pos_data["ticker"],
                        shares=pos_data["shares"],
                        average_cost=pos_data["average_cost"],
                        cost_basis=pos_data["cost_basis"],
                        stop_loss=pos_data.get("stop_loss")
                    )
                    session.add(position)
                    position_objects.append(position)
                
                # Create trades
                trade_objects = []
                for trade_data_row in trade_data:
                    trade = Trade(
                        portfolio_id=portfolio.id,
                        ticker=trade_data_row["ticker"],
                        trade_type=trade_data_row["trade_type"],
                        shares=trade_data_row["shares"],
                        price=trade_data_row["price"],
                        total_amount=trade_data_row["total_amount"],
                        execution_type=trade_data_row.get("execution_type", "MARKET"),
                        status="FILLED",
                        reason=trade_data_row.get("reason", "Migrated from CSV"),
                        executed_at=trade_data_row.get("executed_at", datetime.now()),
                        cost_basis=trade_data_row.get("cost_basis"),
                        realized_pnl=trade_data_row.get("realized_pnl")
                    )
                    session.add(trade)
                    trade_objects.append(trade)
                
                # Create snapshots
                snapshot_objects = []
                for snap_data in snapshots:
                    snapshot = PortfolioSnapshot(
                        portfolio_id=portfolio.id,
                        snapshot_date=snap_data["date"],
                        total_equity=snap_data["total_equity"],
                        cash_balance=snap_data["cash_balance"],
                        total_positions_value=snap_data["total_positions_value"],
                        daily_return=snap_data.get("daily_return", 0.0),
                        total_return=snap_data.get("total_return", 0.0),
                        total_return_pct=snap_data.get("total_return_pct", 0.0)
                    )
                    session.add(snapshot)
                    snapshot_objects.append(snapshot)
                
                logger.info(f"Migration completed successfully")
                logger.info(f"Created portfolio: {portfolio.id}")
                logger.info(f"Created {len(position_objects)} positions")
                logger.info(f"Created {len(trade_objects)} trades")
                logger.info(f"Created {len(snapshot_objects)} snapshots")
                
                return {
                    "success": True,
                    "portfolio_id": portfolio.id,
                    "portfolio_name": portfolio.name,
                    "positions_count": len(position_objects),
                    "trades_count": len(trade_objects),
                    "snapshots_count": len(snapshot_objects)
                }
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _load_portfolio_csv(self, csv_path: str) -> pd.DataFrame:
        """Load and validate portfolio CSV."""
        try:
            df = pd.read_csv(csv_path)
            
            # Validate required columns
            required_columns = ["Date", "Ticker", "Shares", "Buy Price", "Cost Basis"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Convert Date column
            df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
            
            # Clean and convert numeric columns
            numeric_columns = ["Shares", "Buy Price", "Cost Basis", "Stop Loss", 
                             "Current Price", "Total Value", "PnL", "Cash Balance", "Total Equity"]
            
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            logger.info(f"Loaded portfolio CSV: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error loading portfolio CSV: {e}")
            raise
    
    def _load_trade_log_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """Load and parse trade log CSV."""
        try:
            df = pd.read_csv(csv_path)
            
            # Convert Date column
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
            
            trades = []
            for _, row in df.iterrows():
                trade_data = self._parse_trade_row(row)
                if trade_data:
                    trades.append(trade_data)
            
            logger.info(f"Loaded trade log CSV: {len(trades)} trades")
            return trades
            
        except Exception as e:
            logger.error(f"Error loading trade log CSV: {e}")
            return []
    
    def _parse_trade_row(self, row: pd.Series) -> Optional[Dict[str, Any]]:
        """Parse a trade row from CSV."""
        try:
            # Determine trade type and shares
            shares_bought = pd.to_numeric(row.get("Shares Bought", 0), errors='coerce') or 0
            shares_sold = pd.to_numeric(row.get("Shares Sold", 0), errors='coerce') or 0
            
            if shares_bought > 0:
                trade_type = "BUY"
                shares = shares_bought
                price = pd.to_numeric(row.get("Buy Price", 0), errors='coerce') or 0
            elif shares_sold > 0:
                trade_type = "SELL"
                shares = shares_sold
                price = pd.to_numeric(row.get("Sell Price", 0), errors='coerce') or 0
            else:
                return None  # No valid trade
            
            if shares <= 0 or price <= 0:
                return None
            
            total_amount = shares * price
            
            trade_data = {
                "ticker": str(row.get("Ticker", "")).upper(),
                "trade_type": trade_type,
                "shares": shares,
                "price": price,
                "total_amount": total_amount,
                "executed_at": row.get("Date", datetime.now()),
                "reason": str(row.get("Reason", "Migrated from CSV")),
                "cost_basis": pd.to_numeric(row.get("Cost Basis", 0), errors='coerce'),
                "realized_pnl": pd.to_numeric(row.get("PnL", 0), errors='coerce')
            }
            
            return trade_data
            
        except Exception as e:
            logger.error(f"Error parsing trade row: {e}")
            return None
    
    def _extract_portfolio_info(self, df: pd.DataFrame) -> Dict[str, float]:
        """Extract portfolio-level information."""
        # Get latest TOTAL row for current cash
        total_rows = df[df["Ticker"] == "TOTAL"]
        if not total_rows.empty:
            latest_total = total_rows.iloc[-1]
            current_cash = pd.to_numeric(latest_total.get("Cash Balance", 0), errors='coerce') or 0
        else:
            current_cash = 0.0
        
        # Estimate starting cash (this is a rough estimate)
        # In a real migration, you'd want to calculate this more precisely
        starting_cash = max(current_cash, 100.0)  # Default minimum
        
        return {
            "starting_cash": starting_cash,
            "current_cash": current_cash
        }
    
    def _extract_positions(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract current positions from CSV."""
        # Get latest non-TOTAL rows grouped by ticker
        position_rows = df[df["Ticker"] != "TOTAL"].copy()
        
        if position_rows.empty:
            return []
        
        # Get the latest entry for each ticker
        latest_positions = position_rows.groupby("Ticker").last().reset_index()
        
        positions = []
        for _, row in latest_positions.iterrows():
            shares = pd.to_numeric(row.get("Shares", 0), errors='coerce') or 0
            
            # Only include if there are actual shares
            if shares > 0:
                cost_basis = pd.to_numeric(row.get("Cost Basis", 0), errors='coerce') or 0
                average_cost = (cost_basis / shares) if shares > 0 else 0
                stop_loss = pd.to_numeric(row.get("Stop Loss", 0), errors='coerce')
                
                position = {
                    "ticker": str(row["Ticker"]).upper(),
                    "shares": shares,
                    "average_cost": average_cost,
                    "cost_basis": cost_basis,
                    "stop_loss": stop_loss if stop_loss and stop_loss > 0 else None
                }
                positions.append(position)
        
        return positions
    
    def _extract_snapshots(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract portfolio snapshots from CSV."""
        # Get all TOTAL rows for historical snapshots
        total_rows = df[df["Ticker"] == "TOTAL"].copy()
        
        if total_rows.empty:
            return []
        
        snapshots = []
        for _, row in total_rows.iterrows():
            if pd.isna(row["Date"]):
                continue
            
            total_equity = pd.to_numeric(row.get("Total Equity", 0), errors='coerce') or 0
            cash_balance = pd.to_numeric(row.get("Cash Balance", 0), errors='coerce') or 0
            total_value = pd.to_numeric(row.get("Total Value", 0), errors='coerce') or 0
            
            # Calculate positions value
            total_positions_value = total_equity - cash_balance
            
            snapshot = {
                "date": row["Date"],
                "total_equity": total_equity,
                "cash_balance": cash_balance,
                "total_positions_value": max(total_positions_value, 0),
            }
            snapshots.append(snapshot)
        
        # Sort by date
        snapshots.sort(key=lambda x: x["date"])
        
        # Calculate returns
        for i, snapshot in enumerate(snapshots):
            if i == 0:
                snapshot["daily_return"] = 0.0
                snapshot["total_return"] = 0.0
                snapshot["total_return_pct"] = 0.0
            else:
                prev_equity = snapshots[i-1]["total_equity"]
                if prev_equity > 0:
                    daily_return = ((snapshot["total_equity"] - prev_equity) / prev_equity) * 100
                    snapshot["daily_return"] = daily_return
                else:
                    snapshot["daily_return"] = 0.0
                
                # Total return from first snapshot
                first_equity = snapshots[0]["total_equity"]
                if first_equity > 0:
                    total_return = snapshot["total_equity"] - first_equity
                    total_return_pct = (total_return / first_equity) * 100
                    snapshot["total_return"] = total_return
                    snapshot["total_return_pct"] = total_return_pct
                else:
                    snapshot["total_return"] = 0.0
                    snapshot["total_return_pct"] = 0.0
        
        return snapshots
    
    def backup_csv_files(self, portfolio_csv_path: str, trade_log_csv_path: str, backup_dir: str = "backups") -> Dict[str, str]:
        """Create backups of CSV files before migration."""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            backups = {}
            
            # Backup portfolio CSV
            if os.path.exists(portfolio_csv_path):
                portfolio_backup = backup_path / f"portfolio_backup_{timestamp}.csv"
                import shutil
                shutil.copy2(portfolio_csv_path, portfolio_backup)
                backups["portfolio"] = str(portfolio_backup)
                logger.info(f"Portfolio CSV backed up to: {portfolio_backup}")
            
            # Backup trade log CSV
            if os.path.exists(trade_log_csv_path):
                trade_backup = backup_path / f"trade_log_backup_{timestamp}.csv"
                shutil.copy2(trade_log_csv_path, trade_backup)
                backups["trade_log"] = str(trade_backup)
                logger.info(f"Trade log CSV backed up to: {trade_backup}")
            
            return backups
            
        except Exception as e:
            logger.error(f"Error creating backups: {e}")
            raise
    
    def validate_migration(self, portfolio_id: str, original_csv_path: str) -> Dict[str, Any]:
        """Validate that migration was successful by comparing data."""
        try:
            # Load original CSV
            original_df = pd.read_csv(original_csv_path)
            
            # Get migrated data from database
            with db_session_scope() as session:
                portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
                if not portfolio:
                    return {"valid": False, "error": "Portfolio not found in database"}
                
                positions = session.query(Position).filter(Position.portfolio_id == portfolio_id).all()
                snapshots = session.query(PortfolioSnapshot).filter(
                    PortfolioSnapshot.portfolio_id == portfolio_id
                ).all()
            
            # Validation checks
            validation_results = {
                "valid": True,
                "checks": {},
                "warnings": []
            }
            
            # Check position count
            original_positions = len(original_df[original_df["Ticker"] != "TOTAL"]["Ticker"].unique())
            migrated_positions = len(positions)
            validation_results["checks"]["position_count"] = {
                "original": original_positions,
                "migrated": migrated_positions,
                "match": original_positions == migrated_positions
            }
            
            # Check snapshot count
            original_snapshots = len(original_df[original_df["Ticker"] == "TOTAL"])
            migrated_snapshots = len(snapshots)
            validation_results["checks"]["snapshot_count"] = {
                "original": original_snapshots,
                "migrated": migrated_snapshots,
                "match": original_snapshots == migrated_snapshots
            }
            
            # Check latest total equity
            total_rows = original_df[original_df["Ticker"] == "TOTAL"]
            if not total_rows.empty:
                original_equity = pd.to_numeric(total_rows.iloc[-1].get("Total Equity", 0), errors='coerce') or 0
                if snapshots:
                    latest_snapshot = max(snapshots, key=lambda s: s.snapshot_date)
                    migrated_equity = latest_snapshot.total_equity
                    equity_match = abs(original_equity - migrated_equity) < 0.01  # Allow small rounding differences
                    
                    validation_results["checks"]["total_equity"] = {
                        "original": original_equity,
                        "migrated": migrated_equity,
                        "match": equity_match
                    }
                    
                    if not equity_match:
                        validation_results["valid"] = False
            
            logger.info(f"Migration validation completed: {'PASSED' if validation_results['valid'] else 'FAILED'}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating migration: {e}")
            return {"valid": False, "error": str(e)}
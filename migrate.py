#!/usr/bin/env python3
"""Migration script for DCAMOON trading system.

This script migrates data from CSV files to the new database structure.
"""

import argparse
import logging
import sys
from pathlib import Path

from database.database import initialize_database
from database.migrations import MigrationManager


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('migration.log')
        ]
    )


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate DCAMOON CSV data to database")
    
    parser.add_argument(
        "--portfolio-csv",
        required=True,
        help="Path to portfolio CSV file"
    )
    parser.add_argument(
        "--trade-log-csv", 
        required=True,
        help="Path to trade log CSV file"
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (default: sqlite:///dcamoon.db)"
    )
    parser.add_argument(
        "--portfolio-name",
        default="Migrated Portfolio",
        help="Name for the migrated portfolio"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without saving to database"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup of CSV files before migration"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate migration after completion"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting DCAMOON migration")
        logger.info(f"Portfolio CSV: {args.portfolio_csv}")
        logger.info(f"Trade log CSV: {args.trade_log_csv}")
        logger.info(f"Dry run: {args.dry_run}")
        
        # Validate input files
        portfolio_path = Path(args.portfolio_csv)
        trade_log_path = Path(args.trade_log_csv)
        
        if not portfolio_path.exists():
            logger.error(f"Portfolio CSV file not found: {args.portfolio_csv}")
            return 1
            
        if not trade_log_path.exists():
            logger.error(f"Trade log CSV file not found: {args.trade_log_csv}")
            return 1
        
        # Initialize database
        db_manager = initialize_database(
            database_url=args.database_url,
            create_tables=True
        )
        
        logger.info(f"Database initialized: {db_manager.get_db_info()}")
        
        # Create migration manager
        migration_manager = MigrationManager(db_manager)
        
        # Create backups if requested
        if args.backup and not args.dry_run:
            logger.info("Creating backups of CSV files")
            backups = migration_manager.backup_csv_files(
                str(portfolio_path),
                str(trade_log_path)
            )
            logger.info(f"Backups created: {backups}")
        
        # Perform migration
        logger.info("Starting migration")
        result = migration_manager.migrate_csv_to_database(
            portfolio_csv_path=str(portfolio_path),
            trade_log_csv_path=str(trade_log_path),
            portfolio_name=args.portfolio_name,
            dry_run=args.dry_run
        )
        
        if result.get("success", False) or result.get("dry_run", False):
            logger.info("Migration completed successfully")
            
            if not args.dry_run:
                portfolio_id = result["portfolio_id"]
                logger.info(f"Created portfolio ID: {portfolio_id}")
                logger.info(f"Positions created: {result['positions_count']}")
                logger.info(f"Trades created: {result['trades_count']}")
                logger.info(f"Snapshots created: {result['snapshots_count']}")
                
                # Validate migration if requested
                if args.validate:
                    logger.info("Validating migration")
                    validation = migration_manager.validate_migration(
                        portfolio_id,
                        str(portfolio_path)
                    )
                    
                    if validation["valid"]:
                        logger.info("Migration validation PASSED")
                    else:
                        logger.error("Migration validation FAILED")
                        logger.error(f"Validation error: {validation.get('error', 'Unknown')}")
                        return 1
            else:
                logger.info("Dry run completed - no data was saved")
                logger.info(f"Would create:")
                logger.info(f"  - Positions: {result['positions_count']}")
                logger.info(f"  - Trades: {result['trades_count']}")
                logger.info(f"  - Snapshots: {result['snapshots_count']}")
        else:
            logger.error("Migration failed")
            logger.error(f"Error: {result.get('error', 'Unknown error')}")
            return 1
        
        logger.info("Migration process completed")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
"""
Portfolio Helper Utilities

Provides centralized access to portfolio configuration
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_default_portfolio_id() -> str:
    """
    Get the default portfolio ID from environment variable or database.

    Returns:
        str: Portfolio ID (UUID)

    Raises:
        ValueError: If no portfolio ID is configured
    """
    # First, try environment variable
    portfolio_id = os.getenv('DCAMOON_PORTFOLIO_ID')

    if portfolio_id:
        logger.debug(f"Using portfolio ID from environment: {portfolio_id}")
        return portfolio_id

    # If not set, try to get the first portfolio from database
    try:
        from database.database import db_session_scope
        from database.models import Portfolio

        with db_session_scope() as session:
            portfolio = session.query(Portfolio).first()
            if portfolio:
                logger.info(f"Using first portfolio from database: {portfolio.id} ({portfolio.name})")
                return portfolio.id
    except Exception as e:
        logger.warning(f"Could not query database for portfolio: {e}")

    # Fallback to the migrated portfolio (backwards compatibility)
    # This is the UUID from the original migration
    default_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
    logger.warning(f"No DCAMOON_PORTFOLIO_ID set in environment, using default: {default_id}")
    logger.warning("Set DCAMOON_PORTFOLIO_ID in your .env file to customize")

    return default_id


def require_portfolio_id(portfolio_id: Optional[str] = None) -> str:
    """
    Ensure a valid portfolio ID is available.

    Args:
        portfolio_id: Optional portfolio ID to validate

    Returns:
        str: Valid portfolio ID

    Raises:
        ValueError: If portfolio ID is invalid or not found
    """
    if portfolio_id:
        # Validate format (basic UUID check)
        if len(portfolio_id) == 36 and portfolio_id.count('-') == 4:
            return portfolio_id
        else:
            raise ValueError(f"Invalid portfolio ID format: {portfolio_id}")

    return get_default_portfolio_id()

"""Market data service for DCAMOON trading system.

This service handles fetching, caching, and serving market data
from various sources with intelligent fallback mechanisms.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import MarketData
from database.database import db_session_scope

# Import existing market data functions
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from trading_script import download_price_data, FetchResult

logger = logging.getLogger(__name__)


class MarketDataService:
    """Service for market data operations with caching."""
    
    def __init__(self, cache_duration_minutes: int = 15):
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
    
    def get_current_price(self, ticker: str, use_cache: bool = True) -> Optional[float]:
        """Get current price for a ticker with caching.
        
        Args:
            ticker: Stock ticker symbol
            use_cache: Whether to use cached data if available
            
        Returns:
            Current price or None if unavailable
        """
        ticker = ticker.upper()
        
        try:
            # Check cache first
            if use_cache:
                cached_price = self._get_cached_price(ticker)
                if cached_price is not None:
                    return cached_price
            
            # Fetch fresh data
            fetch_result = download_price_data(ticker, period="1d")
            
            if not fetch_result.df.empty:
                current_price = float(fetch_result.df['Close'].iloc[-1])
                
                # Cache the result
                self._cache_market_data(ticker, fetch_result, datetime.now())
                
                logger.debug(f"Fetched current price for {ticker}: ${current_price:.2f}")
                return current_price
            else:
                logger.warning(f"No market data available for {ticker}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting current price for {ticker}: {e}")
            return None
    
    def get_historical_data(
        self, 
        ticker: str, 
        start_date: datetime, 
        end_date: datetime,
        use_cache: bool = True
    ) -> Optional[FetchResult]:
        """Get historical market data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date for data
            end_date: End date for data
            use_cache: Whether to use cached data if available
            
        Returns:
            FetchResult with historical data or None
        """
        ticker = ticker.upper()
        
        try:
            # For simplicity, we'll fetch fresh data for historical requests
            # In production, you might want to implement more sophisticated caching
            fetch_result = download_price_data(
                ticker, 
                start=start_date, 
                end=end_date
            )
            
            if not fetch_result.df.empty:
                # Cache the daily data points
                for date, row in fetch_result.df.iterrows():
                    if isinstance(date, str):
                        date = datetime.strptime(date, '%Y-%m-%d')
                    elif hasattr(date, 'to_pydatetime'):
                        date = date.to_pydatetime()
                    
                    self._cache_daily_data(ticker, date, row, fetch_result.source)
                
                logger.info(f"Fetched historical data for {ticker}: {len(fetch_result.df)} days")
                return fetch_result
            else:
                logger.warning(f"No historical data available for {ticker}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting historical data for {ticker}: {e}")
            return None
    
    def get_multiple_prices(self, tickers: List[str], use_cache: bool = True) -> Dict[str, Optional[float]]:
        """Get current prices for multiple tickers.
        
        Args:
            tickers: List of ticker symbols
            use_cache: Whether to use cached data if available
            
        Returns:
            Dictionary mapping tickers to current prices
        """
        prices = {}
        
        for ticker in tickers:
            prices[ticker] = self.get_current_price(ticker, use_cache)
        
        return prices
    
    def _get_cached_price(self, ticker: str) -> Optional[float]:
        """Get cached current price if recent enough."""
        try:
            cutoff_time = datetime.now() - self.cache_duration
            
            with db_session_scope() as session:
                recent_data = session.query(MarketData).filter(
                    MarketData.ticker == ticker,
                    MarketData.created_at >= cutoff_time
                ).order_by(desc(MarketData.created_at)).first()
                
                if recent_data and recent_data.close_price:
                    logger.debug(f"Using cached price for {ticker}: ${recent_data.close_price:.2f}")
                    return recent_data.close_price
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting cached price for {ticker}: {e}")
            return None
    
    def _cache_market_data(self, ticker: str, fetch_result: FetchResult, fetch_time: datetime) -> None:
        """Cache market data from fetch result."""
        try:
            if fetch_result.df.empty:
                return
            
            # Get the most recent data point
            latest_data = fetch_result.df.iloc[-1]
            latest_date = fetch_result.df.index[-1]
            
            if isinstance(latest_date, str):
                latest_date = datetime.strptime(latest_date, '%Y-%m-%d')
            elif hasattr(latest_date, 'to_pydatetime'):
                latest_date = latest_date.to_pydatetime()
            
            self._cache_daily_data(ticker, latest_date, latest_data, fetch_result.source)
            
        except Exception as e:
            logger.error(f"Error caching market data for {ticker}: {e}")
    
    def _cache_daily_data(self, ticker: str, date: datetime, data_row: Any, source: str) -> None:
        """Cache a single day's market data."""
        try:
            with db_session_scope() as session:
                # Check if data already exists for this ticker/date
                existing = session.query(MarketData).filter(
                    MarketData.ticker == ticker,
                    MarketData.date == date.replace(hour=0, minute=0, second=0, microsecond=0)
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open_price = float(data_row.get('Open', 0))
                    existing.high_price = float(data_row.get('High', 0))
                    existing.low_price = float(data_row.get('Low', 0))
                    existing.close_price = float(data_row.get('Close', 0))
                    existing.adjusted_close = float(data_row.get('Adj Close', data_row.get('Close', 0)))
                    existing.volume = int(data_row.get('Volume', 0))
                    existing.source = source
                else:
                    # Create new record
                    market_data = MarketData(
                        ticker=ticker,
                        date=date.replace(hour=0, minute=0, second=0, microsecond=0),
                        open_price=float(data_row.get('Open', 0)),
                        high_price=float(data_row.get('High', 0)),
                        low_price=float(data_row.get('Low', 0)),
                        close_price=float(data_row.get('Close', 0)),
                        adjusted_close=float(data_row.get('Adj Close', data_row.get('Close', 0))),
                        volume=int(data_row.get('Volume', 0)),
                        source=source
                    )
                    session.add(market_data)
                
        except Exception as e:
            logger.error(f"Error caching daily data for {ticker} on {date}: {e}")
    
    def get_cached_data(
        self, 
        ticker: str, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[MarketData]:
        """Get cached market data for a ticker and date range."""
        try:
            with db_session_scope() as session:
                query = session.query(MarketData).filter(
                    MarketData.ticker == ticker.upper()
                )
                
                if start_date:
                    query = query.filter(MarketData.date >= start_date)
                if end_date:
                    query = query.filter(MarketData.date <= end_date)
                
                data = query.order_by(MarketData.date).all()
                return data
                
        except Exception as e:
            logger.error(f"Error getting cached data for {ticker}: {e}")
            return []
    
    def cleanup_old_cache(self, days_to_keep: int = 30) -> int:
        """Clean up old cached market data.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with db_session_scope() as session:
                deleted_count = session.query(MarketData).filter(
                    MarketData.created_at < cutoff_date
                ).delete()
                
                logger.info(f"Cleaned up {deleted_count} old market data records")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up market data cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            with db_session_scope() as session:
                total_records = session.query(MarketData).count()
                
                unique_tickers = session.query(MarketData.ticker).distinct().count()
                
                oldest_record = session.query(MarketData).order_by(MarketData.date).first()
                newest_record = session.query(MarketData).order_by(desc(MarketData.date)).first()
                
                stats = {
                    "total_records": total_records,
                    "unique_tickers": unique_tickers,
                    "cache_duration_minutes": self.cache_duration.total_seconds() / 60,
                    "oldest_data": oldest_record.date if oldest_record else None,
                    "newest_data": newest_record.date if newest_record else None
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "total_records": 0,
                "unique_tickers": 0,
                "cache_duration_minutes": self.cache_duration.total_seconds() / 60,
                "oldest_data": None,
                "newest_data": None,
                "error": str(e)
            }
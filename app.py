"""
Flask Web Interface for ChatGPT Micro-Cap Trading Experiment

This web interface provides:
- Portfolio status and performance visualization
- Trading history and logs
- Automated trading controls
- Performance charts and analytics
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import json
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
import time
from dataclasses import dataclass
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from typing import Dict, Any, Optional, Tuple

# Import new database services
from database.database import initialize_database, db_session_scope
from services.portfolio_service import PortfolioService
from services.market_data_service import MarketDataService
from utils.portfolio_helper import get_default_portfolio_id
from utils.startup import run_startup_checks, print_startup_banner, StartupError

app = Flask(__name__)
CORS(app)

# Run startup validation
try:
    run_startup_checks(require_openai=False, require_database=True)
except StartupError as e:
    logger.critical(f"Startup validation failed:\n{e}")
    print(f"\nERROR: {e}\n")
    print("Please fix the configuration issues and try again.")
    exit(1)

# Initialize database and services
db_manager = initialize_database()
market_service = MarketDataService()
portfolio_service = PortfolioService(market_service)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DURATION = 30  # seconds

@dataclass
class CachedData:
    """Cached portfolio data with timestamp"""
    data: Dict[str, Any]
    timestamp: float
    file_mtime: float
    
    def is_valid(self, file_mtime: float) -> bool:
        """Check if cached data is still valid"""
        current_time = time.time()
        return (
            current_time - self.timestamp < CACHE_DURATION and
            self.file_mtime == file_mtime
        )

# Global cache
_portfolio_cache: Optional[CachedData] = None
_chart_cache: Optional[Tuple[str, float]] = None

# Configuration
DATA_DIRS = {
    'live': 'Scripts and CSV Files',
    'template': 'Start Your Own'
}

def get_portfolio_data(data_dir: str = 'Scripts and CSV Files') -> Dict[str, Any]:
    """Load portfolio data from CSV files with caching and improved error handling"""
    global _portfolio_cache
    
    portfolio_file = os.path.join(data_dir, 'chatgpt_portfolio_update.csv')
    trade_log_file = os.path.join(data_dir, 'chatgpt_trade_log.csv')
    
    # Check file modification times for cache validation
    portfolio_mtime = os.path.getmtime(portfolio_file) if os.path.exists(portfolio_file) else 0
    trade_mtime = os.path.getmtime(trade_log_file) if os.path.exists(trade_log_file) else 0
    combined_mtime = max(portfolio_mtime, trade_mtime)
    
    # Check if we can use cached data
    if _portfolio_cache and _portfolio_cache.is_valid(combined_mtime):
        logger.debug("Using cached portfolio data")
        return _portfolio_cache.data
    
    logger.info("Loading fresh portfolio data (cache miss or expired)")
    
    portfolio_data: Dict[str, Any] = {
        'portfolio': [],
        'trades': [],
        'total_equity': 0.0,
        'cash_balance': 0.0,
        'total_trades': 0,
        'last_updated': 'Unknown'
    }
    
    # Load portfolio updates
    try:
        if os.path.exists(portfolio_file):
            portfolio_df = pd.read_csv(portfolio_file)
            
            # Optimize: Only process TOTAL rows for summary stats
            total_rows = portfolio_df[portfolio_df['Ticker'] == 'TOTAL']
            if not total_rows.empty:
                latest_total = total_rows.iloc[-1]
                # Convert to numeric values with better error handling
                portfolio_data['total_equity'] = pd.to_numeric(
                    latest_total.get('Total Equity', 0), errors='coerce'
                ) or 0.0
                portfolio_data['cash_balance'] = pd.to_numeric(
                    latest_total.get('Cash Balance', 0), errors='coerce'
                ) or 0.0
                portfolio_data['last_updated'] = latest_total.get('Date', 'Unknown')
            
            # Convert to records only when needed (lighter memory footprint)
            portfolio_data['portfolio'] = portfolio_df.to_dict('records')
        else:
            logger.warning(f"Portfolio file not found: {portfolio_file}")
    except Exception as e:
        logger.error(f"Error loading portfolio data: {e}")
    
    # Load trade log
    try:
        if os.path.exists(trade_log_file):
            trades_df = pd.read_csv(trade_log_file)
            portfolio_data['trades'] = trades_df.to_dict('records')
            portfolio_data['total_trades'] = len(trades_df)
        else:
            logger.warning(f"Trade log file not found: {trade_log_file}")
    except Exception as e:
        logger.error(f"Error loading trade log: {e}")
    
    # Cache the result
    _portfolio_cache = CachedData(
        data=portfolio_data,
        timestamp=time.time(),
        file_mtime=combined_mtime
    )
    
    return portfolio_data

def create_database_performance_chart(portfolio_id: str) -> Optional[str]:
    """Create performance chart from database data"""
    try:
        with db_session_scope() as session:
            from database.models import PortfolioSnapshot
            from sqlalchemy import desc
            
            # Get all snapshots for the portfolio
            snapshots = session.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == portfolio_id
            ).order_by(PortfolioSnapshot.snapshot_date).all()
            
            if not snapshots:
                logger.warning(f"No snapshots found for portfolio {portfolio_id}")
                return None
            
            # Extract data for plotting
            dates = [snap.snapshot_date for snap in snapshots]
            values = [float(snap.total_equity) for snap in snapshots]
            
            # Create the plot
            plt.figure(figsize=(12, 6))
            plt.plot(dates, values, label='DCAMOON Portfolio', linewidth=2, color='#2E86AB')
            
            # Add starting baseline
            starting_value = 100
            plt.axhline(y=starting_value, color='gray', linestyle='--', alpha=0.7, 
                       label='Starting Value (£100)')
            
            plt.title('DCAMOON Portfolio Performance', fontsize=16, fontweight='bold')
            plt.xlabel('Date')
            plt.ylabel('Portfolio Value (£)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            plot_data = buffer.getvalue()
            buffer.close()
            plt.close()
            
            return base64.b64encode(plot_data).decode()
            
    except Exception as e:
        logger.error(f"Error creating database chart: {e}")
        return None

def create_performance_chart() -> Optional[str]:
    """Create performance chart with caching and improved error handling"""
    global _chart_cache
    
    try:
        portfolio_file = os.path.join('Scripts and CSV Files', 'chatgpt_portfolio_update.csv')
        
        if not os.path.exists(portfolio_file):
            logger.warning(f"Portfolio file not found: {portfolio_file}")
            return None
        
        # Check if we can use cached chart
        file_mtime = os.path.getmtime(portfolio_file)
        if _chart_cache and (time.time() - _chart_cache[1] < CACHE_DURATION):
            logger.debug("Using cached performance chart")
            return _chart_cache[0]
            
        logger.info("Creating fresh performance chart")
        df = pd.read_csv(portfolio_file)
        
        # Optimize: Only load TOTAL rows
        total_rows = df[df['Ticker'] == 'TOTAL'].copy()
        
        if total_rows.empty:
            logger.warning("No TOTAL rows found in portfolio data")
            return None
        
        # Data cleaning and validation
        total_rows['Date'] = pd.to_datetime(total_rows['Date'], errors='coerce')
        total_rows['Total Equity'] = pd.to_numeric(total_rows['Total Equity'], errors='coerce')
        
        # Remove invalid data
        valid_data = total_rows.dropna(subset=['Date', 'Total Equity']).sort_values('Date')
        
        if valid_data.empty:
            logger.warning("No valid data found for chart")
            return None
        
        # Create optimized plot
        plt.figure(figsize=(12, 6))
        
        plt.plot(valid_data['Date'], valid_data['Total Equity'], 
                label='ChatGPT Portfolio', linewidth=2, color='#2E86AB')
        
        # Add starting baseline
        starting_value = 100
        plt.axhline(y=starting_value, color='gray', linestyle='--', alpha=0.7, 
                   label='Starting Value ($100)')
        
        plt.title('ChatGPT Micro-Cap Portfolio Performance', fontsize=16, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Portfolio Value ($)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Convert plot to base64 string
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plot_data = buffer.getvalue()
        buffer.close()
        plt.close()
        
        # Cache the result
        chart_b64 = base64.b64encode(plot_data).decode()
        _chart_cache = (chart_b64, time.time())
        
        logger.info("Performance chart created and cached successfully")
        return chart_b64
        
    except Exception as e:
        logger.error(f"Error creating chart: {e}")
        return None

@app.route('/')
def index():
    """Serve the React frontend"""
    return send_file('frontend/public/index.html')

@app.route('/api/portfolio')
def api_portfolio():
    """API endpoint for portfolio data"""
    try:
        # Get the default portfolio from environment or database
        portfolio_id = get_default_portfolio_id()
        summary = portfolio_service.get_portfolio_summary(portfolio_id)
        positions = portfolio_service.get_positions(portfolio_id)
        
        return jsonify({
            'portfolio': summary,
            'positions': [{
                'ticker': pos.ticker,
                'shares': float(pos.shares),
                'average_cost': float(pos.average_cost),
                'current_value': float(pos.shares * pos.average_cost),  # Will update with real prices
                'stop_loss': float(pos.stop_loss) if pos.stop_loss else None
            } for pos in positions],
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error fetching portfolio data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/chart')
def api_chart():
    """API endpoint for performance chart"""
    try:
        portfolio_id = get_default_portfolio_id()
        chart_data = create_database_performance_chart(portfolio_id)
        return jsonify({'chart': chart_data, 'status': 'success'})
    except Exception as e:
        logger.error(f"Error creating chart: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/trades')
def api_trades():
    """API endpoint for trade history"""
    try:
        portfolio_id = get_default_portfolio_id()

        with db_session_scope() as session:
            from database.models import Trade
            from sqlalchemy import desc
            
            trades = session.query(Trade).filter(
                Trade.portfolio_id == portfolio_id
            ).order_by(desc(Trade.trade_date)).limit(50).all()
            
            trade_data = [{
                'id': trade.id,
                'date': trade.trade_date.isoformat(),
                'ticker': trade.ticker,
                'action': trade.trade_type,
                'shares': float(trade.shares),
                'price': float(trade.price),
                'total_amount': float(trade.shares * trade.price),
                'reason': trade.reason or ''
            } for trade in trades]
            
            return jsonify({
                'trades': trade_data,
                'total_count': len(trade_data),
                'status': 'success'
            })
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/execute-trade', methods=['POST'])
def api_execute_trade():
    """API endpoint to execute a trade"""
    try:
        data = request.get_json()
        portfolio_id = get_default_portfolio_id()

        # Validate required fields
        required_fields = ['ticker', 'trade_type', 'shares', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Execute the trade
        trade = portfolio_service.execute_trade(
            portfolio_id=portfolio_id,
            ticker=data['ticker'].upper(),
            trade_type=data['trade_type'].upper(),
            shares=float(data['shares']),
            price=float(data['price']),
            reason=data.get('reason', 'Web interface trade')
        )
        
        return jsonify({
            'status': 'success',
            'message': f"Trade executed: {data['trade_type']} {data['shares']} {data['ticker']}",
            'trade_id': trade.id
        })
        
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/current-prices')
def api_current_prices():
    """API endpoint for current stock prices"""
    try:
        tickers = request.args.get('tickers', '').split(',')
        tickers = [t.strip().upper() for t in tickers if t.strip()]
        
        if not tickers:
            return jsonify({'status': 'error', 'message': 'No tickers provided'}), 400
        
        prices = {}
        for ticker in tickers:
            try:
                price = market_service.get_current_price(ticker)
                prices[ticker] = price
            except Exception as e:
                logger.warning(f"Could not fetch price for {ticker}: {e}")
                prices[ticker] = None
        
        return jsonify({
            'prices': prices,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/portfolio')
def portfolio():
    """Portfolio details page"""
    portfolio_data = get_portfolio_data()
    return render_template('portfolio.html', data=portfolio_data)

@app.route('/trades')
def trades():
    """Trading history page"""
    portfolio_data = get_portfolio_data()
    return render_template('trades.html', data=portfolio_data)

@app.route('/automation')
def automation():
    """Automation controls page"""
    return render_template('automation.html')

@app.route('/api/run-automation', methods=['POST'])
def run_automation():
    """API endpoint to trigger automated trading with improved error handling"""
    try:
        logger.info("Automation endpoint called")
        request_data = request.get_json() if request.is_json else {}
        
        # Validate request
        api_key = request_data.get('api_key') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'status': 'error',
                'message': 'OpenAI API key required. Set OPENAI_API_KEY environment variable or provide in request.'
            }), 400
        
        # TODO: Integrate with simple_automation.py script
        # This would call the actual automation logic
        logger.info("Automation would be triggered here")
        
        return jsonify({
            'status': 'success',
            'message': 'Automation feature ready - integration pending'
        })
    except Exception as e:
        logger.error(f"Error in automation endpoint: {e}")
        return jsonify({
            'status': 'error', 
            'message': f'Automation failed: {str(e)}'
        }), 500

# Template directory
app.template_folder = 'templates'

if __name__ == '__main__':
    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)

    # Print startup banner
    print_startup_banner("DCAMOON Dashboard", "1.0.0")

    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() in ['true', '1', 'yes']

    if debug:
        logger.warning("Running in DEBUG mode - not recommended for production!")

    print(f"\n✓ Server starting on http://0.0.0.0:{port}")
    print(f"✓ Dashboard will display trading results and portfolio performance\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
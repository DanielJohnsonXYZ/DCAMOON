#!/usr/bin/env python3
"""
DCAMOON Autonomous Trading Platform
"""

from flask import Flask, jsonify, send_file
from flask_cors import CORS
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database services
from database.database import initialize_database
from services.portfolio_service import PortfolioService
from services.research_service import ResearchService
from services.autonomous_trader import AutonomousTrader, AutonomousConfig

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
try:
    logger.info("Initializing database and services...")
    db_manager = initialize_database()
    portfolio_service = PortfolioService()
    research_service = ResearchService()
    
    # Initialize autonomous trader
    autonomous_config = AutonomousConfig(
        max_position_size=0.50,  # 50% max position
        crypto_allocation=0.20,  # 20% crypto
        min_confidence=0.60      # 60% minimum confidence
    )
    autonomous_trader = AutonomousTrader('c49d9e6f-a4c2-4524-81d1-96a8e5672d52', autonomous_config)
    
    logger.info("Services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise

@app.route('/')
def index():
    """Serve the React frontend"""
    try:
        return send_file('frontend/public/index.html')
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        return f"Error: {e}", 500

@app.route('/api/portfolio')
def api_portfolio():
    """API endpoint for portfolio data"""
    try:
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
        from database.database import db_session_scope
        from database.models import Portfolio, Position
        
        with db_session_scope() as session:
            # Get portfolio
            portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            if not portfolio:
                return jsonify({'status': 'error', 'message': 'Portfolio not found'}), 404
            
            # Get positions
            positions = session.query(Position).filter(Position.portfolio_id == portfolio_id).all()
            
            # Build response data within session
            portfolio_data = {
                'portfolio_id': portfolio.id,
                'name': portfolio.name,
                'created_at': portfolio.created_at,
                'starting_cash': float(portfolio.starting_cash),
                'current_cash': float(portfolio.current_cash),
                'position_count': len(positions),
                'trade_count': 0,  # Will calculate separately
                'total_equity': float(portfolio.current_cash),  # Start with cash
                'total_positions_value': 0.0,
                'total_return': 0.0,
                'total_return_pct': 0.0,
                'daily_return': 0.0,
                'last_updated': portfolio.updated_at
            }
            
            position_data = []
            total_positions_value = 0.0
            
            for pos in positions:
                pos_value = float(pos.shares * pos.average_cost)
                total_positions_value += pos_value
                
                position_data.append({
                    'ticker': pos.ticker,
                    'shares': float(pos.shares),
                    'average_cost': float(pos.average_cost),
                    'current_value': pos_value,
                    'stop_loss': float(pos.stop_loss) if pos.stop_loss else None
                })
            
            # Update portfolio totals
            portfolio_data['total_positions_value'] = total_positions_value
            portfolio_data['total_equity'] = float(portfolio.current_cash) + total_positions_value
            
            # Calculate returns
            if portfolio.starting_cash > 0:
                total_return = portfolio_data['total_equity'] - float(portfolio.starting_cash)
                portfolio_data['total_return'] = total_return
                portfolio_data['total_return_pct'] = (total_return / float(portfolio.starting_cash)) * 100
        
        return jsonify({
            'portfolio': portfolio_data,
            'positions': position_data,
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error in /api/portfolio: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/trades')
def api_trades():
    """API endpoint for trade history"""
    try:
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
        from database.database import db_session_scope
        from database.models import Trade
        from sqlalchemy import desc
        
        with db_session_scope() as session:
            trades = session.query(Trade).filter(
                Trade.portfolio_id == portfolio_id
            ).order_by(desc(Trade.executed_at)).limit(50).all()
            
            trade_data = [{
                'id': trade.id,
                'date': trade.executed_at.isoformat(),
                'ticker': trade.ticker,
                'action': trade.trade_type,
                'shares': float(trade.shares),
                'price': float(trade.price),
                'total_amount': float(trade.total_amount),
                'reason': trade.reason or ''
            } for trade in trades]
            
            return jsonify({
                'trades': trade_data,
                'total_count': len(trade_data),
                'status': 'success'
            })
    except Exception as e:
        logger.error(f"Error in /api/trades: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/chart')
def api_chart():
    """API endpoint for portfolio performance chart"""
    try:
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
        from database.database import db_session_scope
        from database.models import PortfolioSnapshot
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from io import BytesIO
        import base64
        
        with db_session_scope() as session:
            # Get portfolio snapshots
            snapshots = session.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == portfolio_id
            ).order_by(PortfolioSnapshot.snapshot_date).all()
            
            if not snapshots:
                return jsonify({'status': 'error', 'message': 'No chart data available'}), 404
            
            # Extract data for plotting
            dates = [snap.snapshot_date for snap in snapshots]
            values = [float(snap.total_equity) for snap in snapshots]
            
            # Create the chart
            plt.figure(figsize=(12, 6))
            plt.plot(dates, values, label='DCAMOON Portfolio', linewidth=2, color='#667eea')
            
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
            
            chart_b64 = base64.b64encode(plot_data).decode()
            
            return jsonify({
                'chart': chart_b64,
                'status': 'success'
            })
            
    except Exception as e:
        logger.error(f"Error creating chart: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/execute-trade', methods=['POST'])
def api_execute_trade():
    """API endpoint to execute a trade"""
    try:
        from flask import request
        data = request.get_json()
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
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
        
        # Get trade ID before the object goes out of session scope
        trade_id = trade.id
        
        return jsonify({
            'status': 'success',
            'message': f"Trade executed: {data['trade_type']} {data['shares']} {data['ticker']}",
            'trade_id': trade_id
        })
        
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/recommendations')
def api_recommendations():
    """Get AI-powered trading recommendations"""
    try:
        import openai
        import os
        
        # Get API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'status': 'error', 
                'message': 'OpenAI API key not configured. Set OPENAI_API_KEY environment variable.'
            }), 400
        
        # Get current portfolio data
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
        from database.database import db_session_scope
        from database.models import Portfolio, Position, Trade
        
        with db_session_scope() as session:
            portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            positions = session.query(Position).filter(Position.portfolio_id == portfolio_id).all()
            recent_trades = session.query(Trade).filter(
                Trade.portfolio_id == portfolio_id
            ).order_by(Trade.executed_at.desc()).limit(5).all()
            
            # Build portfolio summary for AI
            portfolio_summary = {
                'total_equity': float(portfolio.current_cash),
                'cash_balance': float(portfolio.current_cash),
                'positions': [{'ticker': p.ticker, 'shares': float(p.shares)} for p in positions],
                'recent_trades': [{'ticker': t.ticker, 'type': t.trade_type, 'shares': float(t.shares)} for t in recent_trades]
            }
        
        # Create AI prompt
        prompt = f"""
        You are a financial advisor analyzing a portfolio. Here's the current portfolio:
        
        Cash: £{portfolio_summary['cash_balance']:.2f}
        Total Equity: £{portfolio_summary['total_equity']:.2f}
        Positions: {portfolio_summary['positions']}
        Recent Trades: {portfolio_summary['recent_trades']}
        
        Please provide:
        1. Portfolio analysis (max 100 words)
        2. 3 specific trading recommendations with rationale
        3. Risk assessment
        
        Focus on UK/European markets and keep recommendations suitable for a small portfolio.
        """
        
        # Call OpenAI API
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content
        
        return jsonify({
            'recommendations': ai_response,
            'generated_at': 'just now',
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return jsonify({
            'status': 'error', 
            'message': f'Failed to generate recommendations: {str(e)}'
        }), 500

@app.route('/api/research/opportunities')
def api_research_opportunities():
    """Get proactive trading opportunities"""
    try:
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
        # Get portfolio context
        from database.database import db_session_scope
        with db_session_scope() as session:
            from database.models import Portfolio
            portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            
            portfolio_context = {
                'cash_balance': float(portfolio.current_cash) if portfolio else 10.0,
                'total_equity': float(portfolio.current_cash) if portfolio else 10.0,
                'risk_tolerance': 'medium'
            }
        
        # Get opportunities
        opportunities = research_service.get_proactive_opportunities(
            portfolio_context=portfolio_context,
            max_opportunities=5
        )
        
        # Convert to JSON-serializable format
        opportunities_data = []
        for opp in opportunities:
            opportunities_data.append({
                'ticker': opp.ticker,
                'current_price': opp.current_price,
                'price_change_pct': opp.price_change_pct,
                'volume_analysis': opp.volume_analysis,
                'news_sentiment': opp.news_sentiment,
                'recommendation': {
                    'action': opp.recommendation.action,
                    'confidence': opp.recommendation.confidence,
                    'target_price': opp.recommendation.target_price,
                    'stop_loss': opp.recommendation.stop_loss,
                    'reasoning': opp.recommendation.reasoning,
                    'risk_level': opp.recommendation.risk_level
                },
                'technical_signals': opp.technical_signals,
                'financial_health': opp.financial_health
            })
        
        return jsonify({
            'opportunities': opportunities_data,
            'total_found': len(opportunities_data),
            'generated_at': datetime.now().isoformat(),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error getting research opportunities: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/research/analyze/<ticker>')
def api_research_analyze(ticker):
    """Get detailed research analysis for a specific ticker"""
    try:
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
        # Get portfolio context
        from database.database import db_session_scope
        with db_session_scope() as session:
            from database.models import Portfolio
            portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            
            portfolio_context = {
                'cash_balance': float(portfolio.current_cash) if portfolio else 10.0,
                'total_equity': float(portfolio.current_cash) if portfolio else 10.0
            }
        
        # Perform research
        research = research_service.perform_market_research(ticker.upper(), portfolio_context)
        
        # Convert to JSON
        research_data = {
            'ticker': research.ticker,
            'current_price': research.current_price,
            'price_change_pct': research.price_change_pct,
            'volume_analysis': research.volume_analysis,
            'news_sentiment': research.news_sentiment,
            'recommendation': {
                'action': research.recommendation.action,
                'confidence': research.recommendation.confidence,
                'target_price': research.recommendation.target_price,
                'stop_loss': research.recommendation.stop_loss,
                'reasoning': research.recommendation.reasoning,
                'risk_level': research.recommendation.risk_level,
                'timeframe': research.recommendation.timeframe
            },
            'technical_signals': research.technical_signals,
            'financial_health': research.financial_health,
            'research_date': research.research_date.isoformat()
        }
        
        return jsonify({
            'research': research_data,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/research/signals')
def api_research_signals():
    """Get trading signals for watchlist"""
    try:
        portfolio_id = 'c49d9e6f-a4c2-4524-81d1-96a8e5672d52'
        
        # Default watchlist
        watchlist = ['VWRP.L', 'VUSA.L', 'TSLA', 'AAPL', 'MSFT']
        
        # Get portfolio context
        from database.database import db_session_scope
        with db_session_scope() as session:
            from database.models import Portfolio
            portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            
            portfolio_context = {
                'cash_balance': float(portfolio.current_cash) if portfolio else 10.0
            }
        
        # Generate signals for each stock
        signals = []
        for ticker in watchlist:
            try:
                signal = research_service.generate_trading_signal(ticker, portfolio_context)
                signals.append({
                    'ticker': signal.ticker,
                    'action': signal.action,
                    'confidence': signal.confidence,
                    'target_price': signal.target_price,
                    'stop_loss': signal.stop_loss,
                    'reasoning': signal.reasoning,
                    'risk_level': signal.risk_level,
                    'generated_at': signal.generated_at.isoformat()
                })
            except Exception as e:
                logger.warning(f"Error generating signal for {ticker}: {e}")
                continue
        
        return jsonify({
            'signals': signals,
            'watchlist': watchlist,
            'generated_at': datetime.now().isoformat(),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error getting trading signals: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/autonomous/start', methods=['POST'])
def api_autonomous_start():
    """Start autonomous trading"""
    try:
        import asyncio
        
        # Run daily cycle
        if hasattr(asyncio, '_get_running_loop') and asyncio._get_running_loop():
            # Already in async context
            future = asyncio.create_task(autonomous_trader.run_daily_cycle())
        else:
            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                summary = loop.run_until_complete(autonomous_trader.run_daily_cycle())
            finally:
                loop.close()
                
        return jsonify({
            'status': 'success',
            'message': 'Autonomous trading cycle started',
            'summary': summary if 'summary' in locals() else 'Running...'
        })
        
    except Exception as e:
        logger.error(f"Error starting autonomous trading: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/autonomous/status')
def api_autonomous_status():
    """Get autonomous trading status"""
    try:
        # Get latest summary
        latest_summary = autonomous_trader.daily_summary[-1] if autonomous_trader.daily_summary else None
        
        return jsonify({
            'status': 'success',
            'autonomous_active': True,
            'last_cycle': latest_summary['timestamp'] if latest_summary else None,
            'config': {
                'max_position_size': autonomous_trader.config.max_position_size,
                'crypto_allocation': autonomous_trader.config.crypto_allocation,
                'stop_loss_stocks': autonomous_trader.config.stop_loss_stocks,
                'min_confidence': autonomous_trader.config.min_confidence
            },
            'latest_summary': latest_summary
        })
        
    except Exception as e:
        logger.error(f"Error getting autonomous status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/autonomous/summary')
def api_autonomous_summary():
    """Get daily summary report"""
    try:
        report = autonomous_trader.get_daily_summary_report()
        
        return jsonify({
            'status': 'success',
            'report': report,
            'summary_count': len(autonomous_trader.daily_summary)
        })
        
    except Exception as e:
        logger.error(f"Error getting summary report: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/autonomous/global-scan')
def api_autonomous_global_scan():
    """Trigger global market scan"""
    try:
        import asyncio
        
        # Get global universe
        universe = autonomous_trader.get_global_universe()
        
        return jsonify({
            'status': 'success',
            'message': 'Global market scan initiated',
            'universe_size': len(universe),
            'markets': list(autonomous_trader.global_markets.keys()),
            'sample_assets': universe[:20]
        })
        
    except Exception as e:
        logger.error(f"Error in global scan: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'portfolio_service': 'active'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5004))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print("DCAMOON Autonomous Trading Platform")
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
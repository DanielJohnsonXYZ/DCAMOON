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
from pathlib import Path
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__)
CORS(app)

# Configuration
DATA_DIRS = {
    'live': 'Scripts and CSV Files',
    'template': 'Start Your Own'
}

def get_portfolio_data(data_dir='Scripts and CSV Files'):
    """Load portfolio data from CSV files"""
    portfolio_file = os.path.join(data_dir, 'chatgpt_portfolio_update.csv')
    trade_log_file = os.path.join(data_dir, 'chatgpt_trade_log.csv')
    
    portfolio_data = {}
    
    # Load portfolio updates
    if os.path.exists(portfolio_file):
        portfolio_df = pd.read_csv(portfolio_file)
        portfolio_data['portfolio'] = portfolio_df.to_dict('records')
        
        # Get latest total equity
        total_rows = portfolio_df[portfolio_df['Ticker'] == 'TOTAL']
        if not total_rows.empty:
            latest_total = total_rows.iloc[-1]
            # Convert to numeric values, handling strings and missing data
            try:
                portfolio_data['total_equity'] = float(latest_total.get('Total Equity', 0))
            except (ValueError, TypeError):
                portfolio_data['total_equity'] = 0.0
            try:
                portfolio_data['cash_balance'] = float(latest_total.get('Cash Balance', 0))
            except (ValueError, TypeError):
                portfolio_data['cash_balance'] = 0.0
            portfolio_data['last_updated'] = latest_total.get('Date', 'Unknown')
    
    # Load trade log
    if os.path.exists(trade_log_file):
        trades_df = pd.read_csv(trade_log_file)
        portfolio_data['trades'] = trades_df.to_dict('records')
        portfolio_data['total_trades'] = len(trades_df)
    
    return portfolio_data

def create_performance_chart():
    """Create performance chart comparing portfolio to benchmarks"""
    try:
        portfolio_file = os.path.join('Scripts and CSV Files', 'chatgpt_portfolio_update.csv')
        
        if not os.path.exists(portfolio_file):
            return None
            
        df = pd.read_csv(portfolio_file)
        total_rows = df[df['Ticker'] == 'TOTAL'].copy()
        
        if total_rows.empty:
            return None
            
        total_rows['Date'] = pd.to_datetime(total_rows['Date'])
        total_rows = total_rows.sort_values('Date')
        
        plt.figure(figsize=(12, 6))
        plt.plot(total_rows['Date'], total_rows['Total Equity'], 
                label='ChatGPT Portfolio', linewidth=2, color='#2E86AB')
        
        # Add starting baseline
        if not total_rows.empty:
            starting_value = 100  # Starting with $100
            plt.axhline(y=starting_value, color='gray', linestyle='--', alpha=0.7, label='Starting Value ($100)')
        
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
        
        return base64.b64encode(plot_data).decode()
        
    except Exception as e:
        print(f"Error creating chart: {e}")
        return None

@app.route('/')
def index():
    """Main dashboard"""
    portfolio_data = get_portfolio_data()
    chart_data = create_performance_chart()
    
    # Calculate some basic stats
    stats = {
        'total_equity': portfolio_data.get('total_equity', 0),
        'cash_balance': portfolio_data.get('cash_balance', 0),
        'total_trades': portfolio_data.get('total_trades', 0),
        'last_updated': portfolio_data.get('last_updated', 'Unknown'),
    }
    
    # Calculate performance if we have data
    if 'portfolio' in portfolio_data:
        portfolio_df = pd.DataFrame(portfolio_data['portfolio'])
        total_rows = portfolio_df[portfolio_df['Ticker'] == 'TOTAL']
        if not total_rows.empty and len(total_rows) > 1:
            starting_value = 100  # Started with $100
            try:
                current_value = float(stats['total_equity']) if stats['total_equity'] else 0
                if current_value and starting_value:
                    stats['return_pct'] = ((current_value - starting_value) / starting_value) * 100
            except (ValueError, TypeError):
                stats['return_pct'] = 0
    
    return render_template('index.html', stats=stats, chart_data=chart_data)

@app.route('/api/portfolio')
def api_portfolio():
    """API endpoint for portfolio data"""
    data_dir = request.args.get('data_dir', 'Scripts and CSV Files')
    return jsonify(get_portfolio_data(data_dir))

@app.route('/api/chart')
def api_chart():
    """API endpoint for performance chart"""
    chart_data = create_performance_chart()
    return jsonify({'chart': chart_data})

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
    """API endpoint to trigger automated trading"""
    try:
        # This would integrate with the simple_automation.py script
        # For now, return a placeholder response
        return jsonify({
            'status': 'success',
            'message': 'Automation feature requires OpenAI API key to be configured'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# Template directory
app.template_folder = 'templates'

if __name__ == '__main__':
    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)
    
    print("ChatGPT Micro-Cap Trading Dashboard")
    print("Starting Flask server on http://0.0.0.0:5000")
    print("Dashboard will display trading results and portfolio performance")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
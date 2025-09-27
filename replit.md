# ChatGPT Micro-Cap Trading Experiment

## Project Overview
This is an AI-powered trading experiment where ChatGPT manages a real-money micro-cap stock portfolio. The project has been successfully imported and configured to work in the Replit environment.

## Project Structure

### Core Components
- **Trading Engine**: `trading_script.py` - Main trading engine with portfolio management and stop-loss automation
- **Automation**: `simple_automation.py` - AI-powered automated trading using OpenAI API
- **Web Dashboard**: `app.py` - Flask web interface for viewing portfolio status and trading results
- **Data Files**: CSV files in `Scripts and CSV Files/` and `Start Your Own/` directories

### Web Interface
- **Dashboard**: Overview of portfolio performance, equity, and trading statistics
- **Portfolio**: Detailed view of current holdings and positions
- **Trades**: Trading history and transaction log
- **Automation**: Controls for automated trading with OpenAI integration

## Current Setup

### Dependencies Installed
- Python 3.11
- Core packages: numpy, pandas, yfinance, matplotlib
- Web framework: Flask, Flask-CORS
- AI integration: OpenAI API client
- Data processing: pandas-datareader

### Workflows Configured
- **Web Dashboard**: Runs Flask app on port 5000 (webview output)
- Deployment configured for autoscale target

### File Structure
```
├── app.py                     # Flask web application
├── trading_script.py          # Core trading engine
├── simple_automation.py       # AI automation script
├── requirements.txt           # Python dependencies
├── templates/                 # HTML templates for web interface
│   ├── base.html
│   ├── index.html
│   ├── portfolio.html
│   ├── trades.html
│   └── automation.html
├── Scripts and CSV Files/     # Live trading data
├── Start Your Own/            # Template files for new experiments
└── Weekly Deep Research*/     # Research reports and analysis
```

## Usage

### Web Interface
The Flask web dashboard runs automatically and provides:
1. Real-time portfolio status and performance metrics
2. Interactive charts showing portfolio vs benchmark performance
3. Detailed portfolio holdings and trading history
4. Automated trading controls with OpenAI integration

### Command Line Tools
- `python trading_script.py` - Manual trading operations
- `python simple_automation.py --dry-run` - Test automated trading
- `python simple_automation.py --api-key YOUR_KEY` - Run automated trading

### Automation Requirements
- OpenAI API key required for automated trading features
- Environment variable: `OPENAI_API_KEY=your-key-here`
- Supports both GPT-4 and GPT-3.5-turbo models

## Recent Changes (Import Setup)
- **2025-09-18**: Initial import and Replit environment setup
- Installed Python 3.11 and all required dependencies
- Created Flask web interface for portfolio visualization
- Fixed data type conversion issues for CSV file processing
- Configured workflows and deployment settings
- Set up templates for responsive web dashboard

## Technical Notes

### Data Handling
- Portfolio data loaded from CSV files with robust error handling
- Automatic type conversion for numeric values
- Graceful fallback when data files are missing

### Chart Generation
- Matplotlib charts with non-interactive backend for server use
- Base64 encoded images served directly in web interface
- Performance comparison with baseline starting value

### Development vs Production
- Development server runs with debug mode enabled
- Production deployment uses autoscale target for efficiency
- All host headers configured for Replit proxy compatibility

## User Preferences
- Clean, professional web interface design
- Real-time data visualization and analytics
- Command-line tools maintained for advanced users
- Comprehensive logging and error handling
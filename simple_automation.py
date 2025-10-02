"""
Simple Automation Script for ChatGPT Micro-Cap Trading

This script integrates with the existing trading_script.py to provide
automated LLM-based trading decisions.

Usage:
    python simple_automation.py --api-key YOUR_KEY
"""

import json
import os
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

# Import existing trading functions
from services.portfolio_service import PortfolioService
from utils.portfolio_helper import get_default_portfolio_id
from trading_script import (
    process_portfolio, daily_results, load_latest_portfolio_state,
    set_data_dir, PORTFOLIO_CSV, TRADE_LOG_CSV, last_trading_date
)

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_trading_prompt(portfolio_df: pd.DataFrame, cash: float, total_equity: float) -> str:
    """Generate a trading prompt with current portfolio data"""
    
    # Format holdings
    if portfolio_df.empty:
        holdings_text = "No current holdings"
    else:
        holdings_text = portfolio_df.to_string(index=False)
    
    # Get current date
    today = last_trading_date().date().isoformat()
    
    prompt = f"""You are a professional portfolio analyst. Here is your current portfolio state as of {today}:

[ Holdings ]
{holdings_text}

[ Snapshot ]
Cash Balance: ${cash:,.2f}
Total Equity: ${total_equity:,.2f}

Rules:
- You have ${cash:,.2f} in cash available for new positions
- Prefer U.S. micro-cap stocks (<$300M market cap)
- Full shares only, no options or derivatives
- Use stop-losses for risk management
- Be conservative with position sizing

Analyze the current market conditions and provide specific trading recommendations.

Respond with ONLY a JSON object in this exact format:
{{
    "analysis": "Brief market analysis",
    "trades": [
        {{
            "action": "buy",
            "ticker": "SYMBOL",
            "shares": 100,
            "price": 25.50,
            "stop_loss": 20.00,
            "reason": "Brief rationale"
        }}
    ],
    "confidence": 0.8
}}

Only recommend trades you are confident about. If no trades are recommended, use an empty trades array."""
    
    return prompt


def call_openai_api(prompt: str, api_key: str, model: str = "gpt-4") -> str:
    """Call OpenAI API and return response with improved error handling"""
    if not HAS_OPENAI:
        raise ImportError("openai package not installed. Run: pip install openai")
    
    if not api_key or not api_key.strip():
        raise ValueError("API key cannot be empty")
    
    logger.info(f"Making API call to {model}")
    client = openai.OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional portfolio analyst. Always respond with valid JSON in the exact format requested."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
            timeout=30
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from API")
        
        logger.info("API call successful")
        return content
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return f'{{"error": "API error: {e}"}}'        
    except Exception as e:
        logger.error(f"Unexpected error in API call: {e}")
        return f'{{"error": "API call failed: {e}"}}'        


def parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse LLM response and extract trading decisions with improved error handling"""
    try:
        # Clean the response
        response = response.strip()
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            result = json.loads(json_str)
            logger.info("Successfully parsed LLM response")
            return result
        else:
            # Try parsing the entire response as JSON
            result = json.loads(response)
            logger.info("Successfully parsed LLM response")
            return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        logger.debug(f"Raw response: {response}")
        return {"error": "Failed to parse response", "raw_response": response}
    except Exception as e:
        logger.error(f"Unexpected error parsing response: {e}")
        return {"error": f"Parse error: {e}", "raw_response": response}


def validate_trade(trade: Dict[str, Any]) -> Optional[str]:
    """Validate a trade object and return error message if invalid"""
    required_fields = ['action', 'ticker']
    for field in required_fields:
        if field not in trade or not trade[field]:
            return f"Missing required field: {field}"
    
    action = trade.get('action', '').lower()
    if action not in ['buy', 'sell', 'hold']:
        return f"Invalid action: {action}"
    
    if action in ['buy', 'sell']:
        try:
            shares = float(trade.get('shares', 0))
            price = float(trade.get('price', 0))
            if shares <= 0 or price <= 0:
                return f"Invalid shares ({shares}) or price ({price})"
        except (ValueError, TypeError):
            return "Invalid numeric values for shares or price"
    
    return None


def execute_automated_trades(trades: List[Dict[str, Any]], portfolio_df: pd.DataFrame, cash: float, 
                           portfolio_service: Optional[PortfolioService] = None, 
                           portfolio_id: Optional[str] = None,
                           execute_real_trades: bool = False) -> tuple[pd.DataFrame, float]:
    """Execute trades recommended by LLM with improved validation and error handling
    
    Args:
        trades: List of trade recommendations
        portfolio_df: Portfolio DataFrame (for compatibility)
        cash: Available cash (for compatibility)
        portfolio_service: Portfolio service for real trade execution
        portfolio_id: Portfolio ID for real trades
        execute_real_trades: Whether to execute real trades or just simulate
    """
    
    logger.info(f"Executing {len(trades)} LLM-recommended trades")
    executed_trades = 0
    
    for i, trade in enumerate(trades):
        # Validate trade
        validation_error = validate_trade(trade)
        if validation_error:
            logger.error(f"Trade {i+1} validation failed: {validation_error}")
            continue
        
        action = trade.get('action', '').lower()
        ticker = trade.get('ticker', '').upper()
        reason = trade.get('reason', 'LLM recommendation')
        
        try:
            if action == 'buy':
                shares = float(trade.get('shares', 0))
                price = float(trade.get('price', 0))
                stop_loss = float(trade.get('stop_loss', 0))
                cost = shares * price
                
                if cost <= cash:
                    logger.info(f"BUY: {shares} shares of {ticker} at ${price:.2f} (stop: ${stop_loss:.2f}) - {reason}")
                    
                    if execute_real_trades and portfolio_service and portfolio_id:
                        try:
                            # Execute real trade through portfolio service
                            trade_result = portfolio_service.execute_trade(
                                portfolio_id=portfolio_id,
                                ticker=ticker,
                                trade_type='BUY',
                                shares=shares,
                                price=price,
                                reason=f"Automation: {reason}"
                            )
                            logger.info(f"✅ REAL TRADE EXECUTED: {trade_result.id}")
                            executed_trades += 1
                            
                            # Set stop loss if specified
                            if stop_loss > 0:
                                portfolio_service.update_stop_loss(portfolio_id, ticker, stop_loss)
                                logger.info(f"Stop loss set at ${stop_loss:.2f}")
                                
                        except Exception as e:
                            logger.error(f"❌ REAL TRADE FAILED: {e}")
                            continue
                    else:
                        # Simulation mode
                        cash -= cost
                        executed_trades += 1
                        logger.info(f"💻 SIMULATION: Cash reduced by ${cost:.2f}, new balance: ${cash:.2f}")
                else:
                    logger.warning(f"BUY REJECTED: {ticker} - Insufficient cash (need ${cost:.2f}, have ${cash:.2f})")
            
            elif action == 'sell':
                shares = float(trade.get('shares', 0))
                price = float(trade.get('price', 0))
                proceeds = shares * price
                logger.info(f"SELL: {shares} shares of {ticker} at ${price:.2f} - {reason}")
                
                if execute_real_trades and portfolio_service and portfolio_id:
                    try:
                        # Execute real trade through portfolio service
                        trade_result = portfolio_service.execute_trade(
                            portfolio_id=portfolio_id,
                            ticker=ticker,
                            trade_type='SELL',
                            shares=shares,
                            price=price,
                            reason=f"Automation: {reason}"
                        )
                        logger.info(f"✅ REAL TRADE EXECUTED: {trade_result.id}")
                        executed_trades += 1
                        
                    except Exception as e:
                        logger.error(f"❌ REAL TRADE FAILED: {e}")
                        continue
                else:
                    # Simulation mode
                    cash += proceeds
                    executed_trades += 1
                    logger.info(f"💻 SIMULATION: Cash increased by ${proceeds:.2f}, new balance: ${cash:.2f}")
            
            elif action == 'hold':
                logger.info(f"HOLD: {ticker} - {reason}")
                executed_trades += 1
                
        except Exception as e:
            logger.error(f"Error executing trade {i+1}: {e}")
    
    logger.info(f"Executed {executed_trades}/{len(trades)} trades successfully")
    return portfolio_df, cash


def run_automated_trading(api_key: str, model: str = "gpt-4", data_dir: str = "Start Your Own", 
                         dry_run: bool = False, execute_real_trades: bool = False):
    """Run the automated trading process with comprehensive error handling"""
    
    logger.info("Starting automated trading system")
    
    try:
        # Validate inputs
        if not api_key or not api_key.strip():
            raise ValueError("API key is required")
        
        # Set up data directory
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.warning(f"Data directory does not exist: {data_path}")
            data_path.mkdir(parents=True, exist_ok=True)
        
        set_data_dir(data_path)
        
        # Initialize portfolio service for real trades
        portfolio_service = None
        portfolio_id = None
        if execute_real_trades:
            from database.database import initialize_database
            try:
                # Initialize database and portfolio service
                initialize_database()
                portfolio_service = PortfolioService()
                portfolio_id = get_default_portfolio_id()
                logger.info(f"Portfolio service initialized for real trade execution (ID: {portfolio_id})")
            except Exception as e:
                logger.error(f"Failed to initialize portfolio service: {e}")
                raise ValueError(f"Cannot execute real trades: {e}")
        
        # Load current portfolio
        portfolio_file = data_path / "chatgpt_portfolio_update.csv"
        try:
            if portfolio_file.exists():
                portfolio_data, cash = load_latest_portfolio_state()
                # Convert list of dicts to DataFrame
                if isinstance(portfolio_data, list):
                    portfolio_df = pd.DataFrame(portfolio_data)
                elif isinstance(portfolio_data, pd.DataFrame):
                    portfolio_df = portfolio_data.copy()
                else:
                    logger.warning(f"Unexpected portfolio data type: {type(portfolio_data)}")
                    portfolio_df = pd.DataFrame(columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"])
                logger.info("Portfolio loaded successfully")
            else:
                logger.warning("Portfolio file not found, using defaults")
                portfolio_df = pd.DataFrame(columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"])
                cash = 10000.0  # Default starting cash
        except Exception as e:
            logger.error(f"Error loading portfolio: {e}")
            portfolio_df = pd.DataFrame(columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"])
            cash = 10000.0
        
        # Ensure portfolio_df has the expected structure
        expected_cols = ["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
        for col in expected_cols:
            if col not in portfolio_df.columns:
                portfolio_df[col] = 0.0 if col in ["shares", "stop_loss", "buy_price", "cost_basis"] else ""
        
        # Calculate total equity
        try:
            if not portfolio_df.empty and 'cost_basis' in portfolio_df.columns:
                # Convert to numeric and handle errors
                cost_basis_series = pd.to_numeric(portfolio_df['cost_basis'], errors='coerce').fillna(0.0)
                total_value = cost_basis_series.sum()
            else:
                total_value = 0.0
            total_equity = cash + total_value
        except Exception as e:
            logger.error(f"Error calculating total equity: {e}")
            total_value = 0.0
            total_equity = cash
        
        logger.info(f"Portfolio loaded: ${cash:,.2f} cash, ${total_equity:,.2f} total equity")
        
        # Generate prompt
        prompt = generate_trading_prompt(portfolio_df, cash, total_equity)
        logger.info(f"Generated prompt ({len(prompt)} characters)")
        
        # Call LLM
        logger.info("Calling LLM for trading recommendations")
        response = call_openai_api(prompt, api_key, model)
        logger.info(f"Received response ({len(response)} characters)")
        
        # Parse response
        parsed_response = parse_llm_response(response)
        
        if "error" in parsed_response:
            logger.error(f"LLM response error: {parsed_response['error']}")
            return
        
        # Display analysis
        analysis = parsed_response.get('analysis', 'No analysis provided')
        confidence = parsed_response.get('confidence', 0.0)
        trades = parsed_response.get('trades', [])
        
        logger.info(f"LLM Analysis - Confidence: {confidence:.1%}, Trades: {len(trades)}")
        print(f"\n=== LLM Analysis ===")
        print(f"Analysis: {analysis}")
        print(f"Confidence: {confidence:.1%}")
        print(f"Recommended trades: {len(trades)}")
        
        # Execute trades
        if trades and not dry_run:
            portfolio_df, cash = execute_automated_trades(
                trades, portfolio_df, cash,
                portfolio_service=portfolio_service,
                portfolio_id=portfolio_id,
                execute_real_trades=execute_real_trades
            )
        elif trades and dry_run:
            logger.info(f"DRY RUN - Would execute {len(trades)} trades")
            print(f"\n=== DRY RUN - Would execute {len(trades)} trades ===")
            for trade in trades:
                action = trade.get('action', 'unknown').upper()
                shares = trade.get('shares', 0)
                ticker = trade.get('ticker', 'unknown')
                price = trade.get('price', 0)
                print(f"  {action}: {shares} shares of {ticker} at ${price:.2f}")
        else:
            logger.info("No trades recommended")
            print("No trades recommended")
        
        # Save the LLM response for review
        try:
            response_file = data_path / "llm_responses.jsonl"
            with open(response_file, "a", encoding='utf-8') as f:
                f.write(json.dumps({
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "response": parsed_response,
                    "raw_response": response
                }, ensure_ascii=False) + "\n")
            logger.info(f"Response saved to: {response_file}")
        except Exception as e:
            logger.error(f"Error saving response: {e}")
        
        logger.info("Automated trading process completed")
        print(f"\n=== Analysis Complete ===")
        
    except Exception as e:
        logger.error(f"Error in automated trading process: {e}")
        print(f"Error: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Simple Automated Trading")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--model", default="gpt-4", help="OpenAI model to use")
    parser.add_argument("--data-dir", default="Start Your Own", help="Data directory")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute trades, just show recommendations")
    parser.add_argument("--execute-real-trades", action="store_true", 
                       help="Execute real trades (WARNING: This will modify your portfolio!)")
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OpenAI API key required")
        print("Error: OpenAI API key required. Set OPENAI_API_KEY env var or use --api-key")
        return 1
    
    # Validate trade execution settings
    if args.execute_real_trades and not args.dry_run:
        logger.warning("REAL TRADES ENABLED - This will modify your portfolio!")
        print("WARNING: Real trade execution is enabled. This will modify your portfolio!")
    
    try:
        # Run automated trading
        run_automated_trading(
            api_key=api_key,
            model=args.model,
            data_dir=args.data_dir,
            dry_run=args.dry_run,
            execute_real_trades=args.execute_real_trades and not args.dry_run
        )
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    main()
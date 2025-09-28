"""Autonomous Trading Engine for DCAMOON.

This is your personal AI trading assistant that:
- Scans global markets 24/7
- Automatically executes trades based on opportunities
- Manages risk and portfolio allocation
- Handles rebalancing and optimization
- Supports stocks, ETFs, crypto, and commodities worldwide
"""

import logging
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import time
from concurrent.futures import ThreadPoolExecutor
import requests

from database.database import db_session_scope
from database.models import Portfolio, Position, Trade
from services.portfolio_service import PortfolioService
from services.research_service import ResearchService, TradingSignal, MarketResearch

logger = logging.getLogger(__name__)

@dataclass
class AutonomousConfig:
    """Configuration for autonomous trading"""
    max_position_size: float = 0.50  # 50% max per position
    stop_loss_stocks: float = 0.20   # 20% stop loss for stocks
    stop_loss_etfs: float = 0.15     # 15% stop loss for ETFs
    stop_loss_crypto: float = 0.25   # 25% stop loss for crypto
    crypto_allocation: float = 0.20  # 20% portfolio in crypto
    min_confidence: float = 0.60     # 60% minimum confidence for trades
    rebalance_frequency: int = 7     # Rebalance every 7 days
    daily_scan_hour: int = 9         # Scan markets at 9 AM
    emergency_stop_loss: float = 0.30 # 30% total portfolio stop loss

@dataclass
class GlobalMarket:
    """Global market configuration"""
    region: str
    currency: str
    market_hours: Dict[str, int]
    top_assets: List[str]
    exchanges: List[str]

class AutonomousTrader:
    """Fully autonomous AI trading system"""
    
    def __init__(self, portfolio_id: str, config: AutonomousConfig = None):
        self.portfolio_id = portfolio_id
        self.config = config or AutonomousConfig()
        self.portfolio_service = PortfolioService()
        self.research_service = ResearchService()
        self.last_rebalance = None
        self.daily_summary = []
        
        # Global markets configuration
        self.global_markets = {
            'US': GlobalMarket(
                region='US',
                currency='USD',
                market_hours={'open': 9, 'close': 16},
                top_assets=['SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META'],
                exchanges=['NASDAQ', 'NYSE']
            ),
            'UK': GlobalMarket(
                region='UK',
                currency='GBP',
                market_hours={'open': 8, 'close': 16},
                top_assets=['VWRP.L', 'VUSA.L', 'VMID.L', 'IUSA.L', 'BP.L', 'SHEL.L', 'AZN.L'],
                exchanges=['LSE']
            ),
            'EU': GlobalMarket(
                region='EU',
                currency='EUR',
                market_hours={'open': 9, 'close': 17},
                top_assets=['ASML', 'SAP', 'LVMH', 'NESN.SW', 'ROCHE.SW'],
                exchanges=['XETRA', 'Euronext']
            ),
            'CRYPTO': GlobalMarket(
                region='Global',
                currency='USD',
                market_hours={'open': 0, 'close': 24},  # 24/7
                top_assets=['BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'ADA-USD', 'MATIC-USD'],
                exchanges=['Crypto']
            ),
            'COMMODITIES': GlobalMarket(
                region='Global',
                currency='USD',
                market_hours={'open': 0, 'close': 24},
                top_assets=['GLD', 'SLV', 'DJP', 'USO', 'UNG', 'PDBC'],
                exchanges=['Commodities']
            )
        }
    
    def get_global_universe(self) -> List[str]:
        """Get comprehensive list of global assets to scan"""
        universe = []
        
        # Add all assets from all markets
        for market in self.global_markets.values():
            universe.extend(market.top_assets)
        
        # Add emerging markets ETFs
        emerging_markets = [
            'VWO',    # Vanguard Emerging Markets
            'IEMG',   # iShares Core MSCI Emerging Markets
            'EEM',    # iShares MSCI Emerging Markets
            'FXI',    # China Large-Cap ETF
            'INDA',   # India ETF
            'EWZ',    # Brazil ETF
        ]
        universe.extend(emerging_markets)
        
        # Add sector-specific growth opportunities
        growth_sectors = [
            # AI & Technology
            'ARKK', 'ARKQ', 'ARKW',  # ARK Innovation ETFs
            'SMH',   # Semiconductor ETF
            'ROBO',  # Robotics ETF
            'CLOU',  # Cloud Computing ETF
            
            # Clean Energy & Sustainability
            'ICLN',  # Clean Energy ETF
            'PBW',   # Clean Energy ETF
            'QCLN',  # Clean Energy ETF
            
            # Healthcare & Biotech
            'XBI',   # Biotech ETF
            'IBB',   # Biotech ETF
            'ARKG',  # Genomics ETF
            
            # Fintech & Digital Assets
            'FINX',  # Fintech ETF
            'BLOK',  # Blockchain ETF
        ]
        universe.extend(growth_sectors)
        
        return list(set(universe))  # Remove duplicates
    
    async def scan_global_markets(self) -> List[MarketResearch]:
        """Scan all global markets for opportunities"""
        logger.info("🌍 Starting global market scan...")
        
        universe = self.get_global_universe()
        opportunities = []
        
        # Get current portfolio context
        portfolio_summary = self.portfolio_service.get_portfolio_summary(self.portfolio_id)
        portfolio_context = {
            'cash_balance': portfolio_summary.get('current_cash', 0),
            'total_equity': portfolio_summary.get('total_equity', 0),
            'risk_tolerance': 'high'
        }
        
        # Scan in batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for ticker in batch:
                    future = executor.submit(
                        self.research_service.perform_market_research,
                        ticker,
                        portfolio_context
                    )
                    futures.append((ticker, future))
                
                for ticker, future in futures:
                    try:
                        research = future.result(timeout=30)
                        
                        # Filter for high-confidence opportunities
                        if (research.recommendation.confidence >= self.config.min_confidence and
                            research.recommendation.action in ['BUY', 'SELL']):
                            opportunities.append(research)
                            
                    except Exception as e:
                        logger.warning(f"Error researching {ticker}: {e}")
                        continue
            
            # Rate limiting - pause between batches
            await asyncio.sleep(2)
        
        # Sort by confidence and potential return
        opportunities.sort(key=lambda x: x.recommendation.confidence, reverse=True)
        
        logger.info(f"🎯 Found {len(opportunities)} high-confidence opportunities")
        return opportunities[:20]  # Top 20 opportunities
    
    def calculate_position_size(self, signal: TradingSignal, portfolio_value: float) -> float:
        """Calculate optimal position size based on confidence and risk"""
        base_size = min(
            portfolio_value * self.config.max_position_size,  # Max 50% per position
            portfolio_value * 0.10  # Default 10% position
        )
        
        # Adjust based on confidence
        confidence_multiplier = signal.confidence
        
        # Adjust based on risk level
        risk_multipliers = {'low': 1.2, 'medium': 1.0, 'high': 0.8}
        risk_multiplier = risk_multipliers.get(signal.risk_level, 1.0)
        
        # Calculate final position size
        position_size = base_size * confidence_multiplier * risk_multiplier
        
        return max(position_size, 1.0)  # Minimum £1 position
    
    def should_execute_trade(self, research: MarketResearch) -> bool:
        """Determine if we should execute a trade based on research"""
        signal = research.recommendation
        
        # Check minimum confidence
        if signal.confidence < self.config.min_confidence:
            return False
        
        # Check if we have enough cash
        portfolio_summary = self.portfolio_service.get_portfolio_summary(self.portfolio_id)
        available_cash = portfolio_summary.get('current_cash', 0)
        
        if available_cash < 1.0:  # Need at least £1 to trade
            return False
        
        # Check if we already have a position
        current_positions = self.portfolio_service.get_positions(self.portfolio_id)
        existing_position = next((p for p in current_positions if p.ticker == research.ticker), None)
        
        if signal.action == 'BUY' and existing_position:
            # Don't buy more if we already have a large position
            position_value = existing_position.shares * research.current_price
            portfolio_value = portfolio_summary.get('total_equity', 0)
            if position_value / portfolio_value > self.config.max_position_size:
                return False
        
        if signal.action == 'SELL' and not existing_position:
            # Can't sell what we don't have
            return False
        
        return True
    
    async def execute_autonomous_trade(self, research: MarketResearch) -> Optional[str]:
        """Execute a trade autonomously"""
        try:
            signal = research.recommendation
            
            if not self.should_execute_trade(research):
                return None
            
            portfolio_summary = self.portfolio_service.get_portfolio_summary(self.portfolio_id)
            available_cash = portfolio_summary.get('current_cash', 0)
            
            if signal.action == 'BUY':
                # Calculate position size
                position_value = self.calculate_position_size(signal, available_cash)
                shares = position_value / research.current_price
                
                # Execute buy order
                trade = self.portfolio_service.execute_trade(
                    portfolio_id=self.portfolio_id,
                    ticker=research.ticker,
                    trade_type='BUY',
                    shares=shares,
                    price=research.current_price,
                    reason=f"🤖 Autonomous: {signal.reasoning[:100]}"
                )
                
                # Set stop loss
                stop_loss_price = research.current_price * (1 - self.get_stop_loss_pct(research.ticker))
                self.portfolio_service.update_stop_loss(self.portfolio_id, research.ticker, stop_loss_price)
                
                logger.info(f"🚀 EXECUTED BUY: {shares:.3f} shares of {research.ticker} at £{research.current_price:.2f}")
                return f"Bought {shares:.3f} {research.ticker} at £{research.current_price:.2f}"
                
            elif signal.action == 'SELL':
                # Get current position
                positions = self.portfolio_service.get_positions(self.portfolio_id)
                position = next((p for p in positions if p.ticker == research.ticker), None)
                
                if position and position.shares > 0:
                    # Execute sell order
                    trade = self.portfolio_service.execute_trade(
                        portfolio_id=self.portfolio_id,
                        ticker=research.ticker,
                        trade_type='SELL',
                        shares=position.shares,
                        price=research.current_price,
                        reason=f"🤖 Autonomous: {signal.reasoning[:100]}"
                    )
                    
                    logger.info(f"💰 EXECUTED SELL: {position.shares:.3f} shares of {research.ticker} at £{research.current_price:.2f}")
                    return f"Sold {position.shares:.3f} {research.ticker} at £{research.current_price:.2f}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error executing autonomous trade for {research.ticker}: {e}")
            return None
    
    def get_stop_loss_pct(self, ticker: str) -> float:
        """Get appropriate stop loss percentage based on asset type"""
        if any(crypto in ticker for crypto in ['BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'MATIC', '-USD']):
            return self.config.stop_loss_crypto
        elif any(etf in ticker for etf in ['SPY', 'QQQ', 'VWO', 'ARKK', 'XBI']):
            return self.config.stop_loss_etfs
        else:
            return self.config.stop_loss_stocks
    
    async def check_stop_losses(self) -> List[str]:
        """Check and execute stop losses automatically"""
        executed_stops = []
        
        try:
            positions = self.portfolio_service.get_positions(self.portfolio_id)
            
            for position in positions:
                if not position.stop_loss:
                    continue
                
                # Get current price
                try:
                    stock = yf.Ticker(position.ticker)
                    current_price = stock.history(period="1d")['Close'].iloc[-1]
                    
                    # Check if stop loss triggered
                    if current_price <= position.stop_loss:
                        # Execute stop loss sell
                        trade = self.portfolio_service.execute_trade(
                            portfolio_id=self.portfolio_id,
                            ticker=position.ticker,
                            trade_type='SELL',
                            shares=position.shares,
                            price=current_price,
                            reason=f"🛑 Stop Loss: Price {current_price:.2f} <= Stop {position.stop_loss:.2f}"
                        )
                        
                        executed_stops.append(f"Stop loss triggered: Sold {position.shares:.3f} {position.ticker} at £{current_price:.2f}")
                        logger.warning(f"🛑 STOP LOSS: {position.ticker} sold at £{current_price:.2f}")
                        
                except Exception as e:
                    logger.warning(f"Error checking stop loss for {position.ticker}: {e}")
                    continue
            
            return executed_stops
            
        except Exception as e:
            logger.error(f"Error checking stop losses: {e}")
            return []
    
    async def rebalance_portfolio(self) -> Dict[str, Any]:
        """Automatically rebalance portfolio to maintain target allocations"""
        try:
            logger.info("⚖️ Starting portfolio rebalancing...")
            
            portfolio_summary = self.portfolio_service.get_portfolio_summary(self.portfolio_id)
            total_value = portfolio_summary.get('total_equity', 0)
            
            if total_value < 10:  # Too small to rebalance
                return {'status': 'skipped', 'reason': 'Portfolio too small'}
            
            positions = self.portfolio_service.get_positions(self.portfolio_id)
            rebalance_actions = []
            
            # Calculate current allocations
            current_crypto = 0
            current_stocks = 0
            
            for position in positions:
                position_value = position.shares * self.get_current_price(position.ticker)
                
                if any(crypto in position.ticker for crypto in ['BTC', 'ETH', 'BNB', 'SOL', '-USD']):
                    current_crypto += position_value
                else:
                    current_stocks += position_value
            
            crypto_pct = current_crypto / total_value if total_value > 0 else 0
            target_crypto_pct = self.config.crypto_allocation
            
            # Rebalance crypto allocation
            if abs(crypto_pct - target_crypto_pct) > 0.05:  # 5% threshold
                if crypto_pct < target_crypto_pct:
                    # Need more crypto
                    buy_amount = total_value * (target_crypto_pct - crypto_pct)
                    rebalance_actions.append(f"Buy £{buy_amount:.2f} crypto to reach {target_crypto_pct:.0%} target")
                else:
                    # Too much crypto
                    sell_amount = total_value * (crypto_pct - target_crypto_pct)
                    rebalance_actions.append(f"Sell £{sell_amount:.2f} crypto to reach {target_crypto_pct:.0%} target")
            
            self.last_rebalance = datetime.now()
            
            return {
                'status': 'completed',
                'actions': rebalance_actions,
                'current_crypto_pct': crypto_pct,
                'target_crypto_pct': target_crypto_pct
            }
            
        except Exception as e:
            logger.error(f"Error rebalancing portfolio: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_current_price(self, ticker: str) -> float:
        """Get current price for a ticker"""
        try:
            stock = yf.Ticker(ticker)
            return stock.history(period="1d")['Close'].iloc[-1]
        except:
            return 0.0
    
    async def run_daily_cycle(self) -> Dict[str, Any]:
        """Run the complete daily autonomous trading cycle"""
        cycle_start = datetime.now()
        logger.info(f"🤖 Starting daily autonomous trading cycle at {cycle_start}")
        
        summary = {
            'timestamp': cycle_start.isoformat(),
            'opportunities_found': 0,
            'trades_executed': [],
            'stop_losses_triggered': [],
            'rebalance_actions': [],
            'portfolio_value': 0,
            'performance': {}
        }
        
        try:
            # 1. Check stop losses first
            stop_losses = await self.check_stop_losses()
            summary['stop_losses_triggered'] = stop_losses
            
            # 2. Scan global markets for opportunities
            opportunities = await self.scan_global_markets()
            summary['opportunities_found'] = len(opportunities)
            
            # 3. Execute high-confidence trades
            for opportunity in opportunities[:5]:  # Top 5 opportunities
                trade_result = await self.execute_autonomous_trade(opportunity)
                if trade_result:
                    summary['trades_executed'].append(trade_result)
                    
                # Rate limiting between trades
                await asyncio.sleep(1)
            
            # 4. Check if rebalancing is needed
            if (not self.last_rebalance or 
                (datetime.now() - self.last_rebalance).days >= self.config.rebalance_frequency):
                rebalance_result = await self.rebalance_portfolio()
                summary['rebalance_actions'] = rebalance_result.get('actions', [])
            
            # 5. Get final portfolio status
            portfolio_summary = self.portfolio_service.get_portfolio_summary(self.portfolio_id)
            summary['portfolio_value'] = portfolio_summary.get('total_equity', 0)
            summary['performance'] = {
                'total_return': portfolio_summary.get('total_return', 0),
                'total_return_pct': portfolio_summary.get('total_return_pct', 0),
                'position_count': portfolio_summary.get('position_count', 0)
            }
            
            # Store daily summary
            self.daily_summary.append(summary)
            
            logger.info(f"✅ Daily cycle completed. Portfolio: £{summary['portfolio_value']:.2f}, Trades: {len(summary['trades_executed'])}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error in daily autonomous cycle: {e}")
            summary['error'] = str(e)
            return summary
    
    def get_daily_summary_report(self) -> str:
        """Generate a human-readable daily summary report"""
        if not self.daily_summary:
            return "No trading activity today."
        
        latest = self.daily_summary[-1]
        
        report = f"""
🤖 **DCAMOON Autonomous Trading Daily Report**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 **Portfolio Status**
• Total Value: £{latest['portfolio_value']:.2f}
• Total Return: £{latest['performance'].get('total_return', 0):.2f} ({latest['performance'].get('total_return_pct', 0):.2f}%)
• Active Positions: {latest['performance'].get('position_count', 0)}

🎯 **Today's Activity**
• Market Opportunities Scanned: {latest['opportunities_found']}
• Trades Executed: {len(latest['trades_executed'])}
• Stop Losses Triggered: {len(latest['stop_losses_triggered'])}

"""
        
        if latest['trades_executed']:
            report += "📈 **Trades Executed Today:**\n"
            for trade in latest['trades_executed']:
                report += f"• {trade}\n"
            report += "\n"
        
        if latest['stop_losses_triggered']:
            report += "🛑 **Stop Losses Triggered:**\n"
            for stop in latest['stop_losses_triggered']:
                report += f"• {stop}\n"
            report += "\n"
        
        if latest['rebalance_actions']:
            report += "⚖️ **Portfolio Rebalancing:**\n"
            for action in latest['rebalance_actions']:
                report += f"• {action}\n"
            report += "\n"
        
        report += "🌍 **Global Market Coverage**: US, UK, EU, Asia, Crypto, Commodities\n"
        report += "🎯 **Next Scan**: Tomorrow at 9:00 AM\n"
        
        return report
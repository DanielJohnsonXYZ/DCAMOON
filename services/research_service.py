"""Research service for proactive market analysis and trading signals.

This service provides:
- Real-time market research
- News sentiment analysis
- Technical analysis
- Trading signal generation
- Market screening
"""

import logging
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import openai
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    """Trading signal with confidence and reasoning"""
    ticker: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 to 1.0
    target_price: Optional[float]
    stop_loss: Optional[float]
    reasoning: str
    timeframe: str  # short, medium, long
    risk_level: str  # low, medium, high
    generated_at: datetime

@dataclass
class MarketResearch:
    """Market research report"""
    ticker: str
    current_price: float
    price_change_pct: float
    volume_analysis: str
    technical_signals: Dict[str, Any]
    news_sentiment: str
    financial_health: Dict[str, Any]
    recommendation: TradingSignal
    research_date: datetime

class ResearchService:
    """Proactive market research and trading bot service"""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if self.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
        
    def get_market_screener_results(self, criteria: Dict[str, Any]) -> List[str]:
        """Screen the market for stocks matching criteria"""
        try:
            # UK market focus - popular ETFs and stocks
            uk_universe = [
                'VWRP.L',  # Vanguard FTSE All-World
                'VUSA.L',  # Vanguard S&P 500
                'VMID.L',  # Vanguard FTSE 250
                'IUSA.L',  # iShares Core S&P 500
                'EIMI.L',  # iShares Core MSCI EM IMI
                'VEUR.L',  # Vanguard FTSE Europe
                'VERX.L',  # Vanguard FTSE Europe ex-UK
                'VFEM.L',  # Vanguard FTSE Emerging Markets
                'TSLA',    # Tesla
                'AAPL',    # Apple
                'MSFT',    # Microsoft
                'GOOGL',   # Google
                'AMZN',    # Amazon
                'NVDA',    # NVIDIA
                'META',    # Meta
                'NFLX',    # Netflix
                'BP.L',    # BP
                'SHEL.L',  # Shell
                'LLOY.L',  # Lloyds
                'BARC.L',  # Barclays
                'VOD.L',   # Vodafone
                'BT-A.L',  # BT Group
            ]
            
            # Basic screening based on criteria
            screened = []
            max_results = criteria.get('max_results', 10)
            
            for ticker in uk_universe[:max_results]:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    
                    # Basic filters
                    if criteria.get('min_market_cap'):
                        market_cap = info.get('marketCap', 0)
                        if market_cap < criteria['min_market_cap']:
                            continue
                    
                    if criteria.get('max_pe_ratio'):
                        pe_ratio = info.get('trailingPE', 999)
                        if pe_ratio and pe_ratio > criteria['max_pe_ratio']:
                            continue
                    
                    screened.append(ticker)
                except Exception as e:
                    logger.warning(f"Error screening {ticker}: {e}")
                    continue
            
            return screened
            
        except Exception as e:
            logger.error(f"Error in market screener: {e}")
            return ['VWRP.L', 'VUSA.L', 'TSLA']  # Fallback list
    
    def get_technical_analysis(self, ticker: str) -> Dict[str, Any]:
        """Perform technical analysis on a stock"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            
            if hist.empty:
                return {"error": "No price data available"}
            
            # Calculate technical indicators
            current_price = hist['Close'].iloc[-1]
            
            # Moving averages
            ma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            ma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else ma_20
            
            # RSI (simplified)
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if not rsi.empty else 50
            
            # Volume analysis
            avg_volume = hist['Volume'].mean()
            recent_volume = hist['Volume'].iloc[-5:].mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # Price momentum
            week_change = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100
            month_change = ((current_price - hist['Close'].iloc[-20]) / hist['Close'].iloc[-20]) * 100
            
            # Support/Resistance (simplified)
            recent_low = hist['Low'].iloc[-20:].min()
            recent_high = hist['High'].iloc[-20:].max()
            
            return {
                'current_price': float(current_price),
                'ma_20': float(ma_20),
                'ma_50': float(ma_50),
                'rsi': float(current_rsi),
                'volume_ratio': float(volume_ratio),
                'week_change_pct': float(week_change),
                'month_change_pct': float(month_change),
                'support_level': float(recent_low),
                'resistance_level': float(recent_high),
                'trend': 'bullish' if current_price > ma_20 > ma_50 else 'bearish' if current_price < ma_20 < ma_50 else 'neutral'
            }
            
        except Exception as e:
            logger.error(f"Error in technical analysis for {ticker}: {e}")
            return {"error": str(e)}
    
    def get_news_sentiment(self, ticker: str) -> str:
        """Get news sentiment analysis for a stock"""
        try:
            # For now, return a basic sentiment based on technical indicators
            # In production, you'd integrate with news APIs like NewsAPI, Alpha Vantage, etc.
            
            technical = self.get_technical_analysis(ticker)
            if 'error' in technical:
                return "neutral"
            
            # Simple sentiment based on technical signals
            rsi = technical.get('rsi', 50)
            trend = technical.get('trend', 'neutral')
            week_change = technical.get('week_change_pct', 0)
            
            if trend == 'bullish' and week_change > 2 and rsi < 70:
                return "positive"
            elif trend == 'bearish' and week_change < -2 and rsi > 30:
                return "negative" 
            else:
                return "neutral"
                
        except Exception as e:
            logger.error(f"Error getting news sentiment for {ticker}: {e}")
            return "neutral"
    
    def generate_trading_signal(self, ticker: str, portfolio_context: Dict[str, Any]) -> TradingSignal:
        """Generate a trading signal with AI analysis"""
        try:
            # Get technical analysis
            technical = self.get_technical_analysis(ticker)
            if 'error' in technical:
                return TradingSignal(
                    ticker=ticker,
                    action="HOLD",
                    confidence=0.1,
                    target_price=None,
                    stop_loss=None,
                    reasoning="Insufficient data for analysis",
                    timeframe="short",
                    risk_level="high",
                    generated_at=datetime.now()
                )
            
            # Get sentiment
            sentiment = self.get_news_sentiment(ticker)
            
            # Get stock info
            stock = yf.Ticker(ticker)
            info = stock.info
            
            current_price = technical['current_price']
            
            # Basic signal generation logic
            signals = []
            confidence_factors = []
            
            # Technical signals
            if technical['trend'] == 'bullish' and technical['rsi'] < 70:
                signals.append('BUY')
                confidence_factors.append(0.7)
            elif technical['trend'] == 'bearish' and technical['rsi'] > 30:
                signals.append('SELL')
                confidence_factors.append(0.6)
            else:
                signals.append('HOLD')
                confidence_factors.append(0.4)
            
            # Sentiment factor
            if sentiment == 'positive':
                confidence_factors.append(0.6)
                if 'SELL' not in signals:
                    signals.append('BUY')
            elif sentiment == 'negative':
                confidence_factors.append(0.5)
                if 'BUY' not in signals:
                    signals.append('SELL')
            
            # Volume confirmation
            if technical['volume_ratio'] > 1.5:  # High volume
                confidence_factors.append(0.3)
            
            # Determine final action
            if signals.count('BUY') > signals.count('SELL'):
                action = 'BUY'
            elif signals.count('SELL') > signals.count('BUY'):
                action = 'SELL'
            else:
                action = 'HOLD'
            
            # Calculate confidence
            confidence = min(sum(confidence_factors) / len(confidence_factors), 1.0) if confidence_factors else 0.5
            
            # Set targets
            target_price = None
            stop_loss = None
            
            if action == 'BUY':
                target_price = current_price * 1.1  # 10% upside target
                stop_loss = current_price * 0.95    # 5% stop loss
            elif action == 'SELL':
                target_price = current_price * 0.9  # 10% downside target
                stop_loss = current_price * 1.05    # 5% stop loss
            
            # Generate reasoning with AI if available
            reasoning = f"Technical: {technical['trend']} trend, RSI: {technical['rsi']:.1f}, Sentiment: {sentiment}"
            
            if self.openai_api_key and self.openai_client:
                try:
                    ai_prompt = f"""
                    Analyze this trading signal for {ticker}:
                    
                    Current Price: £{current_price:.2f}
                    Technical Analysis: {technical}
                    Sentiment: {sentiment}
                    Recommended Action: {action}
                    Portfolio Context: Available cash £{portfolio_context.get('cash_balance', 0):.2f}
                    
                    Provide a concise 2-sentence explanation of why this is a good/bad trade opportunity.
                    """
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": ai_prompt}],
                        max_tokens=100,
                        temperature=0.7
                    )
                    
                    reasoning = response.choices[0].message.content.strip()
                    
                except Exception as e:
                    logger.warning(f"AI reasoning failed: {e}")
            
            return TradingSignal(
                ticker=ticker,
                action=action,
                confidence=confidence,
                target_price=target_price,
                stop_loss=stop_loss,
                reasoning=reasoning,
                timeframe="short",
                risk_level="medium" if confidence > 0.6 else "high",
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error generating trading signal for {ticker}: {e}")
            return TradingSignal(
                ticker=ticker,
                action="HOLD",
                confidence=0.1,
                target_price=None,
                stop_loss=None,
                reasoning=f"Error in analysis: {str(e)}",
                timeframe="short",
                risk_level="high",
                generated_at=datetime.now()
            )
    
    def perform_market_research(self, ticker: str, portfolio_context: Dict[str, Any]) -> MarketResearch:
        """Perform comprehensive market research on a stock"""
        try:
            # Get all analysis components
            technical = self.get_technical_analysis(ticker)
            sentiment = self.get_news_sentiment(ticker)
            signal = self.generate_trading_signal(ticker, portfolio_context)
            
            # Get basic stock info
            stock = yf.Ticker(ticker)
            info = stock.info
            
            current_price = technical.get('current_price', 0)
            
            # Volume analysis
            volume_analysis = "Normal volume"
            if technical.get('volume_ratio', 1) > 1.5:
                volume_analysis = "High volume - increased interest"
            elif technical.get('volume_ratio', 1) < 0.5:
                volume_analysis = "Low volume - reduced interest"
            
            # Financial health (basic)
            financial_health = {
                'market_cap': info.get('marketCap', 'N/A'),
                'pe_ratio': info.get('trailingPE', 'N/A'),
                'dividend_yield': info.get('dividendYield', 'N/A'),
                'debt_to_equity': info.get('debtToEquity', 'N/A')
            }
            
            return MarketResearch(
                ticker=ticker,
                current_price=current_price,
                price_change_pct=technical.get('week_change_pct', 0),
                volume_analysis=volume_analysis,
                technical_signals=technical,
                news_sentiment=sentiment,
                financial_health=financial_health,
                recommendation=signal,
                research_date=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error performing market research for {ticker}: {e}")
            # Return a minimal research object
            return MarketResearch(
                ticker=ticker,
                current_price=0,
                price_change_pct=0,
                volume_analysis="Error",
                technical_signals={"error": str(e)},
                news_sentiment="neutral",
                financial_health={},
                recommendation=TradingSignal(
                    ticker=ticker,
                    action="HOLD",
                    confidence=0.1,
                    target_price=None,
                    stop_loss=None,
                    reasoning="Research error",
                    timeframe="short",
                    risk_level="high",
                    generated_at=datetime.now()
                ),
                research_date=datetime.now()
            )
    
    def get_proactive_opportunities(self, portfolio_context: Dict[str, Any], max_opportunities: int = 5) -> List[MarketResearch]:
        """Find proactive trading opportunities"""
        try:
            # Screen for potential opportunities
            screening_criteria = {
                'max_results': max_opportunities * 2,  # Screen more than needed
                'min_market_cap': 1000000000,  # 1B+ market cap for stability
                'max_pe_ratio': 30  # Reasonable valuation
            }
            
            candidates = self.get_market_screener_results(screening_criteria)
            
            # Research each candidate
            opportunities = []
            for ticker in candidates:
                research = self.perform_market_research(ticker, portfolio_context)
                
                # Filter for good opportunities
                if (research.recommendation.action == 'BUY' and 
                    research.recommendation.confidence > 0.5):
                    opportunities.append(research)
                
                if len(opportunities) >= max_opportunities:
                    break
            
            # Sort by confidence
            opportunities.sort(key=lambda x: x.recommendation.confidence, reverse=True)
            
            return opportunities[:max_opportunities]
            
        except Exception as e:
            logger.error(f"Error finding proactive opportunities: {e}")
            return []
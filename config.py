"""Configuration management for DCAMOON trading system.

This module provides centralized configuration management with validation
and environment variable support.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TradingConfig:
    """Trading system configuration"""
    
    # Data directories
    data_dir: str = "Scripts and CSV Files"
    backup_dir: str = "backups"
    
    # File paths
    portfolio_file: str = "chatgpt_portfolio_update.csv"
    trade_log_file: str = "chatgpt_trade_log.csv"
    
    # Trading parameters
    starting_cash: float = 100.0
    max_position_size: float = 0.1  # 10% of portfolio
    default_stop_loss_pct: float = 0.15  # 15% stop loss
    
    # API configuration
    openai_model: str = "gpt-4"
    openai_timeout: int = 30
    openai_max_tokens: int = 1500
    openai_temperature: float = 0.3
    
    # Data fetching
    data_timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Risk management
    max_daily_trades: int = 5
    max_portfolio_positions: int = 20
    min_trade_amount: float = 10.0
    
    # Benchmarks and universe
    default_benchmarks: List[str] = field(default_factory=lambda: ["IWO", "XBI", "SPY", "IWM"])
    default_universe: List[str] = field(default_factory=list)
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @classmethod
    def from_env(cls) -> 'TradingConfig':
        """Create configuration from environment variables"""
        config = cls()
        
        # Override with environment variables if they exist
        env_mappings = {
            'DCAMOON_DATA_DIR': 'data_dir',
            'DCAMOON_STARTING_CASH': ('starting_cash', float),
            'DCAMOON_MAX_POSITION_SIZE': ('max_position_size', float),
            'DCAMOON_STOP_LOSS_PCT': ('default_stop_loss_pct', float),
            'OPENAI_MODEL': 'openai_model',
            'OPENAI_TIMEOUT': ('openai_timeout', int),
            'DCAMOON_LOG_LEVEL': 'log_level',
        }
        
        for env_var, attr_config in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                try:
                    if isinstance(attr_config, tuple):
                        attr_name, converter = attr_config
                        setattr(config, attr_name, converter(env_value))
                    else:
                        setattr(config, attr_config, env_value)
                    logger.info(f"Using environment variable {env_var}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid value for {env_var}: {env_value} ({e})")
        
        return config
    
    @classmethod
    def from_file(cls, config_path: Path) -> 'TradingConfig':
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Create config with defaults, then update with file data
            config = cls()
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    logger.warning(f"Unknown configuration key: {key}")
            
            logger.info(f"Configuration loaded from {config_path}")
            return config
            
        except FileNotFoundError:
            logger.info(f"Config file not found: {config_path}, using defaults")
            return cls()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file {config_path}: {e}")
            return cls()
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            return cls()
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if self.starting_cash <= 0:
            errors.append("starting_cash must be positive")
        
        if not (0 < self.max_position_size <= 1):
            errors.append("max_position_size must be between 0 and 1")
        
        if not (0 < self.default_stop_loss_pct < 1):
            errors.append("default_stop_loss_pct must be between 0 and 1")
        
        if self.openai_timeout <= 0:
            errors.append("openai_timeout must be positive")
        
        if self.data_timeout <= 0:
            errors.append("data_timeout must be positive")
        
        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")
        
        if self.retry_delay < 0:
            errors.append("retry_delay must be non-negative")
        
        if self.max_daily_trades <= 0:
            errors.append("max_daily_trades must be positive")
        
        if self.max_portfolio_positions <= 0:
            errors.append("max_portfolio_positions must be positive")
        
        if self.min_trade_amount <= 0:
            errors.append("min_trade_amount must be positive")
        
        if self.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            errors.append("log_level must be valid logging level")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'data_dir': self.data_dir,
            'backup_dir': self.backup_dir,
            'portfolio_file': self.portfolio_file,
            'trade_log_file': self.trade_log_file,
            'starting_cash': self.starting_cash,
            'max_position_size': self.max_position_size,
            'default_stop_loss_pct': self.default_stop_loss_pct,
            'openai_model': self.openai_model,
            'openai_timeout': self.openai_timeout,
            'openai_max_tokens': self.openai_max_tokens,
            'openai_temperature': self.openai_temperature,
            'data_timeout': self.data_timeout,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'max_daily_trades': self.max_daily_trades,
            'max_portfolio_positions': self.max_portfolio_positions,
            'min_trade_amount': self.min_trade_amount,
            'default_benchmarks': self.default_benchmarks,
            'default_universe': self.default_universe,
            'log_level': self.log_level,
            'log_format': self.log_format,
        }
    
    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to JSON file"""
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving config to {config_path}: {e}")
            raise


def load_config(config_path: Optional[Path] = None) -> TradingConfig:
    """Load configuration with fallback logic
    
    Priority:
    1. Provided config file path
    2. Environment variables
    3. config.json in current directory
    4. Default configuration
    """
    
    # Try provided path first
    if config_path and config_path.exists():
        config = TradingConfig.from_file(config_path)
    else:
        # Try default config.json
        default_config_path = Path("config.json")
        if default_config_path.exists():
            config = TradingConfig.from_file(default_config_path)
        else:
            # Use defaults
            config = TradingConfig()
    
    # Override with environment variables
    env_config = TradingConfig.from_env()
    for key in config.to_dict().keys():
        env_value = getattr(env_config, key)
        default_value = getattr(TradingConfig(), key)
        if env_value != default_value:
            setattr(config, key, env_value)
    
    # Validate configuration
    errors = config.validate()
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("Configuration loaded and validated successfully")
    return config


def setup_logging(config: TradingConfig) -> None:
    """Setup logging based on configuration"""
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format=config.log_format,
        force=True  # Override any existing logging configuration
    )
    logger.info(f"Logging configured at {config.log_level} level")


# Global configuration instance
_config: Optional[TradingConfig] = None


def get_config() -> TradingConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: TradingConfig) -> None:
    """Set the global configuration instance"""
    global _config
    _config = config
    setup_logging(config)
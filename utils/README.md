# Utils Module Documentation

Shared utilities for the DCAMOON trading system.

---

## Modules

### `portfolio_helper.py`
**Purpose:** Centralized portfolio ID management

**Functions:**
- `get_default_portfolio_id()` - Get portfolio ID from environment or database
- `require_portfolio_id(portfolio_id)` - Validate and return portfolio ID

**Usage:**
```python
from utils.portfolio_helper import get_default_portfolio_id

portfolio_id = get_default_portfolio_id()
# Returns: UUID string from DCAMOON_PORTFOLIO_ID env var or first portfolio in DB
```

---

### `file_lock.py`
**Purpose:** Cross-platform file locking and atomic writes

**Functions:**
- `file_lock(file_path, timeout)` - Context manager for file locking
- `atomic_write(file_path, data)` - Atomic file write
- `locked_csv_write(csv_path, timeout)` - Safe CSV write with locking

**Usage:**
```python
from utils.file_lock import file_lock, atomic_write
from pathlib import Path

# File locking
with file_lock(Path('data.csv'), timeout=10.0):
    # File is locked, safe to read/write
    df = pd.read_csv('data.csv')
    # ... modify df ...
    df.to_csv('data.csv', index=False)

# Atomic write
atomic_write(Path('config.json'), json.dumps(data))
```

**Platform Support:**
- Unix/Linux/macOS: `fcntl` module
- Windows: `msvcrt` module

---

### `retry.py`
**Purpose:** Retry logic with exponential backoff

**Classes:**
- `CircuitBreaker` - Prevent cascading failures

**Decorators:**
- `@retry_with_backoff` - General retry decorator
- `@retry_on_rate_limit` - Specialized for API rate limits

**Usage:**
```python
from utils.retry import retry_with_backoff, CircuitBreaker

@retry_with_backoff(max_retries=3, exceptions=(ConnectionError,))
def fetch_data():
    # Will retry up to 3 times with exponential backoff
    return requests.get('https://api.example.com/data')

# Circuit breaker
circuit = CircuitBreaker(failure_threshold=5, cooldown_seconds=60)
result = circuit.call(risky_function, arg1, arg2)
```

**Configuration:**
- `MAX_RETRIES` environment variable (default: 3)
- `RETRY_BACKOFF` environment variable (default: 2)

---

### `validation.py`
**Purpose:** Input validation for trading operations

**Functions:**
- `validate_ticker(ticker)` - Validate stock ticker format
- `validate_shares(shares, allow_fractional)` - Validate share quantity
- `validate_price(price, ticker)` - Validate stock price
- `validate_trade_amount(shares, price, available_cash, ticker)` - Validate trade amount
- `validate_stop_loss(stop_loss, current_price, ticker)` - Validate stop loss price
- `validate_position_size(trade_amount, portfolio_value, max_position_size, ticker)` - Validate position size
- `validate_trade_type(trade_type)` - Validate trade action (BUY/SELL)
- `validate_portfolio_id(portfolio_id)` - Validate UUID format
- `validate_api_key(api_key, key_type)` - Validate API key format

**Usage:**
```python
from utils.validation import validate_ticker, validate_trade_amount, ValidationError

try:
    ticker = validate_ticker('AAPL')  # Returns: 'AAPL'
    total = validate_trade_amount(100, 150.50, available_cash=20000, ticker='AAPL')
except ValidationError as e:
    print(f"Validation failed: {e}")
```

**Validation Rules:**
- Tickers: 1-5 letters, optional .EXCHANGE suffix
- Shares: Positive, max 1 billion
- Prices: Positive, max $1M, max 4 decimal places
- Trade amounts: Max $10M per trade
- Stop loss: Must be below current price

---

### `startup.py`
**Purpose:** Application startup validation and initialization

**Functions:**
- `validate_required_env_vars(required_vars)` - Check required env vars
- `validate_optional_env_vars(optional_vars)` - Apply defaults to optional vars
- `validate_database_url()` - Validate DATABASE_URL
- `check_api_key_format(api_key, key_name)` - Check for placeholder keys
- `validate_flask_config()` - Validate Flask settings
- `validate_trading_config()` - Validate trading parameters
- `run_startup_checks(require_openai, require_database)` - Run all checks
- `print_startup_banner(app_name, version)` - Print startup banner

**Usage:**
```python
from utils.startup import run_startup_checks, print_startup_banner, StartupError

try:
    print_startup_banner("My App", "1.0.0")
    run_startup_checks(require_openai=True, require_database=True)
except StartupError as e:
    print(f"ERROR: {e}")
    exit(1)
```

**Validation Checks:**
- Required environment variables present
- API keys not placeholders
- Database URL valid and accessible
- Flask debug mode appropriate for environment
- Trading parameters in valid ranges
- File permissions for sensitive directories

---

## Design Principles

1. **Fail Fast** - Validate inputs early, before expensive operations
2. **Clear Errors** - Provide actionable error messages with context
3. **Defensive** - Assume inputs are invalid until proven otherwise
4. **Flexible** - Support configuration via environment variables
5. **Documented** - Comprehensive docstrings and examples

---

## Common Patterns

### Validation Pattern
```python
from utils.validation import validate_ticker, ValidationError

def process_trade(ticker, shares, price):
    try:
        # Validate all inputs first
        ticker = validate_ticker(ticker)
        shares = validate_shares(shares)
        price = validate_price(price, ticker)

        # Then perform operation
        return execute_trade(ticker, shares, price)

    except ValidationError as e:
        logger.error(f"Invalid trade: {e}")
        raise
```

### Retry Pattern
```python
from utils.retry import retry_with_backoff

@retry_with_backoff(max_retries=3)
def fetch_stock_price(ticker):
    # Automatically retries on failure
    return api.get_price(ticker)
```

### File Locking Pattern
```python
from utils.file_lock import file_lock

def update_portfolio_csv(portfolio_df, csv_path):
    with file_lock(csv_path):
        # Safe to read and write
        existing = pd.read_csv(csv_path)
        updated = pd.concat([existing, portfolio_df])
        updated.to_csv(csv_path, index=False)
```

---

## Testing

### Unit Tests
```python
# Test validation
from utils.validation import validate_ticker, ValidationError
import pytest

def test_valid_ticker():
    assert validate_ticker('AAPL') == 'AAPL'
    assert validate_ticker('VWRP.L') == 'VWRP.L'

def test_invalid_ticker():
    with pytest.raises(ValidationError):
        validate_ticker('INVALID123')
```

### Integration Tests
```python
# Test file locking prevents corruption
import threading
from utils.file_lock import file_lock

def concurrent_write_test():
    # Multiple threads writing to same file
    # Should not corrupt data with file locking
    pass
```

---

## Performance Considerations

- **File Locking**: Adds ~10ms overhead per CSV operation (negligible)
- **Validation**: <1ms per validation call (negligible)
- **Retry Logic**: Only activates on failures (no overhead on success)
- **Startup Checks**: One-time cost at initialization (~100ms)

---

## Error Handling

All modules use custom exception classes for clear error handling:

- `ValidationError` - Input validation failures
- `StartupError` - Startup validation failures
- Built-in exceptions preserved where appropriate

---

## Contributing

When adding new utilities:

1. Add comprehensive docstrings
2. Include usage examples
3. Write unit tests
4. Update this README
5. Follow existing patterns and conventions

---

## Dependencies

- **Python Standard Library**: `os`, `pathlib`, `logging`, `re`, `time`, `typing`
- **Cross-Platform Support**: `fcntl` (Unix), `msvcrt` (Windows)
- **Decimal Precision**: `decimal` module for financial calculations

No external dependencies required for core functionality.

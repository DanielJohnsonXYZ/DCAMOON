"""
Input Validation Utilities

Provides validation functions for trading operations to prevent errors
and ensure data integrity.
"""
import re
import logging
from typing import Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_ticker(ticker: str) -> str:
    """
    Validate and normalize a stock ticker symbol.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Normalized ticker (uppercase, stripped)

    Raises:
        ValidationError: If ticker is invalid
    """
    if not ticker or not isinstance(ticker, str):
        raise ValidationError("Ticker must be a non-empty string")

    # Normalize
    ticker = ticker.strip().upper()

    # Validate format: 1-5 letters, optional .EXCHANGE suffix
    # Examples: AAPL, VWRP.L, BRK.B
    if not re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', ticker):
        raise ValidationError(
            f"Invalid ticker format: '{ticker}'. "
            f"Expected 1-5 letters, optionally followed by .EXCHANGE"
        )

    return ticker


def validate_shares(shares: float, allow_fractional: bool = False) -> float:
    """
    Validate share quantity.

    Args:
        shares: Number of shares
        allow_fractional: Whether to allow fractional shares

    Returns:
        Validated shares

    Raises:
        ValidationError: If shares is invalid
    """
    try:
        shares = float(shares)
    except (TypeError, ValueError):
        raise ValidationError(f"Shares must be a number, got: {type(shares)}")

    if shares <= 0:
        raise ValidationError(f"Shares must be positive, got: {shares}")

    if not allow_fractional and shares != int(shares):
        raise ValidationError(f"Fractional shares not allowed, got: {shares}")

    # Sanity check: no more than 1 billion shares
    if shares > 1_000_000_000:
        raise ValidationError(f"Unrealistic share quantity: {shares}")

    return shares


def validate_price(price: float, ticker: Optional[str] = None) -> float:
    """
    Validate stock price.

    Args:
        price: Price per share
        ticker: Optional ticker for error messages

    Returns:
        Validated price

    Raises:
        ValidationError: If price is invalid
    """
    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ValidationError(f"Price must be a number, got: {type(price)}")

    if price <= 0:
        raise ValidationError(f"Price must be positive, got: {price}")

    # Sanity check: no stock over $1 million per share
    # (Berkshire Hathaway is ~$500k)
    if price > 1_000_000:
        ticker_str = f" for {ticker}" if ticker else ""
        raise ValidationError(f"Unrealistic price{ticker_str}: ${price:,.2f}")

    # Precision check: no more than 4 decimal places
    price_decimal = Decimal(str(price))
    if abs(price_decimal.as_tuple().exponent) > 4:
        raise ValidationError(
            f"Price has too many decimal places: {price}. Max 4 decimals."
        )

    return price


def validate_trade_amount(
    shares: float,
    price: float,
    available_cash: Optional[float] = None,
    ticker: Optional[str] = None
) -> float:
    """
    Validate trade amount and check if sufficient funds available.

    Args:
        shares: Number of shares
        price: Price per share
        available_cash: Available cash balance (for buy orders)
        ticker: Optional ticker for error messages

    Returns:
        Total trade amount

    Raises:
        ValidationError: If trade amount is invalid or insufficient funds
    """
    # Validate inputs first
    shares = validate_shares(shares)
    price = validate_price(price, ticker)

    # Calculate total
    total_amount = shares * price

    # Check for unrealistic trade sizes
    if total_amount > 10_000_000:  # $10M max per trade
        ticker_str = f" for {ticker}" if ticker else ""
        raise ValidationError(
            f"Trade amount{ticker_str} exceeds maximum: ${total_amount:,.2f}"
        )

    # Check sufficient funds for buy orders
    if available_cash is not None:
        if total_amount > available_cash:
            ticker_str = f" {ticker}" if ticker else ""
            raise ValidationError(
                f"Insufficient funds for{ticker_str}. "
                f"Required: ${total_amount:,.2f}, Available: ${available_cash:,.2f}"
            )

    return total_amount


def validate_stop_loss(
    stop_loss: float,
    current_price: float,
    ticker: Optional[str] = None
) -> float:
    """
    Validate stop loss price.

    Args:
        stop_loss: Stop loss price
        current_price: Current/buy price
        ticker: Optional ticker for error messages

    Returns:
        Validated stop loss

    Raises:
        ValidationError: If stop loss is invalid
    """
    stop_loss = validate_price(stop_loss, ticker)
    current_price = validate_price(current_price, ticker)

    # Stop loss should be below current price
    if stop_loss >= current_price:
        ticker_str = f" for {ticker}" if ticker else ""
        raise ValidationError(
            f"Stop loss{ticker_str} must be below current price. "
            f"Stop: ${stop_loss:.2f}, Current: ${current_price:.2f}"
        )

    # Check for unrealistic stop loss (more than 50% below)
    loss_pct = (current_price - stop_loss) / current_price
    if loss_pct > 0.50:
        ticker_str = f" for {ticker}" if ticker else ""
        logger.warning(
            f"Large stop loss{ticker_str}: {loss_pct:.1%} below current price"
        )

    return stop_loss


def validate_position_size(
    trade_amount: float,
    portfolio_value: float,
    max_position_size: float = 0.10,
    ticker: Optional[str] = None
) -> None:
    """
    Validate that trade doesn't exceed maximum position size.

    Args:
        trade_amount: Total amount of trade
        portfolio_value: Total portfolio value
        max_position_size: Maximum position size as fraction (default: 0.10 = 10%)
        ticker: Optional ticker for error messages

    Raises:
        ValidationError: If position size exceeds maximum
    """
    if portfolio_value <= 0:
        raise ValidationError("Portfolio value must be positive")

    position_pct = trade_amount / portfolio_value

    if position_pct > max_position_size:
        ticker_str = f" for {ticker}" if ticker else ""
        raise ValidationError(
            f"Position size{ticker_str} exceeds maximum. "
            f"Trade: ${trade_amount:,.2f} ({position_pct:.1%}), "
            f"Max allowed: {max_position_size:.1%} of ${portfolio_value:,.2f}"
        )


def validate_trade_type(trade_type: str) -> str:
    """
    Validate and normalize trade type.

    Args:
        trade_type: Trade type (buy/sell)

    Returns:
        Normalized trade type (uppercase)

    Raises:
        ValidationError: If trade type is invalid
    """
    if not trade_type or not isinstance(trade_type, str):
        raise ValidationError("Trade type must be a non-empty string")

    trade_type = trade_type.strip().upper()

    valid_types = ['BUY', 'SELL']
    if trade_type not in valid_types:
        raise ValidationError(
            f"Invalid trade type: '{trade_type}'. Must be one of: {valid_types}"
        )

    return trade_type


def validate_portfolio_id(portfolio_id: str) -> str:
    """
    Validate portfolio ID format (UUID).

    Args:
        portfolio_id: Portfolio ID

    Returns:
        Validated portfolio ID

    Raises:
        ValidationError: If portfolio ID is invalid
    """
    if not portfolio_id or not isinstance(portfolio_id, str):
        raise ValidationError("Portfolio ID must be a non-empty string")

    portfolio_id = portfolio_id.strip()

    # Basic UUID format validation
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, portfolio_id, re.IGNORECASE):
        raise ValidationError(
            f"Invalid portfolio ID format: '{portfolio_id}'. Expected UUID format."
        )

    return portfolio_id


def validate_api_key(api_key: str, key_type: str = "API") -> str:
    """
    Validate API key format.

    Args:
        api_key: API key string
        key_type: Type of key for error messages (e.g., "OpenAI", "API")

    Returns:
        Validated API key

    Raises:
        ValidationError: If API key is invalid
    """
    if not api_key or not isinstance(api_key, str):
        raise ValidationError(f"{key_type} key must be a non-empty string")

    api_key = api_key.strip()

    # Check for placeholder values
    placeholder_patterns = [
        'your_',
        'example',
        'test_',
        'placeholder',
        'changeme',
        'xxx',
    ]

    api_key_lower = api_key.lower()
    for pattern in placeholder_patterns:
        if pattern in api_key_lower:
            raise ValidationError(
                f"{key_type} key appears to be a placeholder value: '{api_key}'"
            )

    # Minimum length check
    if len(api_key) < 10:
        raise ValidationError(
            f"{key_type} key is too short: {len(api_key)} chars. "
            f"Expected at least 10 characters."
        )

    return api_key


def get_validation_errors(validation_functions: List) -> List[str]:
    """
    Run multiple validation functions and collect all errors.

    Args:
        validation_functions: List of (func, args) tuples

    Returns:
        List of error messages (empty if all validations pass)

    Example:
        errors = get_validation_errors([
            (validate_ticker, ['AAPL']),
            (validate_shares, [100]),
            (validate_price, [150.50]),
        ])
    """
    errors = []

    for func, args in validation_functions:
        try:
            if isinstance(args, (list, tuple)):
                func(*args)
            else:
                func(args)
        except ValidationError as e:
            errors.append(str(e))

    return errors

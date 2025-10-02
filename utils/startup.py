"""
Startup Validation and Initialization

Validates environment configuration on application startup and provides
helpful error messages for missing or invalid configuration.
"""
import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class StartupError(Exception):
    """Raised when startup validation fails."""
    pass


def validate_required_env_vars(required_vars: List[str]) -> Dict[str, str]:
    """
    Validate that all required environment variables are set.

    Args:
        required_vars: List of required environment variable names

    Returns:
        Dictionary of validated environment variables

    Raises:
        StartupError: If any required variables are missing
    """
    missing = []
    invalid = []
    values = {}

    for var in required_vars:
        value = os.getenv(var)

        if not value:
            missing.append(var)
        elif value.strip() == '':
            invalid.append(var)
        else:
            values[var] = value.strip()

    errors = []

    if missing:
        errors.append(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please set these in your .env file or environment."
        )

    if invalid:
        errors.append(
            f"Empty environment variables: {', '.join(invalid)}\n"
            f"Please provide values for these variables."
        )

    if errors:
        raise StartupError('\n\n'.join(errors))

    return values


def validate_optional_env_vars(optional_vars: Dict[str, str]) -> Dict[str, str]:
    """
    Validate optional environment variables and provide defaults.

    Args:
        optional_vars: Dictionary of {var_name: default_value}

    Returns:
        Dictionary of environment variables with defaults applied
    """
    values = {}

    for var, default in optional_vars.items():
        value = os.getenv(var)

        if value and value.strip():
            values[var] = value.strip()
        else:
            values[var] = default
            if default:
                logger.info(f"Using default for {var}: {default}")

    return values


def validate_database_url() -> str:
    """
    Validate DATABASE_URL environment variable.

    Returns:
        Valid database URL

    Raises:
        StartupError: If DATABASE_URL is invalid
    """
    db_url = os.getenv('DATABASE_URL', 'sqlite:///dcamoon.db')

    # Check for supported database types
    valid_prefixes = ['sqlite://', 'postgresql://', 'mysql://']

    if not any(db_url.startswith(prefix) for prefix in valid_prefixes):
        raise StartupError(
            f"Invalid DATABASE_URL: {db_url}\n"
            f"Must start with one of: {', '.join(valid_prefixes)}"
        )

    # For SQLite, check directory exists
    if db_url.startswith('sqlite:///'):
        db_path = Path(db_url.replace('sqlite:///', ''))
        db_dir = db_path.parent

        if not db_dir.exists():
            logger.warning(f"Database directory does not exist: {db_dir}. Creating...")
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise StartupError(f"Could not create database directory {db_dir}: {e}")

    logger.info(f"Using database: {db_url}")
    return db_url


def check_api_key_format(api_key: str, key_name: str = "API") -> None:
    """
    Check if API key looks valid (not a placeholder).

    Args:
        api_key: API key to check
        key_name: Name of the key for error messages

    Raises:
        StartupError: If API key appears to be a placeholder
    """
    placeholder_indicators = [
        'your_',
        'example',
        'placeholder',
        'changeme',
        'xxx',
    ]

    api_key_lower = api_key.lower()

    for indicator in placeholder_indicators:
        if indicator in api_key_lower:
            raise StartupError(
                f"{key_name} appears to be a placeholder value.\n"
                f"Please set a real API key in your .env file.\n"
                f"Current value: {api_key[:10]}..."
            )


def validate_flask_config() -> None:
    """
    Validate Flask-specific configuration.

    Raises:
        StartupError: If Flask configuration is unsafe
    """
    flask_env = os.getenv('FLASK_ENV', 'production')
    flask_debug = os.getenv('FLASK_DEBUG', 'false').lower()

    # Warn about debug mode
    if flask_debug in ['true', '1', 'yes']:
        logger.critical(
            "WARNING: Flask debug mode is enabled! "
            "This is VERY DANGEROUS in production as it can expose sensitive data "
            "and allow arbitrary code execution."
        )

        if flask_env == 'production':
            raise StartupError(
                "Flask debug mode must NOT be enabled in production!\n"
                "Set FLASK_DEBUG=false in your .env file."
            )


def check_file_permissions() -> None:
    """
    Check that critical files/directories have appropriate permissions.
    """
    critical_paths = [
        Path.home() / '.dcamoon',
    ]

    for path in critical_paths:
        if path.exists():
            # Check if directory is readable/writable
            if not os.access(path, os.R_OK | os.W_OK):
                logger.warning(
                    f"Insufficient permissions for {path}. "
                    f"This may cause issues with encryption key storage."
                )


def validate_trading_config() -> None:
    """
    Validate trading-specific configuration.

    Raises:
        StartupError: If trading configuration is invalid
    """
    try:
        max_position_size = float(os.getenv('MAX_POSITION_SIZE', '0.10'))
        if not 0 < max_position_size <= 1:
            raise ValueError("MAX_POSITION_SIZE must be between 0 and 1")
    except ValueError as e:
        raise StartupError(f"Invalid MAX_POSITION_SIZE: {e}")

    try:
        stop_loss_pct = float(os.getenv('STOP_LOSS_PCT', '0.20'))
        if not 0 < stop_loss_pct <= 1:
            raise ValueError("STOP_LOSS_PCT must be between 0 and 1")
    except ValueError as e:
        raise StartupError(f"Invalid STOP_LOSS_PCT: {e}")


def run_startup_checks(
    require_openai: bool = False,
    require_database: bool = True
) -> None:
    """
    Run all startup validation checks.

    Args:
        require_openai: Whether OpenAI API key is required
        require_database: Whether database configuration is required

    Raises:
        StartupError: If any critical validation fails
    """
    logger.info("Running startup validation checks...")

    # Required variables
    required = []
    if require_openai:
        required.append('OPENAI_API_KEY')

    if required:
        try:
            env_vars = validate_required_env_vars(required)

            # Check API key format
            if 'OPENAI_API_KEY' in env_vars:
                check_api_key_format(env_vars['OPENAI_API_KEY'], 'OpenAI API key')

        except StartupError:
            raise

    # Database validation
    if require_database:
        try:
            validate_database_url()
        except StartupError:
            raise

    # Flask config validation
    try:
        validate_flask_config()
    except StartupError:
        raise

    # Trading config validation
    try:
        validate_trading_config()
    except StartupError as e:
        logger.warning(f"Trading configuration issue: {e}")
        # Don't fail startup for trading config issues

    # File permissions check
    check_file_permissions()

    logger.info("✓ Startup validation complete")


def print_startup_banner(app_name: str = "DCAMOON", version: str = "1.0.0") -> None:
    """
    Print application startup banner with configuration info.

    Args:
        app_name: Application name
        version: Application version
    """
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   {app_name:^53}   ║
║   {'Trading System v' + version:^53}   ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Environment: {os.getenv('FLASK_ENV', 'production')}
Database: {os.getenv('DATABASE_URL', 'sqlite:///dcamoon.db')[:50]}
Log Level: {os.getenv('LOG_LEVEL', 'INFO')}

Starting up...
""")

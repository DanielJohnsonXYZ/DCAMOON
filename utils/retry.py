"""
Retry Logic with Exponential Backoff

Provides decorators and utilities for retrying failed operations.
"""
import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional
import os

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: Optional[int] = None,
    backoff_multiplier: float = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: from env or 3)
        backoff_multiplier: Multiplier for exponential backoff (default: from env or 2)
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function(exception, attempt) called on each retry

    Example:
        @retry_with_backoff(max_retries=3, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            return requests.get('https://api.example.com')
    """
    # Get defaults from environment if not specified
    if max_retries is None:
        max_retries = int(os.getenv('MAX_RETRIES', '3'))

    if backoff_multiplier is None:
        backoff_multiplier = float(os.getenv('RETRY_BACKOFF', '2'))

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        # Final attempt failed
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    # Calculate wait time with exponential backoff
                    wait_time = backoff_multiplier ** attempt

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")

                    # Wait before retrying
                    time.sleep(wait_time)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def retry_on_rate_limit(
    max_retries: int = 5,
    base_wait: float = 1.0,
    rate_limit_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Specialized retry decorator for API rate limiting.

    Implements a more aggressive backoff for rate limit errors.

    Args:
        max_retries: Maximum retry attempts
        base_wait: Base wait time in seconds
        rate_limit_exceptions: Exception types that indicate rate limiting
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except rate_limit_exceptions as e:
                    if attempt >= max_retries:
                        logger.error(
                            f"{func.__name__} rate limited after {max_retries + 1} attempts"
                        )
                        raise

                    # Aggressive exponential backoff for rate limits
                    wait_time = base_wait * (2 ** attempt)

                    logger.warning(
                        f"{func.__name__} rate limited (attempt {attempt + 1}). "
                        f"Waiting {wait_time:.1f}s..."
                    )

                    time.sleep(wait_time)

        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    After a certain number of failures, the circuit "opens" and stops
    attempting the operation for a cooldown period.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        expected_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            cooldown_seconds: Time to wait before trying again after opening
            expected_exceptions: Exceptions that count as failures
        """
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.expected_exceptions = expected_exceptions

        self.failure_count = 0
        self.last_failure_time = 0
        self.is_open = False

    def call(self, func: Callable, *args, **kwargs):
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function

        Raises:
            Exception: If circuit is open or function fails
        """
        # Check if circuit is open
        if self.is_open:
            time_since_failure = time.time() - self.last_failure_time

            if time_since_failure < self.cooldown_seconds:
                raise RuntimeError(
                    f"Circuit breaker is open. "
                    f"Try again in {self.cooldown_seconds - time_since_failure:.1f}s"
                )
            else:
                # Cooldown period over, try half-open
                logger.info("Circuit breaker entering half-open state")
                self.is_open = False
                self.failure_count = 0

        try:
            result = func(*args, **kwargs)

            # Success - reset failure count
            if self.failure_count > 0:
                logger.info("Circuit breaker reset after successful call")
                self.failure_count = 0

            return result

        except self.expected_exceptions as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            logger.warning(
                f"Circuit breaker failure {self.failure_count}/{self.failure_threshold}: {e}"
            )

            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                logger.error(
                    f"Circuit breaker opened after {self.failure_count} failures. "
                    f"Cooldown: {self.cooldown_seconds}s"
                )

            raise

    def reset(self):
        """Manually reset the circuit breaker."""
        self.is_open = False
        self.failure_count = 0
        self.last_failure_time = 0
        logger.info("Circuit breaker manually reset")

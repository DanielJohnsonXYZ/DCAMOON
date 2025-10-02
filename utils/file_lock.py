"""
File Locking Utilities

Provides cross-platform file locking to prevent data corruption
during concurrent file access.
"""
import logging
import sys
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Platform-specific locking
if sys.platform == 'win32':
    import msvcrt

    @contextmanager
    def file_lock(file_path: Path, timeout: float = 10.0):
        """
        Windows file locking using msvcrt

        Args:
            file_path: Path to the file to lock
            timeout: Maximum time to wait for lock (seconds)
        """
        lock_file = Path(str(file_path) + '.lock')
        start_time = time.time()
        file_handle = None

        try:
            # Create lock file
            while True:
                try:
                    file_handle = open(lock_file, 'w')
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    logger.debug(f"Acquired lock on {file_path}")
                    break
                except (IOError, OSError):
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Could not acquire lock on {file_path} after {timeout}s")
                    time.sleep(0.1)

            yield

        finally:
            # Release lock
            if file_handle:
                try:
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    file_handle.close()
                    lock_file.unlink(missing_ok=True)
                    logger.debug(f"Released lock on {file_path}")
                except Exception as e:
                    logger.warning(f"Error releasing lock: {e}")

else:  # Unix/Linux/macOS
    import fcntl

    @contextmanager
    def file_lock(file_path: Path, timeout: float = 10.0):
        """
        Unix file locking using fcntl

        Args:
            file_path: Path to the file to lock
            timeout: Maximum time to wait for lock (seconds)
        """
        lock_file = Path(str(file_path) + '.lock')
        start_time = time.time()
        file_handle = None

        try:
            # Create lock file
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            file_handle = open(lock_file, 'w')

            # Try to acquire lock
            while True:
                try:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.debug(f"Acquired lock on {file_path}")
                    break
                except (IOError, OSError):
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Could not acquire lock on {file_path} after {timeout}s")
                    time.sleep(0.1)

            yield

        finally:
            # Release lock
            if file_handle:
                try:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                    file_handle.close()
                    lock_file.unlink(missing_ok=True)
                    logger.debug(f"Released lock on {file_path}")
                except Exception as e:
                    logger.warning(f"Error releasing lock: {e}")


def atomic_write(file_path: Path, data: str, encoding: str = 'utf-8'):
    """
    Write to a file atomically by writing to a temp file and then moving it.

    This prevents partial writes if the process crashes.

    Args:
        file_path: Target file path
        data: String data to write
        encoding: Text encoding (default: utf-8)
    """
    temp_file = Path(str(file_path) + '.tmp')

    try:
        # Write to temporary file
        with open(temp_file, 'w', encoding=encoding) as f:
            f.write(data)
            f.flush()
            import os
            os.fsync(f.fileno())  # Ensure written to disk

        # Atomic move
        temp_file.replace(file_path)
        logger.debug(f"Atomically wrote to {file_path}")

    except Exception as e:
        # Clean up temp file on error
        if temp_file.exists():
            temp_file.unlink()
        raise


@contextmanager
def locked_csv_write(csv_path: Path, timeout: float = 10.0):
    """
    Context manager for safe CSV writing with file locking.

    Usage:
        with locked_csv_write(csv_path) as temp_path:
            df.to_csv(temp_path, index=False)

    Args:
        csv_path: Path to CSV file
        timeout: Lock timeout in seconds
    """
    with file_lock(csv_path, timeout=timeout):
        temp_file = Path(str(csv_path) + '.tmp')
        try:
            yield temp_file
            # Atomic move after successful write
            if temp_file.exists():
                temp_file.replace(csv_path)
                logger.debug(f"Successfully wrote {csv_path}")
        finally:
            # Clean up temp file if it still exists
            if temp_file.exists():
                temp_file.unlink()

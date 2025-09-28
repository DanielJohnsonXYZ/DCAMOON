"""Database connection and session management for DCAMOON."""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager.
        
        Args:
            database_url: Database connection URL. If None, uses environment variable
                         or defaults to SQLite.
        """
        if database_url is None:
            database_url = os.getenv(
                'DATABASE_URL', 
                'sqlite:///dcamoon.db'
            )
        
        self.database_url = database_url
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Enable foreign key constraints for SQLite
        if database_url.startswith('sqlite'):
            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    
    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with appropriate settings."""
        
        if self.database_url.startswith('sqlite'):
            # SQLite configuration
            engine = create_engine(
                self.database_url,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30
                },
                echo=os.getenv('SQL_DEBUG', 'false').lower() == 'true'
            )
        else:
            # PostgreSQL/other database configuration
            engine = create_engine(
                self.database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=os.getenv('SQL_DEBUG', 'false').lower() == 'true'
            )
        
        logger.info(f"Database engine created for: {self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url}")
        return engine
    
    def create_tables(self) -> None:
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def drop_tables(self) -> None:
        """Drop all database tables. USE WITH CAUTION!"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Error dropping database tables: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def get_db_info(self) -> dict:
        """Get database information."""
        try:
            with self.session_scope() as session:
                if self.database_url.startswith('sqlite'):
                    result = session.execute(text("SELECT sqlite_version()")).fetchone()
                    version = result[0] if result else "Unknown"
                    db_type = "SQLite"
                else:
                    result = session.execute(text("SELECT version()")).fetchone()
                    version = result[0] if result else "Unknown"
                    db_type = "PostgreSQL"
                
                return {
                    "type": db_type,
                    "version": version,
                    "url": self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url,
                    "healthy": True
                }
        except Exception as e:
            logger.error(f"Error getting database info: {e}")
            return {
                "type": "Unknown",
                "version": "Unknown", 
                "url": self.database_url,
                "healthy": False,
                "error": str(e)
            }


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db_session() -> Session:
    """Get a database session from the global manager."""
    return get_db_manager().get_session()


@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """Get a database session with automatic transaction management."""
    with get_db_manager().session_scope() as session:
        yield session


def initialize_database(database_url: Optional[str] = None, create_tables: bool = True) -> DatabaseManager:
    """Initialize the database with optional table creation.
    
    Args:
        database_url: Database connection URL
        create_tables: Whether to create tables if they don't exist
        
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    _db_manager = DatabaseManager(database_url)
    
    if create_tables:
        _db_manager.create_tables()
    
    # Test connection
    if not _db_manager.health_check():
        raise RuntimeError("Failed to establish database connection")
    
    logger.info("Database initialized successfully")
    return _db_manager
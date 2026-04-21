"""
Database connection management for job scraper
Supports PostgreSQL with connection pooling and transaction management
"""

import asyncio
import asyncpg
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, List, Any
import json
from pathlib import Path
import sys

# Add config to path
sys.path.append(str(Path(__file__).parent.parent / "config"))

try:
    # Try to import from config package
    from settings import DATABASE_SETTINGS
except ImportError:
    try:
        # Fallback: try direct import from config directory
        from config.settings import DATABASE_SETTINGS
    except ImportError:
        # No fallback - require proper settings.py
        raise ImportError(
            "[ERROR] DATABASE_SETTINGS not found! "
            "Please ensure src/config/settings.py exists and is properly configured. "
            "Run: python scripts/setup_database.py to initialize."
        )

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        """Initialize database manager with connection pool"""
        self.pool: Optional[asyncpg.Pool] = None
        self.is_connected = False
        
        # Database configuration from enhanced settings
        self.host = DATABASE_SETTINGS.get('host', 'localhost')
        self.port = DATABASE_SETTINGS.get('port', 5432)
        self.database = DATABASE_SETTINGS.get('database', 'job_market_data')
        self.username = DATABASE_SETTINGS.get('username', 'postgres')
        self.password = DATABASE_SETTINGS.get('password', 'working')
        self.min_connections = DATABASE_SETTINGS.get('min_connections', 5)
        self.max_connections = DATABASE_SETTINGS.get('max_connections', 20)
        self.connection_timeout = DATABASE_SETTINGS.get('connection_timeout', 60)
        self.command_timeout = DATABASE_SETTINGS.get('command_timeout', 30)
        self.ssl_mode = DATABASE_SETTINGS.get('ssl_mode', 'prefer')
        self.enable_logging = DATABASE_SETTINGS.get('enable_logging', True)
        
        # Connection statistics
        self.connection_stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'total_queries': 0,
            'failed_queries': 0
        }
        
        logger.info(f"DatabaseManager initialized for {self.host}:{self.port}/{self.database}")
        logger.info(f"Connection pool: {self.min_connections}-{self.max_connections}, SSL: {self.ssl_mode}")
    
    async def connect(self) -> bool:
        """Establish connection pool to PostgreSQL database"""
        try:
            self.connection_stats['total_connections'] += 1
            logger.info("Connecting to PostgreSQL database...")
            
            # Build connection string with SSL mode
            if self.ssl_mode and self.ssl_mode != 'prefer':
                dsn = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"
            else:
                dsn = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
            
            # Create connection pool with enhanced settings
            self.pool = await asyncpg.create_pool(
                dsn,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=self.command_timeout,
                init=self._init_connection if self.enable_logging else None,
                server_settings={
                    'jit': 'off',  # Disable JIT for faster small queries
                    'timezone': 'UTC'  # Use UTC timezone
                }
            )
            
            # Test connection
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT version()")
                if self.enable_logging:
                    logger.info(f"Connected to PostgreSQL: {result[:50]}...")
            
            self.is_connected = True
            self.connection_stats['successful_connections'] += 1
            logger.info(f"Database connection pool established successfully")
            logger.info(f"Pool configuration: {self.min_connections}-{self.max_connections} connections, timeout: {self.command_timeout}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self.connection_stats['failed_connections'] += 1
            self.is_connected = False
            return False
    
    async def _init_connection(self, conn):
        """Initialize connection with custom settings"""
        if self.enable_logging:
            logger.debug(f"Initializing database connection {id(conn)}")
    
    async def disconnect(self):
        """Close all database connections"""
        if self.pool:
            try:
                await self.pool.close()
                logger.info("Database connection pool closed")
            except Exception as e:
                logger.error(f"Error closing database pool: {e}")
        
        self.is_connected = False
        self.pool = None
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool (context manager)"""
        if not self.pool:
            raise Exception("Database not connected. Call connect() first.")
        
        conn = None
        try:
            conn = await self.pool.acquire()
            yield conn
        finally:
            if conn:
                await self.pool.release(conn)
    
    @asynccontextmanager
    async def get_transaction(self):
        """Get database transaction (context manager)"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                yield conn
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results as list of dictionaries"""
        try:
            self.connection_stats['total_queries'] += 1
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *args)
                result = [dict(row) for row in rows]
                if self.enable_logging:
                    logger.debug(f"Query executed successfully, returned {len(result)} rows")
                return result
        except Exception as e:
            self.connection_stats['failed_queries'] += 1
            logger.error(f"Query execution failed: {e}")
            if self.enable_logging:
                logger.error(f"Query: {query}")
            raise
    
    async def execute_single(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute SELECT query and return single result"""
        try:
            self.connection_stats['total_queries'] += 1
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query, *args)
                result = dict(row) if row else None
                if self.enable_logging:
                    logger.debug(f"Single query executed successfully, returned {'1 row' if result else 'no rows'}")
                return result
        except Exception as e:
            self.connection_stats['failed_queries'] += 1
            logger.error(f"Single query execution failed: {e}")
            if self.enable_logging:
                logger.error(f"Query: {query}")
            raise
    
    async def execute_command(self, query: str, *args) -> str:
        """Execute INSERT/UPDATE/DELETE and return status"""
        try:
            async with self.get_connection() as conn:
                result = await conn.execute(query, *args)
                logger.debug(f"Command executed: {result}")
                return result
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            logger.error(f"Query: {query}")
            raise
    
    async def execute_many(self, query: str, args_list: List[tuple]) -> str:
        """Execute query with multiple parameter sets"""
        try:
            async with self.get_connection() as conn:
                result = await conn.executemany(query, args_list)
                logger.debug(f"Batch command executed: {result}")
                return result
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            logger.error(f"Query: {query}")
            raise
    
    async def check_table_exists(self, table_name: str) -> bool:
        """Check if table exists in database"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = $1
            )
        """
        result = await self.execute_single(query, table_name)
        return result['exists'] if result else False
    
    async def create_tables_from_schema(self, schema_path: str = None):
        """Create tables from SQL schema file"""
        if not schema_path:
            schema_path = Path(__file__).parent / "schema.sql"
        
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            async with self.get_transaction() as conn:
                await conn.execute(schema_sql)
            
            logger.info(f"Database schema created from {schema_path}")
            
        except FileNotFoundError:
            logger.warning(f"Schema file not found: {schema_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            raise
    
    async def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table column information"""
        query = """
            SELECT 
                column_name, 
                data_type, 
                is_nullable, 
                column_default
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = $1
            ORDER BY ordinal_position
        """
        return await self.execute_query(query, table_name)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get database health and connection status"""
        try:
            if not self.is_connected or not self.pool:
                return {
                    'status': 'disconnected',
                    'error': 'No database connection'
                }
            
            # Check pool status
            pool_info = {
                'min_size': self.pool._minsize,
                'max_size': self.pool._maxsize,
                'current_size': self.pool.get_size(),
                'idle_connections': self.pool.get_idle_size()
            }
            
            # Test query
            async with self.get_connection() as conn:
                start_time = asyncio.get_event_loop().time()
                await conn.fetchval("SELECT 1")
                query_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'database': self.database,
                'host': self.host,
                'port': self.port,
                'ssl_mode': self.ssl_mode,
                'pool_info': pool_info,
                'query_time_ms': round(query_time, 2),
                'connection_stats': self.connection_stats,
                'settings': {
                    'min_connections': self.min_connections,
                    'max_connections': self.max_connections,
                    'connection_timeout': self.connection_timeout,
                    'command_timeout': self.command_timeout,
                    'logging_enabled': self.enable_logging
                }
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'connection_stats': self.connection_stats
            }
    
    def get_connection_statistics(self) -> Dict[str, Any]:
        """Get detailed connection and query statistics"""
        stats = self.connection_stats.copy()
        
        # Calculate derived statistics
        total_connections = stats['total_connections']
        total_queries = stats['total_queries']
        
        if total_connections > 0:
            stats['connection_success_rate'] = (stats['successful_connections'] / total_connections) * 100
            stats['connection_failure_rate'] = (stats['failed_connections'] / total_connections) * 100
        else:
            stats['connection_success_rate'] = 0
            stats['connection_failure_rate'] = 0
        
        if total_queries > 0:
            stats['query_success_rate'] = ((total_queries - stats['failed_queries']) / total_queries) * 100
            stats['query_failure_rate'] = (stats['failed_queries'] / total_queries) * 100
        else:
            stats['query_success_rate'] = 0
            stats['query_failure_rate'] = 0
        
        # Add pool information if connected
        if self.pool:
            stats['pool_status'] = {
                'is_connected': self.is_connected,
                'current_size': self.pool.get_size(),
                'idle_connections': self.pool.get_idle_size(),
                'max_size': self.pool._maxsize,
                'min_size': self.pool._minsize
            }
        
        return stats

# Global database manager instance
db_manager = DatabaseManager()

# Backward compatibility alias in case something is looking for DatabaseConnection
DatabaseConnection = DatabaseManager

# Convenience functions for common operations
async def init_database() -> bool:
    """Initialize database connection"""
    return await db_manager.connect()

async def close_database():
    """Close database connection"""
    await db_manager.disconnect()

async def get_db_connection():
    """Get database connection (context manager)"""
    return db_manager.get_connection()

async def get_db_transaction():
    """Get database transaction (context manager)"""
    return db_manager.get_transaction()

# Example usage and testing
async def test_connection():
    """Test database connection"""
    try:
        success = await init_database()
        if success:
            logger.info(" Database connection test successful")
            
            # Get health status
            health = await db_manager.get_health_status()
            logger.info(f"Database health: {health}")
            
            await close_database()
            return True
        else:
            logger.error("L Database connection test failed")
            return False
            
    except Exception as e:
        logger.error(f"Database test error: {e}")
        return False

if __name__ == "__main__":
    # Test the database connection
    import asyncio
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(test_connection())
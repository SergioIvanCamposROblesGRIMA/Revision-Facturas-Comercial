from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from typing import Generator
from config.settings import settings
from models.registro import Base
from utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    '''Gestor optimizado de base de datos con soporte para Concurrencia (WAL Mode)'''
    
    _instance = None
    _engine = None
    _session_factory = None
    
    def __new__(cls):
        '''Singleton para evitar múltiples instancias'''
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._engine is None:
            self._initialize_engine()
    
    def _initialize_engine(self):
        '''Inicializa el engine con configuración optimizada para alta concurrencia'''
        
        # Configuración del pool
        connect_args = {}
        pool_config = {}
        
        if 'sqlite' in settings.DATABASE_URL:
            # SQLite: Configuración específica para Concurrencia
            connect_args = {
                'check_same_thread': False, # Necesario para FastAPI + Threads
                # Usar el timeout configurado o 30s por defecto
                'timeout': getattr(settings, 'DB_TIMEOUT', 30) 
            }
            # NOTA: Eliminamos pool.StaticPool. 
            # Para que WAL funcione con múltiples hilos, necesitamos permitir 
            # múltiples conexiones (SQLAlchemy usará QueuePool por defecto).
            pool_config = {} 
        else:
            # PostgreSQL/MySQL: Pool normal
            pool_config = {
                'pool_size': 10,
                'max_overflow': 20,
                'pool_pre_ping': True,
                'pool_recycle': 3600
            }
        
        # Crear engine
        self._engine = create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            echo=False,
            future=True,
            **pool_config
        )
        
        # Event listeners (Aquí activamos WAL)
        self._setup_event_listeners()
        
        # Session factory
        session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        self._session_factory = scoped_session(session_factory)
        
        logger.info('✅ Database engine inicializado')
    
    def _setup_event_listeners(self):
        '''Configura listeners para logging y optimización WAL'''
        
        # ACTIVACIÓN DE MODO WAL PARA SQLITE
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            # Solo aplicar si es SQLite
            if "sqlite" in settings.DATABASE_URL:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        @event.listens_for(self._engine, 'connect')
        def receive_connect(dbapi_conn, connection_record):
            '''Log cuando se crea una nueva conexión'''
            logger.debug('Nueva conexión a DB establecida')
        
        @event.listens_for(self._engine, 'checkin')
        def receive_checkin(dbapi_conn, connection_record):
            '''Log cuando una conexión regresa al pool'''
            logger.debug('Conexión devuelta al pool')
    
    def create_tables(self):
        '''Crea todas las tablas en la base de datos'''
        try:
            Base.metadata.create_all(bind=self._engine)
            logger.info('✅ Tablas de base de datos creadas/verificadas')
        except SQLAlchemyError as e:
            logger.error(f'❌ Error al crear tablas: {e}')
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        '''Context manager para sesiones thread-safe'''
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f'Error en sesión DB: {e}')
            raise
        finally:
            session.close()
    
    def get_scoped_session(self) -> scoped_session:
        '''Retorna la scoped_session para uso directo'''
        return self._session_factory
    
    def dispose(self):
        '''Cierra todas las conexiones del pool'''
        if self._engine:
            self._engine.dispose()
            logger.info('Pool de conexiones cerrado')

db_manager = DatabaseManager()
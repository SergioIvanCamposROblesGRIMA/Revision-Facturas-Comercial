import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

# Obtener ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    '''Configuración centralizada usando Pydantic Settings'''
    
    # Paths
    BASE_DIR: Path = BASE_DIR
    DB_DIR: Path = BASE_DIR / 'db'
    LOGS_DIR: Path = BASE_DIR / 'logs'
    REPORTS_DIR: Path = BASE_DIR / 'reports'
    CONFIG_DIR: Path = BASE_DIR / 'config'
    
    # Database
    DATABASE_URL: str = Field(
        default=f'sqlite:///{BASE_DIR}/db/facturas_oc.db',
        description='URL de conexión a la base de datos'
    )
    DB_TIMEOUT: int = Field(default=30, description="Timeout en segundos para SQLite")
    
    # OpenAI
    OPENAI_API_KEY: str = Field(..., description='API Key de OpenAI')
    OPENAI_MODEL: str = Field(default='gpt-4o', description='Modelo de OpenAI a usar')
    OPENAI_MAX_TOKENS: int = Field(default=1500, description='Tokens máximos por respuesta')
    
    # Google
    GOOGLE_CREDENTIALS_PATH: str = Field(
        default=str(BASE_DIR / 'config' / 'google_credentials.json'),
        description='Ruta al archivo de credenciales de Google'
    )
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = Field(
        default=None,
        description='ID de la carpeta de Google Drive'
    )
    GOOGLE_DRIVE_INVOICES_FOLDER_ID: str = Field(
        default="1TvGNPucUb-8mjvO7EOSQNX6Z7bHEBd4g", 
        description='ID carpeta para PDFs de facturas'
    )
    GOOGLE_CHAT_WEBHOOK_URL: str = Field(..., description='URL del webhook de Google Chat')
    
    # Validation
    VALIDATION_HOUR: str = Field(default='09:30', description='Hora de validación diaria (HH:MM)')
    
    # Webhook
    WEBHOOK_PORT: int = Field(default=8000, ge=1, le=65535, description='Puerto del webhook')
    WEBHOOK_HOST: str = Field(default='0.0.0.0', description='Host del webhook')
    
    # Logging
    LOG_LEVEL: str = Field(default='INFO', description='Nivel de logging')
    LOG_FILE: str = Field(
        default=str(BASE_DIR / 'logs' / 'app.log'),
        description='Archivo de log'
    )
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = True
    
    def ensure_directories(self):
        '''Asegura que los directorios necesarios existan'''
        for directory in [self.DB_DIR, self.LOGS_DIR, self.REPORTS_DIR, self.CONFIG_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_production(self) -> bool:
        '''Verifica si está en producción'''
        return os.getenv('ENVIRONMENT', 'development').lower() == 'production'

# Singleton de configuración
settings = Settings()
settings.ensure_directories()

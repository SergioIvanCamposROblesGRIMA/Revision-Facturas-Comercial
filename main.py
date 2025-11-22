import uvicorn
import schedule
import time
import threading
import signal
import sys
from datetime import datetime
from config.settings import settings
from db.database import db_manager
from services.webhook.handler import WebhookHandler
from services.validator.validator import ValidadorRegistros
from services.report.generator import ExcelReportGenerator
from services.google.drive_service import GoogleDriveService
from services.google.chat_service import GoogleChatService
from utils.logger import get_logger

logger = get_logger(__name__)

class OrquestadorPrincipal:
    '''Orquestador principal optimizado del sistema'''
    
    def __init__(self):
        self.validador = ValidadorRegistros()
        self.report_generator = ExcelReportGenerator()
        self.drive_service = GoogleDriveService()
        self.chat_service = GoogleChatService()
        self.webhook_handler = WebhookHandler()
        self.scheduler_thread = None
        self.running = False
    
    def inicializar_sistema(self):
        '''Inicializa el sistema completo con verificaciones'''
        self._print_banner()
        
        try:
            # Verificar directorios
            settings.ensure_directories()
            logger.info('✅ Directorios verificados')
            
            # Inicializar base de datos
            db_manager.create_tables()
            logger.info('✅ Base de datos inicializada')
            
        except Exception as e:
            logger.error(f'❌ Error fatal en inicialización: {e}')
            raise
    
    def _print_banner(self):
        '''Imprime banner de inicio'''
        banner = '''
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     🧾 SISTEMA DE VALIDACIÓN DE FACTURAS Y ÓRDENES DE COMPRA       ║
║                                                                      ║
║     Versión: 2.4.0 (Assistants API + Drive PDF + Chat Requests)      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
        '''
        print(banner)
        logger.info('🚀 INICIANDO SISTEMA')
    
    def ejecutar_validacion(self):
        '''Ejecuta el proceso completo de validación'''
        inicio = datetime.now()
        
        logger.info('')
        logger.info('╔' + '═' * 68 + '╗')
        logger.info('║' + ' ' * 15 + '🔍 INICIANDO PROCESO DE VALIDACIÓN' + ' ' * 18 + '║')
        logger.info('║' + f' Hora: {inicio.strftime("%Y-%m-%d %H:%M:%S")}'.ljust(68) + '║')
        logger.info('╚' + '═' * 68 + '╝')
        
        try:
            # 1. Validar registros
            logger.info('\n📋 PASO 1: Validando registros...')
            resultados = self.validador.validar_todos_los_registros()
            
            if not resultados:
                logger.info('ℹ️  No hay registros para procesar en este momento')
                return
            
            # 2. Generar reporte (incluye subida de PDFs a Drive)
            logger.info('\n📊 PASO 2: Generando reporte Excel...')
            archivo_reporte = self.report_generator.generar_reporte(resultados)
            
            # 3. Subir Excel a Google Drive (Método corregido)
            logger.info('\n☁️  PASO 3: Subiendo Reporte Excel a Google Drive...')
            # Nota: Aquí subimos el Excel a la carpeta general (configurada en settings por defecto)
            link_drive = self.drive_service.upload_to_drive(archivo_reporte)
            
            # 4. Enviar notificación (Método corregido)
            logger.info('\n💬 PASO 4: Enviando notificación...')
            
            # Generar resumen de estadísticas
            total = len(resultados)
            anomalias = sum(1 for r in resultados if r['es_anomalia'])
            correctos = total - anomalias
            
            # Formato de texto simple para el resumen (el Service le pone el header bonito)
            resumen_texto = (
                f"📊 *Resumen de Ejecución:*\n"
                f"• Total procesados: *{total}*\n"
                f"• ✅ Correctos: *{correctos}*\n"
                f"• ⚠️ Anomalías: *{anomalias}*"
            )
            
            self.chat_service.send_advice(link=link_drive, resumen=resumen_texto)
            
            # Estadísticas finales de tiempo
            fin = datetime.now()
            duracion = (fin - inicio).total_seconds()
            
            logger.info('')
            logger.info('╔' + '═' * 68 + '╗')
            logger.info('║' + ' ' * 18 + '✅ PROCESO COMPLETADO' + ' ' * 28 + '║')
            logger.info('║' + f' Duración: {duracion:.2f} segundos'.ljust(68) + '║')
            logger.info('║' + f' Registros: {len(resultados)}'.ljust(68) + '║')
            logger.info('║' + f' Reporte: {link_drive[:40]}...'.ljust(68) + '║')
            logger.info('╚' + '═' * 68 + '╝')
            logger.info('')
            
        except Exception as e:
            logger.error(f'\n❌ ERROR EN PROCESO DE VALIDACIÓN: {e}', exc_info=True)
            
            # Intentar notificar el error usando el nuevo método send_advice
            try:
                error_msg = f"⚠️ *ERROR CRÍTICO EN VALIDACIÓN*\n\nError: {str(e)[:200]}"
                self.chat_service.send_advice(link="N/A", resumen=error_msg)
            except Exception as e2:
                logger.error(f'No se pudo enviar notificación de error: {e2}')
    
    def programar_validacion(self):
        '''Programa la validación automática diaria'''
        schedule.every().day.at(settings.VALIDATION_HOUR).do(self.ejecutar_validacion)
        
        logger.info(f'⏰ Validación programada para las {settings.VALIDATION_HOUR} diariamente')
        
        def ejecutar_schedule():
            self.running = True
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Revisar cada minuto
        
        # Ejecutar en thread separado
        self.scheduler_thread = threading.Thread(target=ejecutar_schedule, daemon=True)
        self.scheduler_thread.start()
        logger.info('✅ Scheduler iniciado en background')
    
    def iniciar_webhook(self):
        '''Inicia el servidor del webhook'''
        logger.info('')
        logger.info('╔' + '═' * 68 + '╗')
        logger.info('║' + ' ' * 20 + '🌐 WEBHOOK INICIADO' + ' ' * 28 + '║')
        logger.info('║' + f' URL: http://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}'.ljust(68) + '║')
        logger.info('║' + f' Docs: http://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}/docs'.ljust(68) + '║')
        logger.info('╚' + '═' * 68 + '╝')
        logger.info('')
        
        uvicorn.run(
            self.webhook_handler.app,
            host=settings.WEBHOOK_HOST,
            port=settings.WEBHOOK_PORT,
            log_level="info",
            access_log=False
        )
    
    def detener(self):
        '''Detiene el sistema gracefully'''
        logger.info('\n🛑 Deteniendo sistema...')
        self.running = False
        
        # Cerrar conexiones de DB
        db_manager.dispose()
        
        logger.info('👋 Sistema detenido correctamente')
    
    def iniciar(self):
        '''Inicia el sistema completo'''
        self.inicializar_sistema()
        self.programar_validacion()
        self.iniciar_webhook()

def signal_handler(signum, frame):
    '''Manejador de señales para shutdown graceful'''
    logger.info('\n⚠️  Señal de interrupción recibida')
    sys.exit(0)

def main():
    '''Función principal con manejo de errores'''
    # Registrar manejadores de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    orquestador = None
    
    try:
        orquestador = OrquestadorPrincipal()
        orquestador.iniciar()
        
    except KeyboardInterrupt:
        logger.info('\n👋 Sistema detenido por el usuario')
        
    except Exception as e:
        logger.error(f'\n❌ Error fatal: {e}', exc_info=True)
        sys.exit(1)
        
    finally:
        if orquestador:
            orquestador.detener()

if __name__ == '__main__':
    main()
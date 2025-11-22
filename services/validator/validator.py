from typing import List, Dict
from datetime import datetime
from sqlalchemy import and_
from models.registro import RegistroWebhook
from db.database import db_manager
from services.openai.client import OpenAIService
from utils.logger import get_logger

logger = get_logger(__name__)

class TipoAnomalia:
    '''Constantes para tipos de anomalías'''
    SIN_OC = 'sin_oc'
    SIN_FACTURA = 'sin_factura'
    SIN_OC_NI_FACTURA = 'sin_oc_ni_factura'
    ERROR_PROCESAMIENTO = 'error_procesamiento_factura'
    DISCREPANCIAS = 'discrepancias_encontradas'

class ValidadorRegistros:
    '''Servicio optimizado de validación de registros'''
    
    def __init__(self):
        self.openai_service = OpenAIService()
    
    def validar_todos_los_registros(self) -> List[Dict]:
        '''Valida todos los registros pendientes de forma eficiente'''
        logger.info('=' * 70)
        logger.info('🔍 INICIANDO VALIDACIÓN DE REGISTROS')
        logger.info('=' * 70)
        
        registros = self._obtener_registros_pendientes()
        
        if not registros:
            logger.info('ℹ️  No hay registros pendientes para validar')
            return []
        
        logger.info(f'📊 Encontrados {len(registros)} registros pendientes')
        
        resultados = []
        exitosos = 0
        con_errores = 0
        
        for idx, registro in enumerate(registros, 1):
            try:
                logger.info(f'')
                logger.info(f'▶️  Validando registro {idx}/{len(registros)} (ID: {registro.id})')
                logger.info(f'   📅 Recibido: {registro.fecha_recepcion}')
                logger.info(f'   📋 OCs: {registro.num_ordenes} | 📄 Factura: {"✓" if registro.tiene_factura else "✗"}')
                
                resultado = self._validar_registro_individual(registro)
                resultados.append(resultado)
                self._actualizar_registro(registro.id, resultado)
                
                exitosos += 1
                logger.info(f'   ✅ Registro {registro.id} procesado exitosamente')
                
            except Exception as e:
                con_errores += 1
                logger.error(f'   ❌ Error al procesar registro {registro.id}: {e}')
                # Crear resultado de error
                resultado_error = {
                    'registro_id': registro.id,
                    'fecha_recepcion': registro.fecha_recepcion,
                    'tiene_oc': registro.tiene_oc,
                    'tiene_factura': registro.tiene_factura,
                    'es_anomalia': True,
                    'tipo_anomalia': TipoAnomalia.ERROR_PROCESAMIENTO,
                    'resultado_openai': f'Error: {str(e)}',
                    'datos_factura': None,
                    # 👇 CRÍTICO: Mantener raw para que el reporte pueda generar el PDF
                    'factura_base64_raw': registro.factura_base64
                }
                resultados.append(resultado_error)
                self._actualizar_registro(registro.id, resultado_error)
        
        logger.info('')
        logger.info('=' * 70)
        logger.info(f'✅ VALIDACIÓN COMPLETADA')
        logger.info(f'   Total procesados: {len(resultados)}')
        logger.info(f'   Exitosos: {exitosos}')
        logger.info(f'   Con errores: {con_errores}')
        logger.info('=' * 70)
        
        return resultados
    
    def _obtener_registros_pendientes(self) -> List[RegistroWebhook]:
        '''Obtiene registros no procesados con query optimizada'''
        with db_manager.get_session() as session:
            # Query optimizada con filtros
            registros = session.query(RegistroWebhook).filter(
                and_(
                    RegistroWebhook.procesado == False,
                    RegistroWebhook.fecha_recepcion != None
                )
            ).order_by(RegistroWebhook.fecha_recepcion.asc()).all()
            
            # Expunge para usar fuera de la sesión
            for registro in registros:
                session.expunge(registro)
            
            return registros
    
    def _validar_registro_individual(self, registro: RegistroWebhook) -> Dict:
        '''Valida un registro individual con lógica REESTRUCTURADA (Extracción Primero)'''
        resultado = {
            'registro_id': registro.id,
            'fecha_recepcion': registro.fecha_recepcion,
            'tiene_oc': registro.tiene_oc,
            'tiene_factura': registro.tiene_factura,
            'es_anomalia': False,
            'tipo_anomalia': None,
            'resultado_openai': None,
            'datos_factura': None,
            'num_ordenes': registro.num_ordenes,
            # 👇 CRÍTICO: Pasamos el raw para el reporte
            'factura_base64_raw': registro.factura_base64
        }
        
        # 1. VALIDACIÓN DE EXISTENCIA DE FACTURA
        # Si no hay factura, no podemos extraer nada.
        if not registro.tiene_factura:
            if not registro.tiene_oc:
                logger.warning(f'   ⚠️  Sin OC ni factura')
                resultado['es_anomalia'] = True
                resultado['tipo_anomalia'] = TipoAnomalia.SIN_OC_NI_FACTURA
            else:
                logger.warning(f'   ⚠️  Sin factura (pero tiene {registro.num_ordenes} OCs)')
                resultado['es_anomalia'] = True
                resultado['tipo_anomalia'] = TipoAnomalia.SIN_FACTURA
            return resultado 
            
        # 2. EXTRACCIÓN DE DATOS (¡SIEMPRE PRIMERO!)
        # Intentamos extraer los datos de la factura INDEPENDIENTEMENTE de si hay OC.
        logger.info(f'   📄 Extrayendo datos de factura (para reporte)...')
        try:
            datos_factura, _ = self.openai_service.extraer_datos_factura(registro.factura_base64)
            resultado['datos_factura'] = datos_factura
            
            if datos_factura:
                prov = datos_factura.get("proveedor", "N/A")
                total = datos_factura.get("gran_total", "N/A")
                logger.info(f'   ✓ Datos extraídos: Prov={prov}, Total={total}')
            else:
                logger.error('   ❌ OpenAI retornó datos nulos')
        except Exception as e:
            logger.error(f'   ❌ Error extrayendo datos: {e}')
            datos_factura = None

        # 3. VALIDACIÓN DE EXISTENCIA DE OC
        # Ahora sí, si no hay OC, nos salimos, pero YA TENEMOS LOS DATOS guardados en 'resultado'.
        if not registro.tiene_oc:
            logger.warning(f'   ⚠️  Sin OC (Datos de factura guardados para reporte)')
            resultado['es_anomalia'] = True
            resultado['tipo_anomalia'] = TipoAnomalia.SIN_OC
            resultado['resultado_openai'] = "No se pudo comparar: Falta Orden de Compra."
            return resultado 
        
        # 4. COMPARACIÓN (Solo si tenemos ambos y la extracción fue exitosa)
        if datos_factura:
            logger.info(f'   🔍 Comparando con {registro.num_ordenes} órdenes de compra...')
            comparacion = self.openai_service.comparar_factura_oc(
                datos_factura,
                registro.ordenes_de_compra
            )
            
            resultado['resultado_openai'] = comparacion
            
            # Verificar si hay discrepancias
            comparacion_upper = comparacion.strip().upper()
            if 'OK' in comparacion_upper and 'DISCREPANCIA' not in comparacion_upper:
                logger.info(f'   ✅ Todo coincide correctamente')
                resultado['es_anomalia'] = False
            else:
                logger.warning(f'   ⚠️  Discrepancias encontradas')
                resultado['es_anomalia'] = True
                resultado['tipo_anomalia'] = TipoAnomalia.DISCREPANCIAS
        else:
            # Hubo factura pero falló la extracción (PDF corrupto o ilegible)
            resultado['es_anomalia'] = True
            resultado['tipo_anomalia'] = TipoAnomalia.ERROR_PROCESAMIENTO
            if not resultado['resultado_openai']:
                resultado['resultado_openai'] = 'Falló la extracción de datos del PDF.'
        
        return resultado
    
    def _actualizar_registro(self, registro_id: int, resultado: Dict):
        '''Actualiza el registro en la base de datos'''
        try:
            with db_manager.get_session() as session:
                session.query(RegistroWebhook).filter_by(id=registro_id).update({
                    'procesado': True,
                    'es_anomalia': resultado['es_anomalia'],
                    'tipo_anomalia': resultado.get('tipo_anomalia'),
                    'resultado_validacion': resultado.get('resultado_openai'),
                    'datos_factura_json': resultado.get('datos_factura'),
                    'fecha_procesamiento': datetime.utcnow()
                })
        except Exception as e:
            logger.error(f'Error al actualizar registro {registro_id}: {e}')
            raise
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Dict, Optional, Any
from db.database import db_manager
from models.registro import RegistroWebhook
from utils.logger import get_logger
from utils.helpers import validate_base64

logger = get_logger(__name__)

class OCAttachedData(BaseModel):
    '''Modelo para datos adjuntos de OC (flexible)'''
    oc_subject: Optional[str] = None
    oc_poDate: Optional[str] = None
    adquired_services: Optional[List[str]] = None
    authorized_by: Optional[str] = None
    
    class Config:
        extra = 'allow'  # Permitir campos adicionales

class OrdenCompraInput(BaseModel):
    '''Modelo flexible para órdenes de compra con normalización'''
    # Campos con múltiples nombres posibles
    VendorName: Optional[str] = None
    vendor_name: Optional[str] = None
    proveedor: Optional[str] = None
    
    our_company: Optional[str] = None
    empresa: Optional[str] = None
    receptor: Optional[str] = None
    
    total: Optional[float] = None
    monto: Optional[float] = None
    amount: Optional[float] = None
    
    moneda: Optional[str] = None
    currency: Optional[str] = None
    
    id: Optional[str] = None
    oc_id: Optional[str] = None
    order_id: Optional[str] = None
    
    oc_attached_data: Optional[OCAttachedData] = None
    datos_adicionales: Optional[Dict] = None
    
    # Campos adicionales opcionales
    concepto: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        extra = 'allow'  # Permitir campos adicionales no definidos
    
    @root_validator(pre=True)
    def normalize_fields(cls, values):
        '''Normaliza campos con diferentes nombres a un formato estándar'''
        # Normalizar proveedor
        proveedor = (
            values.get('VendorName') or 
            values.get('vendor_name') or 
            values.get('proveedor') or 
            values.get('Proveedor')
        )
        if proveedor:
            values['proveedor_normalizado'] = proveedor
        
        # Normalizar empresa/receptor
        empresa = (
            values.get('our_company') or 
            values.get('empresa') or 
            values.get('receptor') or
            values.get('our_company')
        )
        if empresa:
            values['empresa_normalizada'] = empresa
        
        # Normalizar monto
        monto = (
            values.get('total') or 
            values.get('monto') or 
            values.get('amount')
        )
        if monto is not None:
            values['monto_normalizado'] = float(monto)
        
        # Normalizar moneda
        moneda = (
            values.get('moneda') or 
            values.get('currency') or 
            'MXN'  # Default
        )
        values['moneda_normalizada'] = moneda.upper()
        
        # Normalizar ID
        oc_id = (
            values.get('id') or 
            values.get('oc_id') or 
            values.get('order_id') or
            f"OC-{hash(str(values))}"  # Generar ID si no existe
        )
        values['id_normalizado'] = oc_id
        
        # Normalizar concepto/descripción
        concepto = (
            values.get('concepto') or
            values.get('description')
        )
        if concepto:
            values['concepto_normalizado'] = concepto
        
        # Procesar datos adjuntos
        datos_adjuntos = values.get('oc_attached_data') or values.get('datos_adicionales')
        if datos_adjuntos and isinstance(datos_adjuntos, dict):
            values['datos_adjuntos_normalizados'] = datos_adjuntos
        
        return values
    
    def to_normalized_dict(self) -> Dict:
        '''Convierte a diccionario con campos normalizados'''
        normalized = {
            'id': getattr(self, 'id_normalizado', 'N/A'),
            'proveedor': getattr(self, 'proveedor_normalizado', 'N/A'),
            'empresa': getattr(self, 'empresa_normalizada', 'N/A'),
            'monto': getattr(self, 'monto_normalizado', 0.0),
            'moneda': getattr(self, 'moneda_normalizada', 'MXN'),
        }
        
        # Agregar concepto si existe
        if hasattr(self, 'concepto_normalizado'):
            normalized['concepto'] = self.concepto_normalizado
        
        # Agregar datos adjuntos si existen
        if hasattr(self, 'datos_adjuntos_normalizados'):
            normalized['datos_adjuntos'] = self.datos_adjuntos_normalizados
            
            # Extraer información útil de datos adjuntos
            datos_adj = self.datos_adjuntos_normalizados
            if isinstance(datos_adj, dict):
                if 'oc_subject' in datos_adj:
                    normalized['concepto'] = datos_adj['oc_subject']
                if 'oc_poDate' in datos_adj:
                    normalized['fecha_orden'] = datos_adj['oc_poDate']
                if 'adquired_services' in datos_adj or 'adquired_serviecs' in datos_adj:
                    servicios = datos_adj.get('adquired_services') or datos_adj.get('adquired_serviecs', [])
                    normalized['servicios'] = servicios
                if 'authorized_by' in datos_adj:
                    normalized['autorizado_por'] = datos_adj['authorized_by']
        
        return normalized

class WebhookPayload(BaseModel):
    '''Modelo validado y normalizado de datos del webhook'''
    ordenes_de_compra: List[Any] = Field(default_factory=list, description='Lista de órdenes de compra')
    factura: str = Field(default='', description='Factura en base64')
    
    @validator('factura')
    def validate_factura_base64(cls, v):
        '''Valida que la factura sea base64 válido si está presente'''
        if v and not validate_base64(v):
            logger.warning('⚠️  Factura con formato base64 inválido detectado')
            # No fallar, solo advertir
        return v
    
    @validator('ordenes_de_compra', pre=True)
    def normalize_ordenes(cls, v):
        '''Normaliza y valida estructura de OCs'''
        if not v:
            return []
        
        normalized_ocs = []
        for idx, oc in enumerate(v):
            try:
                if not isinstance(oc, dict):
                    logger.warning(f'⚠️  OC en índice {idx} no es un objeto JSON válido')
                    continue
                
                # Intentar normalizar con el modelo
                oc_input = OrdenCompraInput(**oc)
                normalized_oc = oc_input.to_normalized_dict()
                normalized_ocs.append(normalized_oc)
                
                logger.debug(f'✓ OC {idx} normalizada: Proveedor={normalized_oc.get("proveedor")}, Monto={normalized_oc.get("monto")}')
                
            except Exception as e:
                logger.warning(f'⚠️  Error al normalizar OC {idx}: {e}. Usando formato original.')
                # Si falla la normalización, usar el original
                normalized_ocs.append(oc)
        
        return normalized_ocs

class WebhookHandler:
    '''Manejador optimizado del webhook FastAPI con normalización de datos'''
    
    def __init__(self):
        self.app = FastAPI(
            title="Webhook Validador de Facturas",
            description="Recibe facturas y órdenes de compra para validación automatizada con normalización flexible de formatos",
            version="2.1.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        self._setup_routes()
        self._setup_middleware()
    
    def _setup_middleware(self):
        '''Configura middleware para logging de requests'''
        
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            logger.debug(f'Request: {request.method} {request.url.path}')
            response = await call_next(request)
            logger.debug(f'Response status: {response.status_code}')
            return response
    
    def _setup_routes(self):
        '''Configura las rutas del webhook'''
        
        @self.app.post("/webhook", tags=["Webhook"], summary="Recibir factura y OCs")
        async def receive_webhook(request: Request):
            '''
            Endpoint principal para recibir datos con normalización automática
            
            Soporta múltiples formatos de campos:
            - VendorName, vendor_name, proveedor → proveedor
            - our_company, empresa, receptor → empresa
            - total, monto, amount → monto
            - moneda, currency → moneda
            
            También repara JSON mal formado (claves sin comillas dobles)
            '''
            try:
                # Obtener body como texto primero
                body = await request.body()
                body_str = body.decode('utf-8')
                
                # Intentar parsear con reparación automática
                from utils.helpers import parse_flexible_json
                
                try:
                    raw_data = parse_flexible_json(body_str)
                except ValueError as e:
                    logger.error(f'❌ JSON inválido: {e}')
                    logger.info(f'Body recibido: {body_str}...')
                    raise HTTPException(
                        status_code=400,
                        detail=f"JSON inválido: {str(e)}. Asegúrate de usar comillas dobles para las claves."
                    )
                
                # Convertir a WebhookPayload (que ya tiene normalización)
                payload = WebhookPayload(**raw_data)
                
                num_ocs = len(payload.ordenes_de_compra)
                tiene_factura = bool(payload.factura)
                
                logger.info('=' * 60)
                logger.info('📨 WEBHOOK RECIBIDO')
                logger.info(f'   📋 Órdenes de compra: {num_ocs}')
                logger.info(f'   📄 Factura: {"✓" if tiene_factura else "✗"}')
                
                # Mostrar resumen de OCs normalizadas
                if num_ocs > 0:
                    logger.info('   📊 Resumen de OCs:')
                    for idx, oc in enumerate(payload.ordenes_de_compra, 1):
                        proveedor = oc.get('proveedor', 'N/A')
                        monto = oc.get('monto', 0)
                        moneda = oc.get('moneda', 'N/A')
                        logger.info(f'      {idx}. {proveedor} - ${monto:,.2f} {moneda}')
                
                logger.info('=' * 60)
                
                registro_id = self._guardar_registro(payload)
                
                logger.info(f'✅ Registro guardado con ID: {registro_id}')
                
                return {
                    "status": "success",
                    "message": "Datos recibidos, normalizados y guardados correctamente",
                    "registro_id": registro_id,
                    "detalles": {
                        "num_ordenes": num_ocs,
                        "tiene_factura": tiene_factura,
                        "formato_normalizado": True
                    }
                }
                
            except HTTPException:
                raise
            except ValueError as e:
                logger.warning(f'⚠️  Datos inválidos: {e}')
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f'❌ Error al procesar webhook: {e}', exc_info=True)
                raise HTTPException(status_code=500, detail="Error interno al procesar datos")
        
        @self.app.post("/webhook/raw", tags=["Webhook"], summary="Recibir datos en cualquier formato")
        async def receive_webhook_raw(request: Request):
            '''
            Endpoint alternativo que acepta JSON en cualquier formato
            y lo normaliza automáticamente, incluyendo JSON mal formado
            con claves sin comillas dobles
            '''
            try:
                # Obtener el body como texto
                body = await request.body()
                body_str = body.decode('utf-8')
                
                logger.info('📨 WEBHOOK RAW recibido')
                logger.info(f'Body original: {body}...')
                
                # Intentar parsear con reparación automática
                from utils.helpers import parse_flexible_json
                
                try:
                    raw_data = parse_flexible_json(body_str)
                    logger.info('✅ JSON parseado exitosamente (posiblemente reparado)')
                except ValueError as e:
                    logger.error(f'❌ No se pudo parsear el JSON: {e}')
                    raise HTTPException(
                        status_code=400, 
                        detail=f"JSON inválido y no se pudo reparar automáticamente: {str(e)}"
                    )
                
                # Normalizar manualmente si es necesario
                normalized_data = self._normalize_raw_data(raw_data)
                
                # Convertir a WebhookPayload
                payload = WebhookPayload(**normalized_data)
                
                # Guardar
                registro_id = self._guardar_registro(payload)
                
                logger.info(f'✅ Registro guardado con ID: {registro_id}')
                
                return {
                    "status": "success",
                    "message": "Datos raw normalizados y guardados correctamente",
                    "registro_id": registro_id,
                    "formato_original": "raw",
                    "normalizado": True,
                    "json_reparado": True
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f'❌ Error al procesar webhook raw: {e}', exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health", tags=["Health"], summary="Verificar salud del servicio")
        async def health_check():
            '''Verifica el estado del servicio'''
            return {
                "status": "healthy",
                "service": "webhook-validator",
                "version": "2.1.0",
                "features": [
                    "normalización automática",
                    "múltiples formatos de campos",
                    "validación flexible"
                ]
            }
        
        @self.app.get("/stats", tags=["Statistics"], summary="Obtener estadísticas")
        async def get_stats():
            '''Obtiene estadísticas de registros'''
            try:
                stats = self._obtener_estadisticas()
                return stats
            except Exception as e:
                logger.error(f'❌ Error al obtener estadísticas: {e}')
                raise HTTPException(status_code=500, detail="Error al obtener estadísticas")
        
        @self.app.get("/formatos", tags=["Documentation"], summary="Ver formatos soportados")
        async def get_formatos_soportados():
            '''Muestra todos los formatos de campos soportados'''
            return {
                "formatos_soportados": {
                    "proveedor": ["VendorName", "vendor_name", "proveedor", "Proveedor"],
                    "empresa": ["our_company", "empresa", "receptor"],
                    "monto": ["total", "monto", "amount"],
                    "moneda": ["moneda", "currency"],
                    "id": ["id", "oc_id", "order_id"],
                    "concepto": ["concepto", "description"],
                    "datos_adicionales": ["oc_attached_data", "datos_adicionales"]
                },
                "ejemplo_formato_flexible": {
                    "factura": "base64...",
                    "ordenes_de_compra": [
                        {
                            "VendorName": "AGA PACKING SOLUTIONS S DE RL DE CV",
                            "our_company": "CORAL-MX",
                            "total": 2475,
                            "moneda": "MXN",
                            "oc_attached_data": {
                                "oc_subject": "BOLSA DE RETIRO / EAT",
                                "oc_poDate": "2023-12-15",
                                "adquired_serviecs": ["BOLSA NATURAL"],
                                "authorized_by": "Javier Gonzalez"
                            }
                        }
                    ]
                },
                "ejemplo_formato_normalizado": {
                    "factura": "base64...",
                    "ordenes_de_compra": [
                        {
                            "id": "OC-001",
                            "proveedor": "AGA PACKING SOLUTIONS S DE RL DE CV",
                            "empresa": "CORAL-MX",
                            "monto": 2475.0,
                            "moneda": "MXN",
                            "concepto": "BOLSA DE RETIRO / EAT",
                            "fecha_orden": "2023-12-15",
                            "servicios": ["BOLSA NATURAL"],
                            "autorizado_por": "Javier Gonzalez"
                        }
                    ]
                }
            }
        
        @self.app.exception_handler(404)
        async def not_found_handler(request: Request, exc):
            return JSONResponse(
                status_code=404,
                content={"detail": "Endpoint no encontrado"}
            )
    
    def _normalize_raw_data(self, raw_data: Dict) -> Dict:
        '''Normaliza datos raw a formato estándar'''
        # Si ya tiene el formato correcto, retornar
        if 'ordenes_de_compra' in raw_data or 'factura' in raw_data:
            return raw_data
        
        # Intentar normalizar otros formatos comunes
        normalized = {
            'ordenes_de_compra': [],
            'factura': ''
        }
        
        # Buscar factura en diferentes nombres
        for key in ['factura', 'invoice', 'pdf', 'documento']:
            if key in raw_data:
                normalized['factura'] = raw_data[key]
                break
        
        # Buscar órdenes de compra
        for key in ['ordenes_de_compra', 'ordenes', 'ocs', 'purchase_orders', 'orders']:
            if key in raw_data and isinstance(raw_data[key], list):
                normalized['ordenes_de_compra'] = raw_data[key]
                break
        
        return normalized
    
    def _guardar_registro(self, payload: WebhookPayload) -> int:
        '''Guarda el registro en la base de datos con datos normalizados'''
        with db_manager.get_session() as session:
            nuevo_registro = RegistroWebhook(
                ordenes_de_compra=payload.ordenes_de_compra if payload.ordenes_de_compra else None,
                factura_base64=payload.factura if payload.factura else None,
                tiene_oc=len(payload.ordenes_de_compra) > 0,
                tiene_factura=bool(payload.factura)
            )
            session.add(nuevo_registro)
            session.flush()
            return nuevo_registro.id
    
    def _obtener_estadisticas(self) -> Dict:
        '''Obtiene estadísticas de la base de datos'''
        with db_manager.get_session() as session:
            total = session.query(RegistroWebhook).count()
            procesados = session.query(RegistroWebhook).filter_by(procesado=True).count()
            pendientes = total - procesados
            anomalias = session.query(RegistroWebhook).filter_by(es_anomalia=True).count()
            
            return {
                "total_registros": total,
                "procesados": procesados,
                "pendientes": pendientes,
                "anomalias": anomalias,
                "porcentaje_anomalias": f"{(anomalias/total*100):.1f}%" if total > 0 else "0%"
            }

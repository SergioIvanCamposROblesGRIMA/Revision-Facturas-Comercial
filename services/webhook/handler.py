from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from db.database import db_manager
from models.registro import RegistroWebhook
from utils.logger import get_logger
from utils.helpers import parse_flexible_json
import base64
import json
import re
import asyncio

logger = get_logger(__name__)


class OCAttachedData(BaseModel):
    oc_subject: Optional[str] = None
    oc_poDate: Optional[str] = None
    adquired_services: Optional[List[str]] = None
    adquired_serviecs: Optional[List[str]] = None
    authorized_by: Optional[str] = None
    class Config: extra = 'allow'

class OrdenCompraInput(BaseModel):
    VendorName: Optional[str] = None
    vendor_name: Optional[str] = None
    proveedor: Optional[str] = None
    our_company: Optional[str] = None
    empresa: Optional[str] = None
    receptor: Optional[str] = None
    total: Optional[Union[float, str]] = None
    monto: Optional[Union[float, str]] = None
    amount: Optional[Union[float, str]] = None
    moneda: Optional[str] = None
    currency: Optional[str] = None
    id: Optional[str] = None
    oc_id: Optional[str] = None
    order_id: Optional[str] = None
    oc_attached_data: Optional[Union[OCAttachedData, Dict]] = None
    datos_adicionales: Optional[Dict] = None
    concepto: Optional[str] = None
    description: Optional[str] = None
    
    class Config: extra = 'allow'
    
    def to_normalized_dict(self) -> Dict:
        prov = self.proveedor or self.VendorName or self.vendor_name or "N/A"
        emp = self.empresa or self.our_company or self.receptor or "N/A"
        
        raw_monto = self.monto or self.total or self.amount or 0.0
        try:
            if isinstance(raw_monto, str):
                raw_monto = raw_monto.replace(',', '').replace('$', '').strip()
            mnt = float(raw_monto)
        except:
            mnt = 0.0
            
        mon = (self.moneda or self.currency or "MXN").upper()
        oid = self.id or self.oc_id or self.order_id or "N/A"
        
        normalized = {
            'id': oid,
            'proveedor': prov,
            'empresa': emp,
            'monto': mnt,
            'moneda': mon
        }
        
        adj = self.oc_attached_data or self.datos_adicionales
        if isinstance(adj, dict):
            normalized['datos_adjuntos'] = adj
            if 'oc_subject' in adj: normalized['concepto'] = adj['oc_subject']
            if 'oc_poDate' in adj: normalized['fecha_orden'] = adj['oc_poDate']
            servicios = adj.get('adquired_services') or adj.get('adquired_serviecs')
            if servicios: normalized['servicios'] = servicios
            
        return normalized



class WebhookHandler:
    
    def __init__(self):
        self.app = FastAPI(
            title="Webhook Validador (Multipart + Robust JSON)",
            version="3.3.0"
        )
        self._setup_routes()
    
    def _clean_json_string(self, json_str: str) -> str:
        '''Limpia caracteres de control inválidos para JSON'''
        # 1. Reemplazar saltos de línea literales por espacio o escape
        json_str = json_str.replace('\n', ' ').replace('\r', '')
        # 2. Reemplazar tabulaciones
        json_str = json_str.replace('\t', ' ')
        # 3. Eliminar otros caracteres de control no imprimibles (ASCII 0-31 excepto permitidos)
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
        return json_str

    def _setup_routes(self):
        
        @self.app.post("/webhook")
        async def receive_webhook(
            factura: Optional[UploadFile] = File(None, description="Archivo PDF"),
            ordenes_de_compra: Optional[str] = Form(None, description="String JSON")
        ):
            try:
                filename = factura.filename if factura else "None"
                logger.info("="*50)
                logger.info(f"📥 WEBHOOK RECIBIDO - Archivo: {filename}")
                
                # --- 1. PROCESAMIENTO FACTURA ---
                factura_b64 = None
                if factura:
                    file_content = await factura.read()
                    if len(file_content) > 0:
                        factura_b64 = base64.b64encode(file_content).decode('utf-8')
                        logger.info(f"✅ Factura procesada ({len(factura_b64)} chars)")
                    else:
                        logger.warning("⚠️ Archivo vacío")

                # --- 2. PROCESAMIENTO OCS (FASES DE INTENTO) ---
                ocs_finales = []
                
                if ordenes_de_compra:
                    raw_list = None
                    
                    # FASE 1: Parseo Directo (Ideal)
                    try:
                        raw_list = parse_flexible_json(ordenes_de_compra)
                    except Exception:
                        pass # Falló, vamos a Fase 2
                    
                    # FASE 2: Limpieza de Escapes (Para \" en pulgadas)
                    if raw_list is None:
                        try:
                            clean_str = ordenes_de_compra.replace('\\"', '"')
                            raw_list = parse_flexible_json(clean_str)
                            logger.warning("⚠️ Parseo exitoso tras limpiar escapes")
                        except Exception:
                            pass # Falló, vamos a Fase 3
                            
                    # FASE 3: Limpieza de Caracteres de Control (Para saltos de línea \n)
                    if raw_list is None:
                        try:
                            # Limpiar caracteres invisibles y escapes agresivos
                            super_clean = self._clean_json_string(ordenes_de_compra)
                            # Reintentar manejo de comillas sobre la cadena limpia
                            super_clean = super_clean.replace('\\"', '"')
                            
                            raw_list = parse_flexible_json(super_clean)
                            logger.warning("⚠️ Parseo exitoso tras limpieza profunda de caracteres de control")
                        except Exception as e:
                             logger.error(f"❌ Error fatal parseando OCs (Fase 3 fallida): {e}")
                             # Loguear primeros 200 chars para debug
                             logger.debug(f"String problemático inicio: {ordenes_de_compra[:200]}")

                    # PROCESAMIENTO DE LA LISTA OBTENIDA
                    if raw_list:
                        if isinstance(raw_list, dict):
                            raw_list = [raw_list]
                        
                        for item in raw_list:
                            if isinstance(item, dict):
                                try:
                                    oc_normalizada = OrdenCompraInput(**item).to_normalized_dict()
                                    ocs_finales.append(oc_normalizada)
                                except Exception as norm_error:
                                    logger.warning(f"Error normalizando item: {norm_error}")
                                    ocs_finales.append(item)
                            else:
                                ocs_finales.append(item)
                                
                        logger.info(f"✅ OCs procesadas: {len(ocs_finales)} órdenes")
                        if len(ocs_finales) > 0:
                            ej = ocs_finales[0]
                            logger.info(f"   🔍 Check: Prov='{ej.get('proveedor')}' | Monto=${ej.get('monto')}")

                # --- 3. VALIDACIÓN VACÍO ---
                if not factura_b64 and not ocs_finales:
                    logger.warning("⚠️ Ignorado: Sin datos válidos")
                    return JSONResponse(content={"status": "ignored"})

                # --- 4. GUARDAR ---
                registro_id = await asyncio.to_thread(self._guardar_registro_sync,factura_b64,ocs_finales)
                logger.info(f"💾 Guardado ID: {registro_id}")
                
                return {"status": "success", "registro_id": registro_id}

            except Exception as e:
                logger.error(f"❌ Error crítico: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/health")
        async def health(): return {"status": "active"}


    def _guardar_registro_sync(self, factura_b64: Optional[str], ocs: List[Any]) -> int:
        with db_manager.get_session() as session:
            nuevo = RegistroWebhook(
                ordenes_de_compra=ocs if ocs else None,
                factura_base64=factura_b64,
                tiene_oc=len(ocs) > 0 if ocs else False,
                tiene_factura=bool(factura_b64)
            )
            session.add(nuevo)
            session.flush()
            return nuevo.id
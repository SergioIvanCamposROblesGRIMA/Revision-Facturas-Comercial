import json
import time
import io
from typing import Dict, Optional, Tuple, Any
from openai import OpenAI, APIError, RateLimitError
from config.settings import settings
from services.openai.prompts import OpenAIPrompts
from utils.logger import get_logger
from utils.helpers import validate_base64
import base64

logger = get_logger(__name__)

class OpenAIService:
    '''
    Servicio optimizado usando Assistants API v2 (File Search) con GPT-4o-mini.
    Ciclo: Subir PDF -> Crear Vector Store Temp -> Consultar -> Borrar
    '''
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini" 
        self.prompts = OpenAIPrompts()
        self.sleep_interval = 1.5
        self.timeout = 90
    
    def _upload_file(self, base64_string: str) -> Any:
        '''Decodifica base64 y sube el archivo a OpenAI'''
        try:
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            file_data = base64.b64decode(base64_string)
            f = io.BytesIO(file_data)
            f.name = f"factura_{int(time.time())}.pdf"
            
            file_obj = self.client.files.create(
                file=f,
                purpose="assistants"
            )
            logger.info(f"☁️ Archivo subido a OpenAI: {file_obj.id}")
            return file_obj
        except Exception as e:
            logger.error(f"Error subiendo archivo a OpenAI: {e}")
            raise

    def _delete_file(self, file_id: str):
        '''Elimina el archivo de OpenAI para no saturar el storage'''
        try:
            self.client.files.delete(file_id)
            logger.info(f"🗑️ Archivo eliminado de OpenAI: {file_id}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el archivo {file_id}: {e}")

    def extraer_datos_factura(self, factura_base64: str) -> Tuple[Optional[Dict], Optional[str]]:
        '''
        Crea un Assistant temporal, sube el archivo, extrae datos y limpia.
        '''
        file_obj = None
        assistant = None
        thread = None
        response_text = ""
        
        try:
            if not validate_base64(factura_base64):
                logger.error('Base64 de factura inválido')
                return None, None

            # 1. SUBIR ARCHIVO
            file_obj = self._upload_file(factura_base64)

            # 2. CREAR ASISTENTE
            assistant = self.client.beta.assistants.create(
                name="Analista de Facturas",
                instructions="Eres un experto contable. Tu única función es extraer datos de facturas. DEBES responder siempre en formato JSON válido.",
                model=self.model,
                tools=[{"type": "file_search"}],
                response_format={"type": "json_object"} 
            )

            # 3. CREAR THREAD
            thread = self.client.beta.threads.create(
                messages=[
                    {
                        "role": "user",
                        "content": self.prompts.get_extraction_prompt(),
                        "attachments": [
                            {
                                "file_id": file_obj.id,
                                "tools": [{"type": "file_search"}]
                            }
                        ]
                    }
                ]
            )
            
            # 4. EJECUTAR RUN
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id
            )
            
            # Loop de espera (Polling)
            start_time = time.time()
            while run.status not in ["completed", "failed", "cancelled"]:
                if time.time() - start_time > self.timeout:
                    raise TimeoutError("Tiempo de espera agotado en OpenAI")
                
                time.sleep(self.sleep_interval)
                run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            
            if run.status != "completed":
                logger.error(f"❌ Run falló con estado: {run.status}")
                if run.last_error:
                    logger.error(f"Detalle error: {run.last_error}")
                return None, None

            # 5. OBTENER MENSAJES
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # La respuesta más reciente es la primera
            response_text = messages.data[0].content[0].text.value
            
            # 6. LIMPIAR JSON
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            datos_factura = json.loads(clean_json)
            
            logger.info(f"✅ Datos extraídos exitosamente vía Assistants API")
            return datos_factura, None

        except json.JSONDecodeError:
            logger.error("❌ OpenAI no devolvió un JSON válido")
            logger.debug(f"Texto recibido: {response_text}")
            return None, None
        except Exception as e:
            logger.error(f"❌ Error en proceso de extracción (Assistant): {e}", exc_info=True)
            return None, None
        
        finally:
            # 7. LIMPIEZA OBLIGATORIA
            if file_obj:
                self._delete_file(file_obj.id)
            
            if assistant:
                try:
                    self.client.beta.assistants.delete(assistant.id)
                except: pass

    def comparar_factura_oc(self, datos_factura: Dict, ordenes_de_compra: list) -> str:
        '''
        Comparación usando Chat Completions.
        '''
        try:
            logger.info(f'🔍 Comparando factura con {len(ordenes_de_compra)} órdenes de compra...')
            
            prompt = self.prompts.get_comparison_prompt(datos_factura, ordenes_de_compra)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un auditor financiero experto."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            resultado = response.choices[0].message.content.strip()
            return resultado
            
        except Exception as e:
            logger.error(f'❌ Error al comparar factura con OCs: {e}')
            return f'Error en comparación: {str(e)}'
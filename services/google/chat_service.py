import requests
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class GoogleChatService:
    """
    Servicio de notificaciones basado en requests directo.
    """
    def __init__(self):
        self.logger = logger
        self.webhook_url = settings.GOOGLE_CHAT_WEBHOOK_URL

    def send_advice(self, link: str, resumen: str = ""): 
        """
        Envía el mensaje al webhook de Google Chat.
        """
        try:
            # Construimos el mensaje
            texto_mensaje = (
                f"📄✨ ¡Excelente día!\n"
                f"El reporte de validación de \"*Facturas vs Órdenes de Compra*\" 🧾\n"
                f" ya está listo.\n\n"
                f"{resumen}\n\n"
                f"Adjunto podrás encontrar el link:\n"
                f"🔗Link: {link}"
            )

            payload = {
                "text": texto_mensaje
            }
            
            response = requests.post(self.webhook_url, json=payload)
            
            if response.status_code == 200:
                self.logger.info("Message sent successfully to Google Chat")
            else:
                self.logger.critical(f"Error sending message: {response.status_code} - {response.text}")
                
        except Exception as e:
            self.logger.critical(f"Exception in send_advice: {e}")
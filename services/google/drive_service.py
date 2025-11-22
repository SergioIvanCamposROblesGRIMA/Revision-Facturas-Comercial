from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class GoogleDriveService:

    def __init__(self):
        self.logger = logger
        self.folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        self.path_gsa = settings.GOOGLE_CREDENTIALS_PATH
        self.scopes = ['https://www.googleapis.com/auth/drive']

    def upload_to_drive(self, output_file: str, specific_folder_id: str = None):
        """
        Sube archivo a Drive.
        Args:
            output_file: Ruta local del archivo
            specific_folder_id: ID de carpeta opcional (si no, usa la de reportes)
        """
        try:
            # Decidir a qué carpeta va
            target_folder = specific_folder_id if specific_folder_id else self.folder_id
            filename = output_file.split("/")[-1]
            
            # self.logger.info(f"☁️ Subiendo a Drive: {filename}")

            creds = Credentials.from_service_account_file(
                self.path_gsa, 
                scopes=self.scopes
            )
            drive_service = build("drive", "v3", credentials=creds)

            file_metadata = {
                "name": filename,
                "parents": [target_folder]
            }
            
            # Detectar mimetype correcto
            if output_file.lower().endswith('.pdf'):
                mimetype = 'application/pdf'
            else:
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            media = MediaFileUpload(output_file, mimetype=mimetype)

            file = drive_service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields="id", 
                supportsAllDrives=True
            ).execute()
            
            file_id = file.get("id")
            
            # Construir link de vista previa
            drive_link = f"https://drive.google.com/file/d/{file_id}/view"
            
            self.logger.info(f"✅ Subida exitosa a Drive ({filename}). ID: {file_id}")
            
            return drive_link

        except Exception as e:
            self.logger.critical(f"Error uploading to Drive: {e}")
            raise
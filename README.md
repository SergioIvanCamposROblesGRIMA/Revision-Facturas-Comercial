# Revision-Facturas-Comercial


# 🧾 Sistema de Validación de Facturas y Órdenes de Compra v2.0

Sistema empresarial automatizado para recibir, validar y reportar facturas contra órdenes de compra utilizando **OpenAI GPT-4**, **Google Drive** y **Google Chat**.

## 🎯 Características Principales

### ✨ Funcionalidades Core
- 🌐 **Webhook REST API** profesional con FastAPI
- 🤖 **Integración Inteligente con OpenAI** (2 peticiones optimizadas):
  1. **Extracción OCR** de datos estructurados de facturas PDF
  2. **Comparación automática** contra órdenes de compra con análisis de discrepancias
- 🗄️ **Base de datos SQLite** con SQLAlchemy 2.0 y optimizaciones de índices
- ⏰ **Validación programada** configurable (por defecto 23:00 hrs)
- ⚠️ **Detección automática de anomalías** con 5 tipos clasificados
- 📊 **Reportes Excel profesionales** con formato y colores condicionales
- ☁️ **Subida automática a Google Drive** con permisos públicos
- 💬 **Notificaciones a Google Chat** con formato rico y estadísticas

### 🚀 Mejoras Técnicas v2.0
- ✅ **Manejo de errores robusto** con retry logic
- ✅ **Logging avanzado** con rotación de archivos (10MB, 5 backups)
- ✅ **Validación de datos** con Pydantic
- ✅ **Pool de conexiones** optimizado para SQLAlchemy
- ✅ **Thread-safety** con scoped_session
- ✅ **Shutdown graceful** con signal handlers
- ✅ **Health checks** y endpoints de estadísticas
- ✅ **Documentación automática** con OpenAPI/Swagger

## 📋 Tabla de Contenidos

- [Requisitos](#requisitos)
- [Instalación Rápida](#instalación-rápida)
- [Configuración](#configuración)
- [Uso](#uso)
- [API Documentation](#api-documentation)
- [Arquitectura](#arquitectura)
- [Troubleshooting](#troubleshooting)

## 💻 Requisitos

- **Python** 3.9 o superior
- **OpenAI API Key** con acceso a GPT-4 Vision
- **Google Cloud Project** con APIs habilitadas:
  - Google Drive API
  - Google Chat API
- **Cuenta de servicio de Google** con credenciales JSON

## 🚀 Instalación Rápida

### Opción 1: Script Automatizado

```bash
# Descargar y ejecutar setup
chmod +x setup_project.sh
bash setup_project.sh

cd factura-validator

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### Opción 2: Manual

```bash
# Clonar o crear estructura
mkdir factura-validator && cd factura-validator

# Entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install fastapi uvicorn sqlalchemy openai google-auth \
  google-api-python-client pandas openpyxl schedule \
  python-dotenv requests pydantic-settings
```

## ⚙️ Configuración

### 1. Variables de Entorno (.env)

Copia `.env.example` a `.env` y configura:

```env
# OpenAI
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o

# Google Services
GOOGLE_CREDENTIALS_PATH=config/google_credentials.json
GOOGLE_DRIVE_FOLDER_ID=1ABC123XYZ
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/AAAA/messages?key=XXX

# Database
DATABASE_URL=sqlite:///db/facturas_oc.db

# Validation
VALIDATION_HOUR=23:00

# Webhook
WEBHOOK_PORT=8000
WEBHOOK_HOST=0.0.0.0

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### 2. Credenciales de Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Crea/selecciona un proyecto
3. Habilita APIs:
   - Google Drive API
   - Google Chat API  
4. Crea una **Cuenta de Servicio**:
   - IAM & Admin → Service Accounts → Create Service Account
   - Roles: "Drive File" + "Chat Bot"
5. Genera clave JSON:
   - Actions → Manage Keys → Add Key → JSON
6. Guarda como `config/google_credentials.json`

### 3. Google Chat Webhook

1. Abre Google Chat
2. Ve a un espacio (o crea uno)
3. Click en nombre del espacio → **Apps & integrations**
4. **Manage webhooks** → **Add webhook**
5. Copia la URL generada

## 🎯 Uso

### Iniciar el Sistema

```bash
python main.py
```

Esto iniciará:
- ✅ Servidor webhook en `http://localhost:8000`
- ✅ Scheduler para validación diaria
- ✅ Documentación en `http://localhost:8000/docs`

### Enviar Datos al Webhook

#### Ejemplo con curl:

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "ordenes_de_compra": [
      {
        "id": "OC-2024-001",
        "proveedor": "Proveedor XYZ SA de CV",
        "monto": 15000.00,
        "moneda": "MXN",
        "concepto": "Servicios de consultoría"
      },
      {
        "id": "OC-2024-002",
        "proveedor": "Proveedor XYZ SA de CV",
        "monto": 5000.00,
        "moneda": "MXN",
        "concepto": "Licencias de software"
      }
    ],
    "factura": "JVBERi0xLjQKJeLjz9MKNCAwIG9iago8PC9MZW5ndGggMzUvRmlsdGVyL0ZsYXRlRGVjb2RlPj4Kc3RyZWFtC..."
  }'
```

#### Ejemplo con Python:

```python
import requests
import base64

# Leer PDF
with open('factura.pdf', 'rb') as f:
    factura_base64 = base64.b64encode(f.read()).decode('utf-8')

# Preparar datos
payload = {
    "ordenes_de_compra": [
        {
            "id": "OC-001",
            "proveedor": "Mi Proveedor",
            "monto": 10000.00,
            "moneda": "MXN"
        }
    ],
    "factura": factura_base64
}

# Enviar
response = requests.post(
    'http://localhost:8000/webhook',
    json=payload
)

print(response.json())
```

### Ejecutar Validación Manual

```python
from main import OrquestadorPrincipal

orquestador = OrquestadorPrincipal()
orquestador.inicializar_sistema()
orquestador.ejecutar_validacion()
```

## 📚 API Documentation

### Endpoints Disponibles

#### POST `/webhook`
Recibe y guarda facturas con sus OCs

**Request:**
```json
{
  "ordenes_de_compra": [
    {
      "id": "string",
      "proveedor": "string",
      "monto": 0.00,
      "moneda": "string"
    }
  ],
  "factura": "base64_string"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Datos recibidos y guardados correctamente",
  "registro_id": 1,
  "detalles": {
    "num_ordenes": 2,
    "tiene_factura": true
  }
}
```

#### GET `/health`
Health check del servicio

**Response:**
```json
{
  "status": "healthy",
  "service": "webhook-validator",
  "version": "2.0.0"
}
```

#### GET `/stats`
Estadísticas de registros

**Response:**
```json
{
  "total_registros": 150,
  "procesados": 145,
  "pendientes": 5,
  "anomalias": 12,
  "porcentaje_anomalias": "8.0%"
}
```

## 🏗️ Arquitectura

```
┌─────────────┐
│   Webhook   │ ──▶ Valida y guarda en SQLite
└─────────────┘
       │
       ▼
┌─────────────┐
│  Scheduler  │ ──▶ Ejecuta validación a las 23:00
└─────────────┘
       │
       ▼
┌─────────────┐      ┌──────────────┐
│  Validator  │ ───▶ │ OpenAI API   │
│             │      │ 1. Extracción│
│             │      │ 2. Comparación│
└─────────────┘      └──────────────┘
       │
       ▼
┌─────────────┐
│   Report    │ ──▶ Genera Excel con formato
└─────────────┘
       │
       ▼
┌─────────────┐      ┌──────────────┐
│   Google    │ ───▶ │ Drive + Chat │
└─────────────┘      └──────────────┘
```

## 🔧 Troubleshooting

### Error: "OpenAI API Key inválida"
```bash
# Verifica tu API key
echo $OPENAI_API_KEY

# O en Python
python -c "from config.settings import settings; print(settings.OPENAI_API_KEY[:10])"
```

### Error: "Google credentials not found"
```bash
# Verifica que el archivo exista
ls -la config/google_credentials.json

# Verifica permisos
chmod 600 config/google_credentials.json
```

### Base de datos bloqueada
```bash
# Detén el servicio
pkill -f main.py

# Elimina el archivo de lock
rm db/facturas_oc.db-journal

# Reinicia
python main.py
```

### Ver logs en tiempo real
```bash
tail -f logs/app.log
```

## 📊 Ejemplo de Reporte

El sistema genera reportes Excel con 2 hojas:

### Hoja 1: Validación
| Estado | ID | Fecha | OC | Cant OCs | Factura | Proveedor | Total | Moneda | Resultado |
|--------|----|----|-----|----------|---------|-----------|-------|--------|-----------|
| ✅ OK | 1 | 2024-01-15 | Sí | 2 | Sí | Proveedor A | 15000 | MXN | OK |
| ⚠️ ANOMALÍA | 2 | 2024-01-15 | Sí | 1 | No | N/A | N/A | N/A | Sin factura |

### Hoja 2: Resumen
- Total de Registros: 150
- Registros Correctos: 138 (92%)
- Total de Anomalías: 12 (8%)

## 📝 Licencia

Este proyecto es privado y confidencial.

## 🤝 Soporte

Para problemas:
1. Revisa logs: `logs/app.log`
2. Verifica configuración: `.env`
3. Consulta API docs: `/docs`

---

**Versión:** 2.0.0  
**Última actualización:** 2024"""

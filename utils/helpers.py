import base64
import re
import json
from datetime import datetime
from typing import Optional, Any

def decode_base64_pdf(base64_string: str) -> Optional[bytes]:
    '''Decodifica un string base64 a bytes'''
    try:
        # Limpiar posibles espacios o saltos de línea
        clean_string = base64_string.strip().replace('\\n', '').replace(' ', '')
        return base64.b64decode(clean_string)
    except Exception:
        return None

def format_datetime(dt: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    '''Formatea datetime a string legible'''
    return dt.strftime(format_str)

def generate_report_filename() -> str:
    '''Genera nombre único para reporte'''
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'reporte_validacion_{timestamp}.xlsx'

def validate_base64(base64_string: str) -> bool:
    '''Valida si un string es base64 válido'''
    try:
        if not base64_string:
            return False
        # Intentar decodificar
        base64.b64decode(base64_string.strip())
        return True
    except Exception:
        return False

def truncate_text(text: str, max_length: int = 100) -> str:
    '''Trunca texto largo para logs'''
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'

def fix_malformed_json(json_string: str) -> str:
    '''
    Repara JSON mal formado con claves sin comillas dobles
    
    Ejemplos que repara:
    - {name: "value"} -> {"name": "value"}
    - {name : "value"} -> {"name": "value"}
    - {'name': 'value'} -> {"name": "value"}
    - {name: 123} -> {"name": 123}
    '''
    try:
        # Ya es JSON válido, retornar sin cambios
        json.loads(json_string)
        return json_string
    except json.JSONDecodeError:
        pass
    
    # 1. Reemplazar comillas simples por dobles en valores string
    # Pero cuidado con comillas simples dentro de strings
    fixed = json_string
    
    # 2. Encontrar claves sin comillas y agregarlas
    # Patrón: palabra seguida de : (con o sin espacios)
    # Que no esté ya entre comillas
    pattern = r'(?<!")(\b[a-zA-Z_][a-zA-Z0-9_]*\b)(?!")\s*:'
    
    def add_quotes(match):
        key = match.group(1)
        return f'"{key}":'
    
    fixed = re.sub(pattern, add_quotes, fixed)
    
    # 3. Reemplazar comillas simples por dobles en valores
    # Esto es más complejo, hay que tener cuidado con comillas dentro de strings
    fixed = fixed.replace("'", '"')
    
    return fixed

def parse_flexible_json(json_string: str) -> Any:
    '''
    Parsea JSON de forma flexible, intentando reparar errores comunes
    
    Args:
        json_string: String JSON que puede estar mal formado
        
    Returns:
        Objeto Python parseado (dict, list, etc.)
        
    Raises:
        ValueError: Si no se puede parsear incluso después de intentar reparar
    '''
    # Limpiar espacios en blanco al inicio/final
    json_string = json_string.strip()
    
    # Intentar parsear directamente primero
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        pass
    
    # Intentar reparar y parsear
    try:
        fixed_json = fix_malformed_json(json_string)
        return json.loads(fixed_json)
    except json.JSONDecodeError as e:
        # Si aún falla, intentar con ast.literal_eval (más permisivo)
        try:
            import ast
            # Reemplazar true/false/null por True/False/None
            python_like = json_string.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            return ast.literal_eval(python_like)
        except:
            raise ValueError(f"No se pudo parsear el JSON: {e}")

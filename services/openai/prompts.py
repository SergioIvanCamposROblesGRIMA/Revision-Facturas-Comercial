from typing import Dict, List
import json
import itertools

class OpenAIPrompts:
    '''Prompts optimizados con estrategias de Prompt Engineering avanzadas'''
    
    @staticmethod
    def get_extraction_prompt() -> str:
        '''
        Prompt para extracción (Se mantiene igual que la versión mejorada anterior)
        '''
        return '''Eres un analista contable experto especializado en auditoría de facturas.
Tu objetivo es analizar el documento PDF adjunto y extraer información crítica con precisión.

### GUÍA DE RAZONAMIENTO (CHAIN OF THOUGHT):

1. **PROVEEDOR (Emisor):**
   - Busca "Emisor", "Vendedor". Extrae el nombre legal completo del vendedor de producto o servicio.
2. **RECEPTOR (Cliente):**
   - Busca "Receptor", "Cliente", "Facturar a".
   - El receptor suele llamarse Eat Burgers, Cafe Cachanilla, Corporación de Alimentos, Corporacion De Alimentos De Mexicali, CORPORACION DE ALIMENTOS DE MEXICALI LITTLE CAESARS, CORPORACION DE ALIMENTOS DE MEXICALI S.A. DE C.V., INMOBILIARIA KARMAR, Karmar, Karmar de Baja Califonria, Little Caesars, IKA y cualquier convinación de estas, etc. (prueba buscando estos nombres comunes en la factura).
   - Si no es ninguna de las anteriores buscas el campo receptor.
3. **GRAN TOTAL (Monto Final):**
   - Es la cantidad FINAL a pagar (con impuestos). Busca al final de la columna de totales.
   - NO confundir con Subtotal.
   - Formato: Solo el número (ej. 1500.50).
4. **MONEDA:**
   - Busca códigos ISO (MXN, USD). Si no hay, infiere por el contexto (dirección México = MXN).
5. **FECHA:**
   - Fecha de emisión (YYYY-MM-DD).
6. **FOLIO:**
   - Identificador interno de la factura.

### 📦 FORMATO DE SALIDA (JSON):

Responde ÚNICAMENTE con este JSON. Si no encuentras algo, usa null.

{
    "proveedor": "string o null",
    "gran_total": numero o 0.0,
    "moneda": "string o null",
    "receptor": "string o null",
    "fecha": "YYYY-MM-DD o null",
    "folio": "string o null"
}
'''

    @staticmethod
    def get_comparison_prompt(datos_factura: Dict, ordenes_de_compra: List[Dict]) -> str:
        '''
        Prompt AVANZADO para comparación inteligente (Match Individual o Grupal).
        '''
        
        # 1. Preparar lista legible de OCs para el prompt
        lista_ocs_texto = ""
        suma_total_todas_ocs = 0.0
        
        for idx, oc in enumerate(ordenes_de_compra, 1):
            try:
                monto = float(oc.get('monto', 0))
            except:
                monto = 0.0
            
            suma_total_todas_ocs += monto
            
            oc_id = oc.get('id', 'Sin ID')
            prov = oc.get('proveedor', 'N/A')
            mon = oc.get('moneda', 'MXN')
            desc = oc.get('concepto', '')[:50] # Recortar descripción si es muy larga
            
            lista_ocs_texto += f"   [OC #{idx}] ID: {oc_id} | Prov: {prov} | Monto: ${monto:,.2f} {mon} | Desc: {desc}\n"
            
        num_ocs = len(ordenes_de_compra)
        total_factura = datos_factura.get('gran_total', 0)
        moneda_factura = datos_factura.get('moneda', 'N/A')

        # Construir el prompt con lógica de "Búsqueda de Match"
        return f'''Eres un Auditor Financiero Inteligente. Tienes una Factura y una lista de "Candidatos" (Órdenes de Compra).
Tu misión es descubrir CUAL(ES) orden(es) de compra justifican esta factura.

═══════════════════════════════════════════════════════════
📄 FACTURA A VALIDAR:
═══════════════════════════════════════════════════════════
• Proveedor: {datos_factura.get('proveedor')}
• Total Factura: ${total_factura:,.2f}
• Moneda: {moneda_factura}

═══════════════════════════════════════════════════════════
📋 LISTA DE OCs DISPONIBLES ({num_ocs}):
═══════════════════════════════════════════════════════════
{lista_ocs_texto}

═══════════════════════════════════════════════════════════
🧠 LÓGICA DE EMPAREJAMIENTO (MATCHING LOGIC):
═══════════════════════════════════════════════════════════

Debes verificar los siguientes escenarios en orden:

1. **MATCH INDIVIDUAL (1 a 1):**
   ¿Existe alguna OC individual cuyo monto sea igual al de la factura (tolerancia +/- $1.00)?
   *Si sí*: La factura es válida y corresponde a esa OC específica.

2. **MATCH TOTAL (1 a Todas):**
   ¿La suma de TODAS las OCs coincide con el monto de la factura?
   *Si sí*: La factura agrupa todas las órdenes.

3. **MATCH PARCIAL (1 a Varias):**
   (Solo si hay 3 o más OCs) ¿Existe alguna combinación de OCs que sumadas den el total de la factura?

═══════════════════════════════════════════════════════════
🔍 REGLAS DE VALIDACIÓN ADICIONALES:
═══════════════════════════════════════════════════════════
- **Proveedor:** El nombre del proveedor en la(s) OC(s) emparejada(s) debe coincidir razonablemente con el de la factura.
- **Moneda:** Las monedas deben coincidir.

═══════════════════════════════════════════════════════════
📝 FORMATO DE RESPUESTA:
═══════════════════════════════════════════════════════════

Si encuentras un emparejamiento válido (Individual o Grupal), responde:
"OK - [Explicación Breve]"
Ejemplo: "OK - Corresponde a la OC #2 (ID: 12345) por monto exacto."
Ejemplo: "OK - Corresponde a la suma de todas las OCs."

Si NO encuentras ninguna combinación que cuadre, o el proveedor es incorrecto:
"DISCREPANCIA - [Detalle]"
Ejemplo: "DISCREPANCIA - El monto de la factura ($15,000) no coincide con ninguna OC individual ni con la suma total ($20,000)."
Ejemplo: "DISCREPANCIA - El monto coincide con OC #1, pero el proveedor es diferente."

Analiza los números cuidadosamente antes de responder.
'''
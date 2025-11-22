from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional, Dict, List

Base = declarative_base()

class RegistroWebhook(Base):
    '''Modelo para registros del webhook con índices optimizados'''
    __tablename__ = 'registros_webhook'
    
    # Columnas
    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_recepcion = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ordenes_de_compra = Column(JSON, nullable=True)
    factura_base64 = Column(Text, nullable=True)
    procesado = Column(Boolean, default=False, nullable=False, index=True)
    tiene_oc = Column(Boolean, nullable=True, index=True)
    tiene_factura = Column(Boolean, nullable=True, index=True)
    resultado_validacion = Column(Text, nullable=True)
    es_anomalia = Column(Boolean, default=False, nullable=False, index=True)
    tipo_anomalia = Column(String(100), nullable=True)
    datos_factura_json = Column(JSON, nullable=True)
    fecha_procesamiento = Column(DateTime, nullable=True)
    
    # Índices compuestos para queries comunes
    __table_args__ = (
        Index('idx_procesado_anomalia', 'procesado', 'es_anomalia'),
        Index('idx_fecha_procesado', 'fecha_recepcion', 'procesado'),
    )
    
    def __repr__(self):
        return f'<RegistroWebhook(id={self.id}, fecha={self.fecha_recepcion}, procesado={self.procesado})>'
    
    def to_dict(self) -> Dict:
        '''Convierte el registro a diccionario'''
        return {
            'id': self.id,
            'fecha_recepcion': self.fecha_recepcion,
            'tiene_oc': self.tiene_oc,
            'tiene_factura': self.tiene_factura,
            'procesado': self.procesado,
            'es_anomalia': self.es_anomalia,
            'tipo_anomalia': self.tipo_anomalia,
            'resultado_validacion': self.resultado_validacion,
            'datos_factura': self.datos_factura_json,
            'fecha_procesamiento': self.fecha_procesamiento
        }
    
    @property
    def num_ordenes(self) -> int:
        '''Retorna el número de órdenes de compra'''
        return len(self.ordenes_de_compra) if self.ordenes_de_compra else 0

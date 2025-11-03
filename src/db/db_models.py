import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Numeric, 
    Date, TIMESTAMP, Boolean, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import JSONB  # Específico para PostgreSQL 
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Base declarativa de SQLAlchemy
Base = declarative_base()

class CaLicitacion(Base):
    """
    Tabla Maestra: ca_licitacion
    Almacena todos los campos maestros y detallados de una CA.
    """
    __tablename__ = 'ca_licitacion'
    
    # Columnas 
    ca_id = Column(Integer, primary_key=True)
    codigo_ca = Column(String(20), nullable=False, unique=True)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text)
    monto_clp = Column(Numeric(15, 2))
    fecha_publicacion = Column(Date)
    fecha_cierre = Column(TIMESTAMP(timezone=True))
    fecha_cierre_p1 = Column(TIMESTAMP(timezone=True))
    fecha_cierre_p2 = Column(TIMESTAMP(timezone=True))
    direccion_entrega = Column(String(255))
    proveedores_cotizando = Column(Integer)
    productos_solicitados = Column(JSONB) # Tipo de dato JSONB para PostgreSQL 
    estado_ca_texto = Column(String(50))
    puntuacion_final = Column(Integer, index=True) # Indexado para búsquedas rápidas 
    
    # Relaciones (Lógica de SQLAlchemy, no son columnas SQL)
    # Relación 1-a-1 con ca_seguimiento
    seguimiento = relationship(
        "CaSeguimiento", 
        back_populates="licitacion", 
        uselist=False, # Indica que es 1-a-1
        cascade="all, delete-orphan" # Borra el seguimiento si se borra la licitación
    )
    
    # Relación 1-a-N con ca_historial_estado
    historial = relationship(
        "CaHistorialEstado", 
        back_populates="licitacion",
        cascade="all, delete-orphan" # Borra el historial si se borra la licitación
    )
    
    # Índices adicionales
    __table_args__ = (
        Index('ix_ca_licitacion_codigo_ca', 'codigo_ca', unique=True),
    )

class CaSeguimiento(Base):
    """
    Tabla de Monitoreo: ca_seguimiento
    Permite marcar favoritos y monitorear su estado.
    """
    __tablename__ = 'ca_seguimiento'
    
    # Usamos ca_id como PK y FK en una relación 1-a-1
    ca_id = Column(Integer, ForeignKey('ca_licitacion.ca_id'), primary_key=True)
    es_favorito = Column(Boolean, default=False, index=True)
    estado_actual_id = Column(Integer)
    fecha_ultimo_chequeo = Column(TIMESTAMP(timezone=True))
    
    # Relación inversa 1-a-1
    licitacion = relationship("CaLicitacion", back_populates="seguimiento")

class CaHistorialEstado(Base):
    """
    Tabla de Auditoría: ca_historial_estado
    Registra todos los cambios de estado detectados.
    """
    __tablename__ = 'ca_historial_estado'
    
    historial_id = Column(Integer, primary_key=True)
    ca_id = Column(Integer, ForeignKey('ca_licitacion.ca_id'), index=True)
    fecha_registro = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow)
    estado_anterior_id = Column(Integer)
    estado_nuevo_id = Column(Integer)
    
    # Relación inversa N-a-1
    licitacion = relationship("CaLicitacion", back_populates="historial")
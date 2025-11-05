import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Numeric, 
    Date, TIMESTAMP, Boolean, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

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
    productos_solicitados = Column(JSONB) 
    estado_ca_texto = Column(String(50))
    puntuacion_final = Column(Integer, index=True) 
    
    # Relaciones (Lógica de SQLAlchemy, no son columnas SQL)
    seguimiento = relationship(
        "CaSeguimiento", 
        back_populates="licitacion", 
        uselist=False, 
        cascade="all, delete-orphan" 
    )
    
    historial = relationship(
        "CaHistorialEstado", 
        back_populates="licitacion",
        cascade="all, delete-orphan" 
    )
    
    __table_args__ = (
        Index('ix_ca_licitacion_codigo_ca', 'codigo_ca', unique=True),
    )

class CaSeguimiento(Base):
    """
    Tabla de Monitoreo: ca_seguimiento
    Permite marcar favoritos y monitorear su estado.
    """
    __tablename__ = 'ca_seguimiento'
    
    ca_id = Column(Integer, ForeignKey('ca_licitacion.ca_id'), primary_key=True)
    es_favorito = Column(Boolean, default=False, index=True)
    
    # --- ¡NUEVA COLUMNA! ---
    es_ofertada = Column(Boolean, default=False, index=True)
    # ----------------------
    
    estado_actual_id = Column(Integer)
    fecha_ultimo_chequeo = Column(TIMESTAMP(timezone=True))
    
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
    
    licitacion = relationship("CaLicitacion", back_populates="historial")
import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.config import DATABASE_URL
from .db_models import Base, CaLicitacion 
from typing import List, Dict

# --- Importar el logger ---
from src.utils.logger import configurar_logger
logger = configurar_logger('db_service') # Configurar un logger para este módulo
# ---

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True, 
    )
except Exception as e:
    logger.critical(f"Error al crear el engine de SQLAlchemy: {e}") # Usar logger
    exit(1)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def init_db():
    logger.info("Inicializando base de datos...") # Usar logger
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas creadas exitosamente (si no existían).") # Usar logger
    except Exception as e:
        logger.critical(f"Error al conectar o crear tablas en PostgreSQL: {e}") # Usar logger
        logger.critical("---")
        logger.critical("Por favor, asegúrate de que:")
        logger.critical(f"  1. PostgreSQL esté corriendo en {os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}.")
        logger.critical(f"  2. La base de datos '{os.getenv('DB_NAME', 'ca_monitor')}' exista.")
        logger.critical("  3. El usuario y contraseña en tu archivo .env sean correctos.")

def _parse_fecha(fecha_str: str):
    """Convierte un string de fecha (ej: '2025-10-30' o timestamp) a un objeto date."""
    if not fecha_str:
        return None
    try:
        # Intentar parsear timestamp completo primero (ej: 2025-11-01T23:59:00.000Z)
        return datetime.datetime.fromisoformat(fecha_str.replace('Z', '+00:00')).date()
    except (ValueError, TypeError):
        try:
            # Si falla, intentar parsear solo fecha (ej: 2025-11-01)
            return datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except Exception:
            logger.warning(f"No se pudo parsear la fecha: {fecha_str}")
            return None

def _parse_monto(monto_str: str):
    """Convierte un string de monto a float."""
    if monto_str is None:
        return None
    try:
        return float(monto_str)
    except (ValueError, TypeError):
        return None

def insertar_o_actualizar_licitaciones(session: Session, compras: List[Dict]):
    codigos_procesados = set()
    
    # --- Contadores ---
    nuevos_inserts = 0
    actualizaciones = 0
    # ---

    for item in compras:
        codigo = item.get('codigo', item.get('id'))
        if not codigo:
            continue 

        if codigo in codigos_procesados:
            continue
        codigos_procesados.add(codigo)

        licitacion_existente = session.query(CaLicitacion).filter_by(codigo_ca=codigo).first()
        
        if licitacion_existente:
            licitacion_existente.proveedores_cotizando = item.get('cantidad_provedores_cotizando')
            licitacion_existente.estado_ca_texto = item.get('estado')
            licitacion_existente.fecha_cierre = item.get('fecha_cierre') # Actualizar fecha de cierre
            actualizaciones += 1 # Contar
        
        else:
            nueva_licitacion = CaLicitacion(
                codigo_ca = codigo,
                nombre = item.get('nombre'),
                monto_clp = _parse_monto(item.get('monto_disponible_CLP')),
                fecha_publicacion = _parse_fecha(item.get('fecha_publicacion')),
                fecha_cierre = item.get('fecha_cierre'), 
                proveedores_cotizando = item.get('cantidad_provedores_cotizando'),
                estado_ca_texto = item.get('estado')
            )
            session.add(nueva_licitacion)
            nuevos_inserts += 1 # Contar

    try:
        session.commit()
        # --- Log detallado ---
        logger.info(f"Commit exitoso: {nuevos_inserts} nuevos, {actualizaciones} actualizados.")
    except Exception as e:
        logger.error(f"Error al hacer commit en la base de datos: {e}")
        session.rollback()
    finally:
        session.close()
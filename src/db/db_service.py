import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.config import DATABASE_URL
from .db_models import Base, CaLicitacion 
from typing import List, Dict

# --- Importar el logger ---
from src.utils.logger import configurar_logger
logger = configurar_logger('db_service')
# ---

# --- ¡NUEVAS IMPORTACIONES! ---
# Importamos el motor de puntuación y el umbral
from src.logic.score_engine import calcular_puntuacion_fase_1
from config.score_config import UMBRAL_FASE_2
# ---

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True, 
    )
except Exception as e:
    logger.critical(f"Error al crear el engine de SQLAlchemy: {e}")
    exit(1)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def init_db():
    logger.info("Inicializando base de datos...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas creadas exitosamente (si no existían).")
    except Exception as e:
        logger.critical(f"Error al conectar o crear tablas en PostgreSQL: {e}")
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
    """
    Procesa una lista de compras, las puntúa (Fase 1) y las inserta o 
    actualiza en la BD si superan el UMBRAL_FASE_2.
    """
    logger.info(f"Recibidas {len(compras)} compras para procesar y puntuar...")
    
    codigos_procesados = set()
    nuevos_inserts = 0
    actualizaciones = 0
    omitidos_duplicados = 0
    omitidos_score = 0 # <-- Nuevo contador

    for item in compras:
        codigo = item.get('codigo', item.get('id'))
        if not codigo:
            omitidos_duplicados += 1
            logger.debug("Compra sin código omitida")
            continue 

        if codigo in codigos_procesados:
            omitidos_duplicados += 1
            logger.debug(f"Código duplicado omitido: {codigo}")
            continue
        codigos_procesados.add(codigo)

        # --- ¡NUEVA LÓGICA DE SCORING! ---
        # 1. Calcular puntuación ANTES de consultar la BD
        puntos_fase_1 = calcular_puntuacion_fase_1(item)

        # 2. Aplicar Umbral (Punto de corte)
        if puntos_fase_1 < UMBRAL_FASE_2:
            omitidos_score += 1
            logger.debug(f"Compra {codigo} omitida. Puntuación: {puntos_fase_1} (Umbral: {UMBRAL_FASE_2})")
            continue # No guardar en la BD
        # --- FIN DE LA LÓGICA DE SCORING ---

        # Si la compra supera el umbral, la procesamos:
        licitacion_existente = session.query(CaLicitacion).filter_by(codigo_ca=codigo).first()
        
        if licitacion_existente:
            # Actualizar datos y la puntuación (puede haber cambiado)
            licitacion_existente.proveedores_cotizando = item.get('cantidad_provedores_cotizando')
            licitacion_existente.estado_ca_texto = item.get('estado')
            licitacion_existente.fecha_cierre = item.get('fecha_cierre')
            licitacion_existente.puntuacion_final = puntos_fase_1 # <-- Actualizar score
            actualizaciones += 1
        
        else:
            # Crear nueva licitación con su puntuación
            nueva_licitacion = CaLicitacion(
                codigo_ca = codigo,
                nombre = item.get('nombre'),
                monto_clp = _parse_monto(item.get('monto_disponible_CLP')),
                fecha_publicacion = _parse_fecha(item.get('fecha_publicacion')),
                fecha_cierre = item.get('fecha_cierre'), 
                proveedores_cotizando = item.get('cantidad_provedores_cotizando'),
                estado_ca_texto = item.get('estado'),
                puntuacion_final = puntos_fase_1 # <-- Guardar score
            )
            session.add(nueva_licitacion)
            nuevos_inserts += 1

    logger.info(f"Procesadas {len(codigos_procesados)} compras únicas")
    logger.info(f"Omitidas {omitidos_duplicados} (sin código o duplicadas)")
    logger.info(f"Omitidas {omitidos_score} por baja puntuación (Score < {UMBRAL_FASE_2})")
    
    try:
        session.commit()
        logger.info(f"Commit exitoso: {nuevos_inserts} nuevos, {actualizaciones} actualizados.")
    except Exception as e:
        logger.error(f"Error al hacer commit en la base de datos: {e}")
        session.rollback()
        raise
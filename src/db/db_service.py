import os
import datetime
from sqlalchemy import create_engine, select, join
from sqlalchemy.orm import sessionmaker, Session
from config.config import DATABASE_URL
from .db_models import Base, CaLicitacion, CaSeguimiento
from typing import List, Dict

# --- Importar el logger ---
from src.utils.logger import configurar_logger
logger = configurar_logger('db_service')
# ---
# Importamos el motor de puntuación y el umbral
from src.logic.score_engine import calcular_puntuacion_fase_1
from config.score_config import UMBRAL_FASE_2, UMBRAL_FINAL


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

def obtener_candidatas_para_fase_2(session: Session) -> List[CaLicitacion]:
    """
    Obtiene todas las CAs que pasaron la Fase 1 (tienen puntaje >= UMBRAL_FASE_2)
    pero que aún no han sido procesadas por el scraper de Ficha Individual
    (es decir, su 'descripcion' o 'productos_solicitados' están vacíos).
    """
    logger.info(f"Buscando CAs candidatas para scraping Fase 2 (Score >= {UMBRAL_FASE_2})...")
    
    candidatas = session.query(CaLicitacion).filter(
        CaLicitacion.puntuacion_final >= UMBRAL_FASE_2,
        CaLicitacion.descripcion.is_(None) # Filtra las que no tienen descripción
    ).order_by(CaLicitacion.fecha_cierre.asc()).all() # Prioriza las más prontas a cerrar
    
    logger.info(f"Se encontraron {len(candidatas)} CAs para procesar en Fase 2.")
    return candidatas

def actualizar_ca_con_fase_2(session: Session, codigo_ca: str, datos_fase_2: Dict, puntuacion_total: int):
    """
    Actualiza una CA existente con los datos detallados de la Fase 2 
    y su puntuación final total (Fase 1 + Fase 2).
    """
    try:
        licitacion = session.query(CaLicitacion).filter_by(codigo_ca=codigo_ca).first()
        if not licitacion:
            logger.error(f"[Fase 2] No se encontró la CA {codigo_ca} en la BD para actualizar.")
            return

        # Actualizar campos de la Fase 2 [cite: 167]
        licitacion.descripcion = datos_fase_2.get('descripcion')
        licitacion.productos_solicitados = datos_fase_2.get('productos_solicitados')
        licitacion.direccion_entrega = datos_fase_2.get('direccion_entrega')
        licitacion.fecha_cierre_p1 = datos_fase_2.get('fecha_cierre_p1')
        licitacion.fecha_cierre_p2 = datos_fase_2.get('fecha_cierre_p2')
        
        # Actualizar la puntuación final [cite: 164]
        licitacion.puntuacion_final = puntuacion_total
        
        session.commit()
        logger.debug(f"[Fase 2] CA {codigo_ca} actualizada con éxito. Nueva puntuación: {puntuacion_total}")

    except Exception as e:
        logger.error(f"[Fase 2] Error al actualizar CA {codigo_ca}: {e}")
        session.rollback()
        raise

# --- Funciones para la GUI (Fase 3) ---

def obtener_datos_tab1_candidatas(session: Session) -> List[CaLicitacion]:
    """
    GUI: Obtiene las CAs para la Pestaña 1.
    (ca_licitacion donde puntuacion_final >= 5)
    """
    logger.debug(f"GUI: Obteniendo datos para Pestaña 1 (Score >= {UMBRAL_FASE_2})")
    return session.query(CaLicitacion).filter(
        CaLicitacion.puntuacion_final >= UMBRAL_FASE_2
    ).order_by(CaLicitacion.puntuacion_final.desc()).all()


def obtener_datos_tab2_relevantes(session: Session) -> List[CaLicitacion]:
    """
    GUI: Obtiene las CAs para la Pestaña 2.
    (ca_licitacion donde puntuacion_final >= 9)
    """
    logger.debug(f"GUI: Obteniendo datos para Pestaña 2 (Score >= {UMBRAL_FINAL})")
    return session.query(CaLicitacion).filter(
        CaLicitacion.puntuacion_final >= UMBRAL_FINAL
    ).order_by(CaLicitacion.puntuacion_final.desc()).all()


def obtener_datos_tab3_seguimiento(session: Session) -> List[CaLicitacion]:
    """
    GUI: Obtiene las CAs para la Pestaña 3.
    (JOIN ca_licitacion con ca_seguimiento donde es_favorito = TRUE)
    """
    logger.debug("GUI: Obteniendo datos para Pestaña 3 (Favoritos)")
    
    # Construimos un JOIN explícito
    stmt = (
        select(CaLicitacion)
        .select_from(
            join(CaLicitacion, CaSeguimiento, 
                 CaLicitacion.ca_id == CaSeguimiento.ca_id)
        )
        .filter(CaSeguimiento.es_favorito == True)
        .order_by(CaLicitacion.fecha_cierre.asc())
    )
    
    # execute() retorna 'scalars' que son los objetos CaLicitacion
    return session.scalars(stmt).all()

def gestionar_favorito(session: Session, ca_id: int, es_favorito: bool):
    """
    Marca o desmarca una CA como favorita.
    Crea o actualiza el registro en 'ca_seguimiento'.
    """
    logger.debug(f"GUI: Gestionando favorito. ID: {ca_id}, Set Favorito: {es_favorito}")
    
    # Buscar si ya existe un registro de seguimiento
    seguimiento = session.query(CaSeguimiento).filter_by(ca_id=ca_id).first()
    
    if seguimiento:
        # Si existe, solo actualiza el estado 'es_favorito'
        seguimiento.es_favorito = es_favorito
        logger.info(f"CA {ca_id} actualizada a es_favorito={es_favorito}")
    else:
        # Si no existe, crear un nuevo registro
        # (Esto solo debería pasar si se marca como favorito, 
        # pero lo manejamos por si acaso)
        if es_favorito:
            nuevo_seguimiento = CaSeguimiento(
                ca_id=ca_id,
                es_favorito=True
            )
            session.add(nuevo_seguimiento)
            logger.info(f"CA {ca_id} insertada en seguimiento como favorito.")
        
    try:
        session.commit()
    except Exception as e:
        logger.error(f"Error al gestionar favorito para CA {ca_id}: {e}")
        session.rollback()


def eliminar_ca_definitivamente(session: Session, ca_id: int):
    """
    Elimina una CA de la base de datos (DELETE en ca_licitacion).
    El cascade (definido en db_models.py) borrará los registros
    relacionados en ca_seguimiento y ca_historial_estado.
    """
    logger.debug(f"GUI: Eliminación definitiva de CA ID: {ca_id}")
    
    licitacion = session.query(CaLicitacion).filter_by(ca_id=ca_id).first()
    
    if licitacion:
        try:
            session.delete(licitacion)
            session.commit()
            logger.info(f"CA {ca_id} eliminada permanentemente de la BD.")
        except Exception as e:
            logger.error(f"Error en eliminación definitiva de CA {ca_id}: {e}")
            session.rollback()
    else:
        logger.warning(f"No se encontró CA {ca_id} para eliminación definitiva.")
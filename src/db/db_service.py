import os
import datetime
from sqlalchemy import create_engine, select, join
from sqlalchemy.orm import sessionmaker, Session, joinedload # <-- ¡NUEVA IMPORTACIÓN!
from config.config import DATABASE_URL
from .db_models import Base, CaLicitacion, CaSeguimiento 
from typing import List, Dict

# --- Importar el logger ---
from src.utils.logger import configurar_logger
logger = configurar_logger('db_service')
# ---

# --- Importar score config ---
from config.score_config import UMBRAL_FASE_2, UMBRAL_FINAL
# ---

# --- Importar lógica de scoring ---
from src.logic.score_engine import calcular_puntuacion_fase_1
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
        logger.info("Tablas creadas/actualizadas exitosamente.")
    except Exception as e:
        logger.critical(f"Error al conectar o crear tablas en PostgreSQL: {e}")
        logger.critical("---")
        logger.critical(f"  1. PostgreSQL esté corriendo en {os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}.")
        logger.critical(f"  2. La base de datos '{os.getenv('DB_NAME', 'ca_monitor')}' exista.")
        logger.critical("  3. El usuario y contraseña en tu archivo .env sean correctos.")

def _parse_fecha(fecha_str: str):
    if not fecha_str:
        return None
    try:
        return datetime.datetime.fromisoformat(fecha_str.replace('Z', '+00:00')).date()
    except (ValueError, TypeError):
        try:
            return datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except Exception:
            logger.warning(f"No se pudo parsear la fecha: {fecha_str}")
            return None

def _parse_monto(monto_str: str):
    if monto_str is None:
        return None
    try:
        return float(monto_str)
    except (ValueError, TypeError):
        return None

def insertar_o_actualizar_licitaciones(session: Session, compras: List[Dict]):
    logger.info(f"Recibidas {len(compras)} compras para procesar y puntuar...")
    
    codigos_procesados = set()
    nuevos_inserts = 0
    actualizaciones = 0
    omitidos_duplicados = 0
    omitidos_score = 0

    for item in compras:
        codigo = item.get('codigo', item.get('id'))
        if not codigo:
            omitidos_duplicados += 1
            continue 
        if codigo in codigos_procesados:
            omitidos_duplicados += 1
            continue
        codigos_procesados.add(codigo)

        puntos_fase_1 = calcular_puntuacion_fase_1(item)

        if puntos_fase_1 < UMBRAL_FASE_2:
            omitidos_score += 1
            continue 

        licitacion_existente = session.query(CaLicitacion).filter_by(codigo_ca=codigo).first()
        
        if licitacion_existente:
            licitacion_existente.proveedores_cotizando = item.get('cantidad_provedores_cotizando')
            licitacion_existente.estado_ca_texto = item.get('estado')
            licitacion_existente.fecha_cierre = item.get('fecha_cierre')
            licitacion_existente.puntuacion_final = puntos_fase_1 
            actualizaciones += 1
        
        else:
            nueva_licitacion = CaLicitacion(
                codigo_ca = codigo,
                nombre = item.get('nombre'),
                monto_clp = _parse_monto(item.get('monto_disponible_CLP')),
                fecha_publicacion = _parse_fecha(item.get('fecha_publicacion')),
                fecha_cierre = item.get('fecha_cierre'), 
                proveedores_cotizando = item.get('cantidad_provedores_cotizando'),
                estado_ca_texto = item.get('estado'),
                puntuacion_final = puntos_fase_1 
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

# --- Funciones de Fase 2 (Scraping Detalle) ---

def obtener_candidatas_para_fase_2(session: Session) -> List[CaLicitacion]:
    logger.info(f"Buscando CAs candidatas para scraping Fase 2 (Score >= {UMBRAL_FASE_2})...")
    
    # ¡MODIFICADO! Añadir joinedload para la relación 'seguimiento'
    candidatas = session.query(CaLicitacion).options(
        joinedload(CaLicitacion.seguimiento)
    ).filter(
        CaLicitacion.puntuacion_final >= UMBRAL_FASE_2,
        CaLicitacion.descripcion.is_(None) 
    ).order_by(CaLicitacion.fecha_cierre.asc()).all() 
    
    logger.info(f"Se encontraron {len(candidatas)} CAs para procesar en Fase 2.")
    return candidatas

def actualizar_ca_con_fase_2(session: Session, codigo_ca: str, datos_fase_2: Dict, puntuacion_total: int):
    try:
        licitacion = session.query(CaLicitacion).filter_by(codigo_ca=codigo_ca).first()
        if not licitacion:
            logger.error(f"[Fase 2] No se encontró la CA {codigo_ca} en la BD para actualizar.")
            return

        licitacion.descripcion = datos_fase_2.get('descripcion')
        licitacion.productos_solicitados = datos_fase_2.get('productos_solicitados')
        licitacion.direccion_entrega = datos_fase_2.get('direccion_entrega')
        licitacion.fecha_cierre_p1 = datos_fase_2.get('fecha_cierre_p1')
        licitacion.fecha_cierre_p2 = datos_fase_2.get('fecha_cierre_p2')
        licitacion.puntuacion_final = puntuacion_total
        
        session.commit()
        logger.debug(f"[Fase 2] CA {codigo_ca} actualizada con éxito. Nueva puntuación: {puntuacion_total}")

    except Exception as e:
        logger.error(f"[Fase 2] Error al actualizar CA {codigo_ca}: {e}")
        session.rollback()
        raise

# --- Funciones para la GUI (Fase 3 y 4) ---

def obtener_datos_tab1_candidatas(session: Session) -> List[CaLicitacion]:
    logger.debug(f"GUI: Obteniendo datos para Pestaña 1 (Score >= {UMBRAL_FASE_2})")
    # ¡MODIFICADO! Añadir joinedload
    return session.query(CaLicitacion).options(
        joinedload(CaLicitacion.seguimiento)
    ).filter(
        CaLicitacion.puntuacion_final >= UMBRAL_FASE_2
    ).order_by(CaLicitacion.puntuacion_final.desc()).all()


def obtener_datos_tab2_relevantes(session: Session) -> List[CaLicitacion]:
    logger.debug(f"GUI: Obteniendo datos para Pestaña 2 (Score >= {UMBRAL_FINAL})")
    # ¡MODIFICADO! Añadir joinedload
    return session.query(CaLicitacion).options(
        joinedload(CaLicitacion.seguimiento)
    ).filter(
        CaLicitacion.puntuacion_final >= UMBRAL_FINAL
    ).order_by(CaLicitacion.puntuacion_final.desc()).all()


def obtener_datos_tab3_seguimiento(session: Session) -> List[CaLicitacion]:
    logger.debug("GUI: Obteniendo datos para Pestaña 3 (Favoritos)")
    
    # ¡MODIFICADO! Añadir joinedload
    stmt = (
        select(CaLicitacion)
        .options(joinedload(CaLicitacion.seguimiento)) 
        .select_from(
            join(CaLicitacion, CaSeguimiento, 
                 CaLicitacion.ca_id == CaSeguimiento.ca_id)
        )
        .filter(CaSeguimiento.es_favorito == True)
        .order_by(CaLicitacion.fecha_cierre.asc())
    )
    return session.scalars(stmt).all()

def obtener_datos_tab4_ofertadas(session: Session) -> List[CaLicitacion]:
    logger.debug("GUI: Obteniendo datos para Pestaña 4 (Ofertadas)")
    
    # ¡MODIFICADO! Añadir joinedload
    stmt = (
        select(CaLicitacion)
        .options(joinedload(CaLicitacion.seguimiento))
        .select_from(
            join(CaLicitacion, CaSeguimiento, 
                 CaLicitacion.ca_id == CaSeguimiento.ca_id)
        )
        .filter(CaSeguimiento.es_ofertada == True)
        .order_by(CaLicitacion.fecha_cierre.asc())
    )
    return session.scalars(stmt).all()

# --- Funciones de Acciones de Menú ---

def gestionar_favorito(session: Session, ca_id: int, es_favorito: bool):
    logger.debug(f"GUI: Gestionando favorito. ID: {ca_id}, Set Favorito: {es_favorito}")
    
    seguimiento = session.query(CaSeguimiento).filter_by(ca_id=ca_id).first()
    
    if seguimiento:
        seguimiento.es_favorito = es_favorito
        logger.info(f"CA {ca_id} actualizada a es_favorito={es_favorito}")
    elif es_favorito:
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

def gestionar_ofertada(session: Session, ca_id: int, es_ofertada: bool):
    logger.debug(f"GUI: Gestionando ofertada. ID: {ca_id}, Set Ofertada: {es_ofertada}")
    
    seguimiento = session.query(CaSeguimiento).filter_by(ca_id=ca_id).first()
    
    if seguimiento:
        seguimiento.es_ofertada = es_ofertada
        if es_ofertada:
            seguimiento.es_favorito = True
        logger.info(f"CA {ca_id} actualizada a es_ofertada={es_ofertada}")
    elif es_ofertada:
        nuevo_seguimiento = CaSeguimiento(
            ca_id=ca_id,
            es_favorito=True, 
            es_ofertada=True
        )
        session.add(nuevo_seguimiento)
        logger.info(f"CA {ca_id} insertada en seguimiento como ofertada.")
        
    try:
        session.commit()
    except Exception as e:
        logger.error(f"Error al gestionar ofertada para CA {ca_id}: {e}")
        session.rollback()

def eliminar_ca_definitivamente(session: Session, ca_id: int):
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
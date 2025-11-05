import time
from sqlalchemy.orm import Session
from PySide6.QtCore import Signal
from playwright.sync_api import sync_playwright

from src.utils.logger import configurar_logger
from src.db.db_service import (
    obtener_candidatas_para_fase_2, 
    actualizar_ca_con_fase_2,
    CaLicitacion
)
from src.scraper.scraper_service import (
    run_scraper_listado, 
    scrape_ficha_detalle_api
)
from src.logic.score_engine import calcular_puntuacion_fase_2
from config.config import MODO_HEADLESS, TIMEOUT_REQUESTS

logger = configurar_logger('etl_service')

def run_full_etl_process(
    db_session: Session, 
    progress_callback: Signal, 
    config: dict
):
    """
    Función maestra que ejecuta el proceso ETL (Extract, Transform, Load) completo.
    1. Ejecuta Fase 1 (Scraping Listado)
    2. Ejecuta Fase 2 (Scraping Fichas)
    """
    
    date_from = config['date_from']
    date_to = config['date_to']
    max_paginas = config['max_paginas']
    
    logger.info(f"Iniciando Proceso ETL Completo... Rango: {date_from} a {date_to}")
    progress_callback.emit(f"Iniciando Fase 1 (Listado) Rango: {date_from} a {date_to}...")

    # --- 1. EJECUTAR FASE 1 (LISTADO) ---
    try:
        filtros_fase_1 = {
            'date_from': date_from,
            'date_to': date_to
        }
        # Esta función ya guarda en la BD
        run_scraper_listado(
            db_session=db_session,
            progress_callback=progress_callback,
            filtros=filtros_fase_1,
            max_paginas=max_paginas
        )
    except Exception as e:
        logger.critical(f"Proceso ETL falló catastróficamente en Fase 1: {e}")
        progress_callback.emit(f"Error Crítico en Fase 1: {e}")
        raise e # Relanzar el error para que el worker lo capture
    
    
    # --- 2. OBTENER CANDIDATAS PARA FASE 2 ---
    progress_callback.emit("Obteniendo candidatas para Fase 2...")
    try:
        # Usamos la misma sesión del hilo, no una nueva
        candidatas: list[CaLicitacion] = obtener_candidatas_para_fase_2(db_session)
    except Exception as e:
        logger.error(f"Error al obtener candidatas de la BD: {e}")
        progress_callback.emit(f"Error de BD: {e}")
        return # Terminar si no podemos obtener candidatas
        
    if not candidatas:
        logger.info("Proceso ETL finalizado. No hay candidatas nuevas para Fase 2.")
        progress_callback.emit("Proceso finalizado. No hay CAs nuevas para Fase 2.")
        return

    logger.info(f"Se encontraron {len(candidatas)} CAs para procesar en Fase 2.")
    progress_callback.emit(f"Iniciando Fase 2 (Fichas). {len(candidatas)} CAs por procesar...")

    # --- 3. EJECUTAR FASE 2 (FICHAS) ---
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=MODO_HEADLESS, slow_mo=500)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit(537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-CL'
            )
            page = context.new_page()

            exitosas = 0
            total = len(candidatas)
            
            for i, licitacion in enumerate(candidatas):
                codigo_ca = licitacion.codigo_ca
                puntos_fase_1 = licitacion.puntuacion_final
                
                logger.info(f"--- [Fase 2] Procesando {i+1}/{total}: {codigo_ca} ---")
                progress_callback.emit(f"Fase 2: Procesando {i+1}/{total} ({codigo_ca})...")
                
                # 4. Scrapear la ficha
                datos_ficha = scrape_ficha_detalle_api(page, codigo_ca, progress_callback)
                
                if datos_ficha is None:
                    logger.error(f"No se pudieron obtener datos de la ficha para {codigo_ca}.")
                    continue
                
                # 5. Calcular puntuación
                ca_dict_fase_1 = {
                    'codigo': licitacion.codigo_ca,
                    'nombre': licitacion.nombre
                }
                puntos_fase_2 = calcular_puntuacion_fase_2(ca_dict_fase_1, datos_ficha)
                puntuacion_total = puntos_fase_1 + puntos_fase_2
                
                # 6. Actualizar la BD (usando la misma sesión de hilo)
                actualizar_ca_con_fase_2(db_session, codigo_ca, datos_ficha, puntuacion_total)
                
                exitosas += 1
                time.sleep(1) # Pausa breve

            context.close()
            browser.close()

        except Exception as e:
            logger.critical(f"FALLO EL PROCESO DE SCRAPING FASE 2: {e}")
            progress_callback.emit(f"Error Crítico en Fase 2: {e}")
            raise e
        finally:
            logger.info(f"Resumen Fase 2: {exitosas}/{total} procesadas exitosamente.")
            
    progress_callback.emit("Proceso ETL Completo. Refrescando datos...")
    logger.info("Proceso ETL Completo.")
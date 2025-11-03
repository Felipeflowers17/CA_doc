import time
from playwright.sync_api import sync_playwright, Page, Response
from typing import Optional, Dict

from src.utils.logger import configurar_logger
from src.db.db_service import SessionLocal, insertar_o_actualizar_licitaciones
from . import api_handler
from .url_builder import construir_url_listado
from config.config import (
    MODO_HEADLESS,
    TIMEOUT_REQUESTS,
    DELAY_ENTRE_PAGINAS
)

logger = configurar_logger('scraper_service')

def scrapear_pagina_listado(page: Page, numero_pagina: int, filtros: Dict) -> tuple:
    """
    Scrapea una única página del listado esperando la respuesta de API correcta.
    
    Returns:
        (exito, metadata_paginacion, lista_resultados)
    """
    try:
        url = construir_url_listado(numero_pagina, filtros)
        logger.info(f"Navegando a página {numero_pagina}...")
        logger.debug(f"URL: {url}")

        with page.expect_response(
            lambda r: "api.buscador.mercadopublico.cl/compra-agil" in r.url and \
                      f"page_number={numero_pagina}" in r.url,
            timeout=TIMEOUT_REQUESTS * 1000
        ) as response_event:
            # --- CAMBIO 1: De 'networkidle' a 'load' ---
            # Esto es más rápido y estable. Dejamos que 'expect_response'
            # se encargue de la espera inteligente.
            page.goto(url, wait_until='load', timeout=TIMEOUT_REQUESTS * 1000)

        response = response_event.value
        datos_json = response.json()
        
        if not api_handler.validar_respuesta_api(datos_json, logger):
            logger.error(f"Respuesta API inválida para página {numero_pagina}.")
            return False, {}, []

        metadata = api_handler.extraer_metadata_paginacion(datos_json, logger)
        resultados = api_handler.extraer_resultados(datos_json, logger)
        
        logger.info(f"Página {numero_pagina} procesada: {len(resultados)} compras encontradas.")
        
        if resultados:
            logger.debug(f"Iniciando guardado en BD para {len(resultados)} items...")
            db_session = SessionLocal()
            insertar_o_actualizar_licitaciones(db_session, resultados)
        
        return True, metadata, resultados

    except Exception as e:
        if "Timeout" in str(e):
             logger.error(f"TIMEOUT en página {numero_pagina}. La API no respondió a tiempo.")
        else:
            logger.error(f"ERROR crítico al scrapear página {numero_pagina}: {e}")
        return False, {}, []

def run_scraper_listado(filtros: Optional[Dict] = None, max_paginas: Optional[int] = None):
    logger.info("="*60)
    logger.info("INICIANDO SCRAPER DE LISTADO - FASE 1 (Listado)")
    logger.info("="*60)
    logger.info(f"Filtros aplicados: {filtros or 'Por defecto'}")
    logger.info(f"Límite de páginas: {max_paginas or 'Sin límite'}")
    
    tiempo_inicio = time.time()
    total_compras_procesadas = 0 # Renombrado para claridad
    paginas_procesadas = 0
    
    # --- CAMBIO 2: Inicializar 'limite' ---
    # Asignamos un valor por defecto para evitar el UnboundLocalError
    limite = max_paginas if max_paginas is not None else 0
    
    with sync_playwright() as p:
        try:
            logger.info("Iniciando navegador (Playwright)...")
            browser = p.chromium.launch(headless=MODO_HEADLESS, slow_mo=500)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-CL'
            )
            page = context.new_page()

            # --- Procesar Página 1 ---
            exito, metadata, resultados = scrapear_pagina_listado(page, 1, filtros)
            if not exito:
                raise Exception("No se pudo obtener la página 1. Abortando.")
            
            total_resultados = metadata.get('resultCount', 0)
            total_paginas = metadata.get('pageCount', 0)
            total_compras_procesadas += len(resultados)
            paginas_procesadas += 1
            
            logger.info(f"Total resultados encontrados: {total_resultados}")
            logger.info(f"Total páginas a scrapear: {total_paginas}")

            # Definimos el límite real de páginas
            limite = total_paginas
            if max_paginas is not None and max_paginas < total_paginas:
                limite = max_paginas
            
            logger.info(f"Límite de páginas establecido en: {limite}")

            # --- Procesar Páginas Restantes (2 hasta N) ---
            for num_pagina in range(2, limite + 1):
                time.sleep(DELAY_ENTRE_PAGINAS) 
                
                exito, _, resultados_pagina = scrapear_pagina_listado(page, num_pagina, filtros)
                
                if exito:
                    total_compras_procesadas += len(resultados_pagina)
                    paginas_procesadas += 1
                else:
                    logger.warning(f"Se omite la página {num_pagina} por error.")

            context.close()
            browser.close()
            logger.info("Navegador (Playwright) cerrado.")

        except Exception as e:
            logger.critical(f"FALLO EL PROCESO DE SCRAPING: {e}")
        finally:
            tiempo_total = time.time() - tiempo_inicio
            logger.info("="*60)
            logger.info("RESUMEN DE SCRAPING (Listado)")
            logger.info(f"Tiempo total: {tiempo_total:.2f} segundos")
            logger.info(f"Páginas procesadas: {paginas_procesadas} / {limite if limite > 0 else (paginas_procesadas if paginas_procesadas > 0 else 'N/A')}")
            logger.info(f"Total compras procesadas: {total_compras_procesadas}")
            logger.info("="*60)
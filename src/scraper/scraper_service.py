import time
# (El resto de tus imports: playwright, typing, logger, db, etc.)
from playwright.sync_api import sync_playwright, Page, Response
from typing import Optional, Dict, Callable

from src.utils.logger import configurar_logger
from src.db.db_service import SessionLocal, insertar_o_actualizar_licitaciones
from . import api_handler
from .url_builder import construir_url_listado, construir_url_ficha, construir_url_api_ficha
from config.config import (
    MODO_HEADLESS,
    TIMEOUT_REQUESTS,
    DELAY_ENTRE_PAGINAS
)

logger = configurar_logger('scraper_service')

HEADERS_API = {
    'X-Api-Key': 'e93089e4-437c-4723-b343-4fa20045e3bc'
}


# ===================================================================
# === ESTA FUNCIÓN NO CAMBIA ===
# (scrapear_pagina_listado se queda igual que la versión anterior)
# ===================================================================
def scrapear_pagina_listado(page: Page, numero_pagina: int, accion_trigger: Callable[[], None]) -> tuple:
    logger.debug(f"Configurando listener para API page_number={numero_pagina}...")
    try:
        predicate = lambda response: (
            'api.buscador.mercadopublico.cl/compra-agil' in response.url and
            f"page_number={numero_pagina}" in response.url and
            response.status == 200
        )
        with page.expect_response(predicate, timeout=TIMEOUT_REQUESTS * 1000) as response_info:
            logger.debug(f"Ejecutando acción trigger para página {numero_pagina}...")
            accion_trigger()
        
        logger.debug(f"Respuesta API específica para página {numero_pagina} recibida.")
        response = response_info.value
        datos_api = response.json()

        if not api_handler.validar_respuesta_api(datos_api, logger):
            logger.error(f"Respuesta API inválida para página {numero_pagina}.")
            return False, {}, []

        metadata = api_handler.extraer_metadata_paginacion(datos_api, logger)
        resultados = api_handler.extraer_resultados(datos_api, logger)
        
        logger.info(f"Página {numero_pagina} procesada: {len(resultados)} compras encontradas.")
        
        if resultados:
            codigos_pagina = [r.get('codigo', r.get('id', 'N/A')) for r in resultados]
            logger.info(f"CÓDIGOS DE PÁGINA {numero_pagina}:")
            for i, codigo in enumerate(codigos_pagina, 1):
                logger.info(f"  [{i}] {codigo}")
        
        return True, metadata, resultados

    except Exception as e:
        if "Timeout" in str(e):
             logger.error(f"TIMEOUT en página {numero_pagina}. La API específica (page_number={numero_pagina}) no respondió a tiempo.")
        else:
            logger.error(f"ERROR crítico al scrapear página {numero_pagina}: {e}")
        return False, {}, []


# ===================================================================
# === ESTA FUNCIÓN ES LA QUE MODIFICAMOS ===
# ===================================================================
def run_scraper_listado(filtros: Optional[Dict] = None, max_paginas: Optional[int] = None):
    logger.info("="*60)
    logger.info("INICIANDO SCRAPER DE LISTADO - FASE 1 (Listado)")
    logger.info("="*60)
    logger.info(f"Filtros aplicados: {filtros or 'Por defecto'}")
    logger.info(f"Límite de páginas: {max_paginas or 'Sin límite'}")
    
    tiempo_inicio = time.time()
    total_compras_procesadas = 0
    paginas_procesadas = 0
    limite = max_paginas if max_paginas is not None else 0
    
    todas_las_compras = []
    
    with sync_playwright() as p:
        try:
            logger.info("Iniciando navegador (Playwright)...")
            browser = p.chromium.launch(headless=MODO_HEADLESS, slow_mo=500)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit(537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-CL'
            )
            page = context.new_page()
            
            page.set_extra_http_headers(HEADERS_API)

            # --- Procesar Página 1 (con page.goto) ---
            url_pagina_1 = construir_url_listado(1, filtros)
            logger.info(f"Navegando a página 1: {url_pagina_1}")
            
            accion_p1 = lambda: page.goto(url_pagina_1, wait_until='networkidle')
            exito, metadata, resultados = scrapear_pagina_listado(page, 1, accion_p1)
            
            if not exito:
                raise Exception("No se pudo obtener la página 1. Abortando.")
            
            total_resultados = metadata.get('resultCount', 0)
            total_paginas = metadata.get('pageCount', 0)
            total_compras_procesadas += len(resultados)
            todas_las_compras.extend(resultados)
            paginas_procesadas += 1
            
            logger.info(f"Total resultados encontrados: {total_resultados}")
            logger.info(f"Total páginas a scrapear: {total_paginas}")

            limite = total_paginas
            if max_paginas is not None and max_paginas < total_paginas:
                limite = max_paginas
            
            logger.info(f"Límite de páginas establecido en: {limite}")

            # --- Procesar Páginas Restantes (2 hasta N) (con page.click) ---
            for num_pagina in range(2, limite + 1):
                time.sleep(DELAY_ENTRE_PAGINAS) 
                
                logger.info(f"--- Procesando Página {num_pagina} ---")
                
                # --- INICIO DEL CAMBIO (Paginador) ---
                # ¡Usamos tu estrategia! Buscamos el botón "Siguiente Página"
                selector_aria_label = "Go to next page"
                
                logger.debug(f"Buscando selector de paginador: 'button[aria-label=\"{selector_aria_label}\"]'")
                selector_pagina_siguiente = page.locator(f'button[aria-label="{selector_aria_label}"]')
                # --- FIN DEL CAMBIO ---

                try:
                    # Esperar a que esté visible (máx 10 segundos)
                    selector_pagina_siguiente.wait_for(state='visible', timeout=10000)
                    logger.debug(f"Botón 'Siguiente Página' encontrado y visible.")
                
                except Exception as e:
                    # Si falla, registrar el error y saltar
                    logger.error(f"No se pudo encontrar el paginador 'Siguiente Página' (aria-label='{selector_aria_label}').")
                    logger.error(f"Error detallado: {e}")
                    logger.warning(f"Se omite la página {num_pagina} por NO encontrar el botón.")
                    # Si no encontramos el botón "siguiente", no podemos continuar.
                    break 
                
                # Si se encontró, definir la acción de clic
                accion_clic = lambda: selector_pagina_siguiente.click()

                # Pasar la acción de click al scraper (que esperará la API)
                exito, _, resultados_pagina = scrapear_pagina_listado(page, num_pagina, accion_clic)
                
                if exito:
                    total_compras_procesadas += len(resultados_pagina)
                    todas_las_compras.extend(resultados_pagina)
                    paginas_procesadas += 1
                else:
                    logger.warning(f"Se omite la página {num_pagina} por error de API.")
            
            # (El resto de la función para cerrar y guardar en BD sigue igual)
            context.close()
            browser.close()
            logger.info("Navegador (Playwright) cerrado.")
            
            if todas_las_compras:
                # (El resto de la lógica de duplicados y guardado en BD no cambia)
                logger.info(f"ANÁLISIS DE DUPLICADOS...")
                codigos_conteo = {}
                for compra in todas_las_compras:
                    codigo = compra.get('codigo', compra.get('id'))
                    if codigo:
                        codigos_conteo[codigo] = codigos_conteo.get(codigo, 0) + 1
                
                duplicados = {k: v for k, v in codigos_conteo.items() if v > 1}
                if duplicados:
                    logger.info(f"CÓDIGOS DUPLICADOS ENCONTRADOS: {len(duplicados)}")
                else:
                    logger.info("NO SE ENCONTRARON DUPLICADOS")
                
                compras_unicas = {}
                for compra in todas_las_compras:
                    codigo = compra.get('codigo', compra.get('id'))
                    if codigo and codigo not in compras_unicas:
                        compras_unicas[codigo] = compra
                
                lista_unicas = list(compras_unicas.values())
                logger.info(f"Compras únicas a guardar en BD: {len(lista_unicas)}")
                
                db_session = SessionLocal()
                try:
                    insertar_o_actualizar_licitaciones(db_session, lista_unicas)
                    logger.info("Guardado en BD completado exitosamente.")
                finally:
                    db_session.close()

        except Exception as e:
            logger.critical(f"FALLO EL PROCESO DE SCRAPING: {e}")
        finally:
            tiempo_total = time.time() - tiempo_inicio
            logger.info("="*60)
            logger.info("RESUMEN DE SCRAPING (Listado)")
            logger.info(f"Tiempo total: {tiempo_total:.2f} segundos")
            logger.info(f"Página procesada: {paginas_procesadas} / {limite if limite > 0 else (paginas_procesadas if paginas_procesadas > 0 else 'N/A')}")
            logger.info(f"Total compras procesadas: {total_compras_procesadas}")
            logger.info("="*60)
            

def scrape_ficha_detalle_api(page: Page, codigo_ca: str) -> Optional[Dict]:
    """
    Scrapea la Ficha Individual de una CA (el segundo tipo de scraping)
    utilizando el listener de la API (mucho más robusto que el HTML).
    
    Retorna un diccionario con los datos o None si falla.
    """
    
    # URL de la API que vamos a escuchar
    url_api_ficha = construir_url_api_ficha(codigo_ca)
    
    # URL de la página web que vamos a visitar (para triggerear la API)
    url_web_ficha = construir_url_ficha(codigo_ca)
    
    logger.info(f"[Fase 2] Scrapeando Ficha: {url_web_ficha}")

    try:
        # 1. Configurar el listener ANTES de navegar
        predicate = lambda response: (
            url_api_ficha in response.url and
            response.status == 200
        )

        with page.expect_response(predicate, timeout=TIMEOUT_REQUESTS * 1000) as response_info:
            # 2. Navegar a la página (esto dispara la llamada a la API)
            logger.debug(f"[{codigo_ca}] Navegando a la ficha web para triggerear la API...")
            page.goto(url_web_ficha, wait_until='networkidle')
        
        logger.debug(f"[{codigo_ca}] Respuesta API de Ficha recibida.")
        response = response_info.value
        datos_api_ficha = response.json()

        # 3. Validar y extraer el payload
        if 'success' not in datos_api_ficha or datos_api_ficha['success'] != 'OK':
            logger.warning(f"[{codigo_ca}] Respuesta API de Ficha sin 'success': 'OK'.")
            return None
        
        if 'payload' not in datos_api_ficha:
            logger.warning(f"[{codigo_ca}] Respuesta API de Ficha sin 'payload'.")
            return None

        payload = datos_api_ficha['payload']
        
        # 4. Mapear los datos que nos interesan
        datos_extraidos = {
            'descripcion': payload.get('descripcion'),
            'direccion_entrega': payload.get('direccion_entrega'),
            'fecha_cierre_p1': payload.get('fecha_cierre_primer_llamado'),
            'fecha_cierre_p2': payload.get('fecha_cierre_segundo_llamado'),
            
            # --- ¡ESTA ES LA LÍNEA CORREGIDA! ---
            'productos_solicitados': payload.get('productos_solicitados', [])
        }
        
        logger.info(f"[{codigo_ca}] Ficha procesada. Productos encontrados: {len(datos_extraidos['productos_solicitados'])}")
        return datos_extraidos

    except Exception as e:
        if "Timeout" in str(e):
             logger.error(f"[{codigo_ca}] TIMEOUT en Ficha Individual. La API no respondió a tiempo.")
        else:
            logger.error(f"[{codigo_ca}] ERROR crítico al scrapear Ficha Individual: {e}")
        return None
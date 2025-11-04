import sys
import time
from pathlib import Path

# --- INICIO DE LA CONFIGURACIÓN DEL PATH ---
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# --- FIN DE LA CONFIGURACIÓN DEL PATH ---

from playwright.sync_api import sync_playwright

from src.db.db_service import SessionLocal, obtener_candidatas_para_fase_2, actualizar_ca_con_fase_2
from src.scraper.scraper_service import scrape_ficha_detalle_api
from src.logic.score_engine import calcular_puntuacion_fase_2
from config.config import MODO_HEADLESS, TIMEOUT_REQUESTS

from src.utils.logger import configurar_logger
logger = configurar_logger('run_fase_2')


def main():
    logger.info("="*60)
    logger.info("INICIANDO SCRAPER DE DETALLE - FASE 2 (Ficha Individual)")
    logger.info("="*60)
    
    db_session = SessionLocal()
    
    # 1. Obtener CAs que necesitan ser procesadas
    candidatas = []
    try:
        candidatas = obtener_candidatas_para_fase_2(db_session)
    except Exception as e:
        logger.critical(f"Error al obtener candidatas de la BD: {e}")
        db_session.close()
        return
        
    if not candidatas:
        logger.info("No hay CAs nuevas para procesar en Fase 2. Terminando.")
        db_session.close()
        return

    # 2. Iniciar el navegador (solo una vez)
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

            procesadas = 0
            exitosas = 0
            
            # 3. Iterar sobre cada CA candidata
            for licitacion in candidatas:
                codigo_ca = licitacion.codigo_ca
                puntos_fase_1 = licitacion.puntuacion_final
                
                logger.info(f"--- Procesando CA: {codigo_ca} (Score Fase 1: {puntos_fase_1}) ---")
                
                # 4. Scrapear la ficha individual (usando la API)
                datos_ficha = scrape_ficha_detalle_api(page, codigo_ca)
                
                if datos_ficha is None:
                    logger.error(f"No se pudieron obtener datos de la ficha para {codigo_ca}. Omitiendo.")
                    continue
                
                # 5. Calcular puntuación de Fase 2
                # Convertimos el objeto SQLAlchemy 'licitacion' a un dict simple
                # (Asumimos que el scraper de Fase 1 guardó 'codigo' y 'nombre')
                ca_dict_fase_1 = {
                    'codigo': licitacion.codigo_ca,
                    'nombre': licitacion.nombre
                }
                
                puntos_fase_2 = calcular_puntuacion_fase_2(ca_dict_fase_1, datos_ficha)
                
                puntuacion_total = puntos_fase_1 + puntos_fase_2
                
                # 6. Actualizar la BD
                actualizar_ca_con_fase_2(db_session, codigo_ca, datos_ficha, puntuacion_total)
                
                exitosas += 1
                procesadas += 1
                
                # Pausa breve para no saturar
                time.sleep(1) 
    
            context.close()
            browser.close()
            logger.info("Navegador (Playwright) cerrado.")

        except Exception as e:
            logger.critical(f"FALLO EL PROCESO DE SCRAPING FASE 2: {e}")
        finally:
            logger.info("="*60)
            logger.info("RESUMEN DE SCRAPING (Fase 2)")
            logger.info(f"CAs para procesar: {len(candidatas)}")
            logger.info(f"Procesadas exitosamente: {exitosas}")
            logger.info("="*60)
            db_session.close()


if __name__ == "__main__":
    main()
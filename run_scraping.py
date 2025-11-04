import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# --- INICIO DE LA CONFIGURACIÓN DEL PATH ---
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# --- FIN DE LA CONFIGURACIÓN DEL PATH ---

from src.scraper.scraper_service import run_scraper_listado

def main():
    """
    Punto de entrada para ejecutar el scraping.
    """
    
    # --- EJEMPLO DE FILTROS ---
    # Queremos scrapear solo las compras de los últimos 5 días
    
    # 1. Definir el rango de fechas
    fecha_hoy = datetime.now()
    fecha_hace_2_dias = fecha_hoy - timedelta(days=5)
    
    date_to = fecha_hoy.strftime('%Y-%m-%d')
    date_from = fecha_hace_2_dias.strftime('%Y-%m-%d')

    # 2. Crear el diccionario de filtros 
    filtros_personalizados = {
        'date_from': date_from,
        'date_to': date_to
    }
    
    # 3. Definir un límite de páginas (para no demorar mucho en la prueba)
    limite_paginas = 5 # Scrapear solo 5 páginas

    print(f"Iniciando scraping... Rango: {date_from} a {date_to}")
    print(f"Límite de páginas: {limite_paginas}")
    
    # 4. Ejecutar el servicio
    run_scraper_listado(
        filtros=filtros_personalizados,
        max_paginas=limite_paginas
    )
    
    print("Proceso de scraping de listado finalizado.")


if __name__ == "__main__":
    main()
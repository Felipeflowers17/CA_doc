# --- Reglas Numéricas del Scoring ---
# (Según la especificación en 'score_config.py') 

# --- Puntuaciones Fase 1 (Listado) ---
PUNTOS_ORGANISMO = 5
PUNTOS_SEGUNDO_LLAMADO = 4
PUNTOS_KEYWORD_TITULO = 2
PUNTOS_ALERTA_URGENCIA = 3

# --- Puntuaciones Fase 2 (Ficha Individual) ---
PUNTOS_KEYWORD_PRODUCTO = 5

# --- Umbrales (Puntos de Corte) ---
UMBRAL_FASE_2 = 5  # Puntos mínimos para pasar a Fase 2 (Scraping detallado) 
UMBRAL_FINAL = 9   # Puntos mínimos para ser "Relevante" (Hoja 2) 
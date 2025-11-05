# --- Reglas Numéricas del Scoring --- 

# --- Puntuaciones Fase 1 (Listado) ---
PUNTOS_ORGANISMO = 5 #si es organismo prioritario suma 5 puntos 
PUNTOS_SEGUNDO_LLAMADO = 4 #si es segundo llamdo como estado suma 4 puntos
PUNTOS_KEYWORD_TITULO = 2 #suma 2 puntos por cada keyword encontrada en el titulo
PUNTOS_ALERTA_URGENCIA = 3 

# --- Puntuaciones Fase 2 (Ficha Individual) ---
PUNTOS_KEYWORD_PRODUCTO = 5 #suma 5 puntos en caso de haber keywords en el listado de productos solicitados 

# --- Umbrales  ---
UMBRAL_FASE_2 = 5  # Puntos mínimos para pasar a Fase 2 (Scraping detallado) 
UMBRAL_FINAL = 9   # Puntos mínimos para ser "Relevante" (Hoja 2) 
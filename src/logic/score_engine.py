import datetime
from typing import Dict, Any

# --- ¡NUEVA IMPORTACIÓN! ---
from src.utils.logger import configurar_logger
# ---

# Importar las reglas y los datos
from config.keywords_data import ORGANISMOS_PRIORITARIOS, KEYWORDS_TITULO
from config.score_config import (
    PUNTOS_ORGANISMO, 
    PUNTOS_SEGUNDO_LLAMADO, 
    PUNTOS_KEYWORD_TITULO, 
    PUNTOS_ALERTA_URGENCIA
)

# --- Configurar el logger para este módulo ---
logger = configurar_logger('score_engine')
# ---

# --- ¡MEJORA DE ROBUSTEZ! ---
# Convertimos las listas a minúsculas/mayúsculas UNA SOLA VEZ al iniciar.
# Esto evita errores si el usuario escribe "Ferreteria" en lugar de "ferreteria".
# Usamos 'set' para búsquedas más rápidas.
LISTA_ORGANISMOS = {org.upper() for org in ORGANISMOS_PRIORITARIOS}
LISTA_KEYWORDS_TITULO = {kw.lower() for kw in KEYWORDS_TITULO}
# ---


def calcular_puntuacion_fase_1(ca: Dict[str, Any]) -> int:
    """
    Calcula la puntuación de Fase 1 (Listado Básico) para una CA.
    La CA debe ser un diccionario (como el JSON recibido de la API).
    
    NOTA: El criterio "Alerta Urgencia" ha sido deshabilitado temporalmente.
    """
    
    puntos = 0
    codigo_ca = ca.get('codigo', 'N/A')
    
    # 1. Preparar datos (limpiar y normalizar)
    nombre_ca = str(ca.get('nombre', '')).lower()
    organismo_ca = str(ca.get('organismo', '')).upper() # Normalizamos a mayúsculas
    estado_texto = str(ca.get('estado', '')).lower()
    
    # --- Iniciamos log de puntuación ---
    logger.debug(f"--- Puntuando CA: {codigo_ca} ({nombre_ca[:30]}...) ---")
    
    # --- Aplicar Lógica de Puntuación ---

    # 1. Criterio: Organismo Prioritario (+5)
    if organismo_ca in LISTA_ORGANISMOS:
        puntos += PUNTOS_ORGANISMO
        logger.debug(f"[{codigo_ca}] +{PUNTOS_ORGANISMO} pts. Organismo: {organismo_ca}")

    # 2. Criterio: Segundo Llamado (+4)
    if "segundo llamado" in estado_texto:
        puntos += PUNTOS_SEGUNDO_LLAMADO
        logger.debug(f"[{codigo_ca}] +{PUNTOS_SEGUNDO_LLAMADO} pts. Segundo Llamado.")

    # 3. Criterio: Keywords en Título (+2 por cada una)
    for keyword in LISTA_KEYWORDS_TITULO:
        if keyword in nombre_ca:
            puntos += PUNTOS_KEYWORD_TITULO
            logger.debug(f"[{codigo_ca}] +{PUNTOS_KEYWORD_TITULO} pts. Keyword Título: '{keyword}'")

    # 4. Criterio: Alerta Urgencia (+3)
    # --- DESHABILITADO ---
    # (Se eliminó la lógica de proveedores y fechas)
    
    logger.debug(f"[{codigo_ca}] Puntuación Fase 1 Total: {puntos}")
    return puntos
import datetime
from typing import Dict, Any

from src.utils.logger import configurar_logger

# Importar las reglas y los datos
from config.keywords_data import KEYWORDS_PRODUCTOS_ALTO_VALOR, ORGANISMOS_PRIORITARIOS, KEYWORDS_TITULO
from config.score_config import (
    PUNTOS_KEYWORD_PRODUCTO,
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
LISTA_KEYWORDS_PRODUCTOS = {kw.lower() for kw in KEYWORDS_PRODUCTOS_ALTO_VALOR}
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

def calcular_puntuacion_fase_2(ca: Dict[str, Any], datos_ficha: Dict) -> int:
    """
    Calcula la puntuación de Fase 2 (Ficha Individual).
    Esta puntuación se SUMA a la de la Fase 1.
    """
    
    puntos_fase_2 = 0
    codigo_ca = ca.get('codigo', 'N/A')
    
    # Extraer la lista de productos de los datos de la ficha
    productos_solicitados = datos_ficha.get('productos_solicitados', [])
    if not productos_solicitados:
        logger.debug(f"[{codigo_ca}] No se encontraron productos para puntuar en Fase 2.")
        return 0
        
    logger.debug(f"[{codigo_ca}] Puntuando Fase 2 (encontrados {len(productos_solicitados)} productos)...")
    
    # 1. Criterio: Keywords en Productos (+5 por cada producto clave)
    for producto in productos_solicitados:
        # Asumimos que el producto es un dict con una key 'nombre'
        nombre_producto = str(producto.get('nombre', '')).lower()
        
        if not nombre_producto:
            continue
            
        for keyword in LISTA_KEYWORDS_PRODUCTOS:
            if keyword in nombre_producto:
                puntos_fase_2 += PUNTOS_KEYWORD_PRODUCTO
                logger.debug(f"[{codigo_ca}] +{PUNTOS_KEYWORD_PRODUCTO} pts. Keyword Producto: '{keyword}' en '{nombre_producto}'")
                # Importante: rompemos el bucle interno para no sumar
                # puntos varias veces por el mismo producto si tiene
                # múltiples keywords (ej. "niple codo de tubo")
                break 

    logger.debug(f"[{codigo_ca}] Puntuación Fase 2 Total: {puntos_fase_2}")
    return puntos_fase_2
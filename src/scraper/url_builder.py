from typing import Dict, Optional
from config.config import URL_BASE_WEB, URL_BASE_API # <-- Actualizado

def construir_url_listado(numero_pagina: int = 1, filtros: Optional[Dict] = None):
    """
    Construye la URL para el listado de compras ágiles.
    
    Args:
        numero_pagina: El número de página a solicitar.
        filtros: Un diccionario con los filtros a aplicar (ej: date_from, date_to).
    
    Returns:
        La URL completa como string.
    """
    
    parametros = {
        'status': 2,            # Estado: Publicadas
        'order_by': 'recent',   # Orden: Más recientes
        'page_number': numero_pagina
    }
    
    if filtros:
        parametros.update(filtros)
        
    if 'region' not in parametros:
        parametros['region'] = 'all'

    string_parametros = '&'.join([f"{k}={v}" for k, v in parametros.items()])
    
    return f"{URL_BASE_WEB}/compra-agil?{string_parametros}"

def construir_url_ficha(codigo_compra: str):
    """
    Construye la URL para la ficha individual de una compra (página web).
    """
    return f"{URL_BASE_WEB}/ficha?code={codigo_compra}"

def construir_url_api_ficha(codigo_compra: str):
    """
    Construye la URL para la API de la ficha individual.
    """
    return f"{URL_BASE_API}/compra-agil?action=ficha&code={codigo_compra}"
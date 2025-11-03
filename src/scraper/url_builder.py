from typing import Dict, Optional
from config.config import URL_BASE_WEB # Importamos la URL desde config

def construir_url_listado(numero_pagina: int = 1, filtros: Optional[Dict] = None):
    """
    Construye la URL para el listado de compras ágiles.
    
    Args:
        numero_pagina: El número de página a solicitar.
        filtros: Un diccionario con los filtros a aplicar (ej: date_from, date_to).
    
    Returns:
        La URL completa como string.
    """
    
    # Parámetros base que siempre queremos
    parametros = {
        'status': 2,            # Estado: Publicadas
        'order_by': 'recent',   # Orden: Más recientes
        'page_number': numero_pagina
    }
    
    # Si el usuario mandó filtros, los agregamos
    if filtros:
        parametros.update(filtros)
        
    # Si no se especificó región en los filtros, ponemos 'all' por defecto
    if 'region' not in parametros:
        parametros['region'] = 'all'

    # Construir el string de parámetros (ej: "status=2&order_by=recent&...")
    string_parametros = '&'.join([f"{k}={v}" for k, v in parametros.items()])
    
    return f"{URL_BASE_WEB}/compra-agil?{string_parametros}"

def construir_url_ficha(codigo_compra: str):
    """
    Construye la URL para la ficha individual de una compra.
    """
    return f"{URL_BASE_WEB}/ficha?code={codigo_compra}"
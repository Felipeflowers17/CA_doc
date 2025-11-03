import logging
import sys
from pathlib import Path

# Apuntar a la carpeta 'data/logs' 
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True) # Asegurarse de que exista

FORMATO_LOG = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
FORMATO_FECHA_LOG = '%Y-%m-%d %H:%M:%S'

def configurar_logger(nombre_modulo, nombre_archivo_log="proyecto_ca.log"):
    """
    Configura un logger para un módulo específico.
    Todos los logs irán al mismo archivo.
    """
    logger = logging.getLogger(nombre_modulo)
    logger.setLevel(logging.DEBUG) # Nivel de log 
    logger.propagate = False # Evita que los logs se dupliquen

    # Si ya tiene handlers, no agregar más
    if logger.handlers:
        return logger

    # 1. Handler para Consola (StreamHandler)
    handler_consola = logging.StreamHandler(sys.stdout)
    handler_consola.setLevel(logging.INFO) # Mostrar solo INFO y superior en consola
    handler_consola.setFormatter(logging.Formatter(FORMATO_LOG, FORMATO_FECHA_LOG))
    logger.addHandler(handler_consola)

    # 2. Handler para Archivo (FileHandler)
    ruta_archivo = LOG_DIR / nombre_archivo_log
    handler_archivo = logging.FileHandler(ruta_archivo, encoding='utf-8')
    handler_archivo.setLevel(logging.DEBUG) # Guardar todo (DEBUG) en el archivo
    handler_archivo.setFormatter(logging.Formatter(FORMATO_LOG, FORMATO_FECHA_LOG))
    logger.addHandler(handler_archivo)

    return logger
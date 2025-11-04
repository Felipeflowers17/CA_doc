import pandas as pd
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime

# Importar el logger
from src.utils.logger import configurar_logger
logger = configurar_logger('excel_service')

# Importar las funciones de la BD (las mismas que usa la GUI)
from src.db.db_service import (
    obtener_datos_tab1_candidatas,
    obtener_datos_tab2_relevantes,
    obtener_datos_tab3_seguimiento
)

# Definir la carpeta de salida (como en tu plan)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
EXPORTS_DIR = BASE_DIR / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True) # Asegurarse de que exista

# Definir las columnas que queremos en el Excel
# (Pueden ser las mismas o diferentes de la GUI)
COLUMNAS_EXCEL = [
    "puntuacion_final", "codigo_ca", "nombre", "estado_ca_texto", 
    "monto_clp", "fecha_cierre", "proveedores_cotizando", "descripcion", 
    "direccion_entrega", "productos_solicitados"
]

def _convertir_objetos_a_dataframe(data_list: list) -> pd.DataFrame:
    """
    Convierte una lista de objetos CaLicitacion a un DataFrame de Pandas,
    seleccionando y formateando las columnas.
    """
    # Convertir la lista de objetos SQLAlchemy a una lista de diccionarios
    data_dicts = []
    for licitacion in data_list:
        # Creamos un diccionario solo con las columnas deseadas
        fila = {col: getattr(licitacion, col, None) for col in COLUMNAS_EXCEL}
        data_dicts.append(fila)

    if not data_dicts:
        # Si no hay datos, crear un DF vacío con las columnas
        return pd.DataFrame(columns=COLUMNAS_EXCEL)

    # Crear el DataFrame
    df = pd.DataFrame(data_dicts)
    
    # --- Formateo y Limpieza (opcional pero recomendado) ---
    
    # 1. Formatear Fecha (quitar zona horaria para Excel)
    if 'fecha_cierre' in df.columns:
        df['fecha_cierre'] = pd.to_datetime(df['fecha_cierre']).dt.tz_localize(None).dt.strftime('%Y-%m-%d %H:%M')
        
    # 2. Convertir JSON de productos a un string legible
    if 'productos_solicitados' in df.columns:
        def format_productos(productos_json):
            if not isinstance(productos_json, list):
                return ""
            try:
                # Extraer solo el nombre de cada producto
                nombres = [p.get('nombre', 'N/A') for p in productos_json]
                return "; ".join(nombres) # Separar por punto y coma
            except Exception:
                return str(productos_json) # Si falla, mostrar el JSON crudo
        
        df['productos_solicitados'] = df['productos_solicitados'].apply(format_productos)

    # 3. Renombrar columnas para ser más amigables
    df.rename(columns={
        "puntuacion_final": "Puntuación",
        "codigo_ca": "Código",
        "nombre": "Nombre",
        "estado_ca_texto": "Estado",
        "monto_clp": "Monto (CLP)",
        "fecha_cierre": "Fecha Cierre",
        "proveedores_cotizando": "Proveedores",
        "descripcion": "Descripción",
        "direccion_entrega": "Dirección Entrega",
        "productos_solicitados": "Productos Solicitados"
    }, inplace=True)

    return df


def generar_reporte_excel(session: Session) -> str:
    """
    Función principal: Consulta la BD para las 3 hojas,
    las convierte a DataFrames y las guarda en un archivo Excel.
    
    Retorna la ruta del archivo generado.
    """
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"Reporte_CA_{timestamp}.xlsx"
    ruta_salida = EXPORTS_DIR / nombre_archivo
    
    logger.info(f"Iniciando generación de Reporte Excel: {nombre_archivo}")

    try:
        # 1. Obtener los datos para cada hoja
        logger.debug("Obteniendo datos de Hoja 1 (Candidatas)...")
        datos_h1 = obtener_datos_tab1_candidatas(session)
        
        logger.debug("Obteniendo datos de Hoja 2 (Relevantes)...")
        datos_h2 = obtener_datos_tab2_relevantes(session)
        
        logger.debug("Obteniendo datos de Hoja 3 (Seguimiento)...")
        datos_h3 = obtener_datos_tab3_seguimiento(session)

        # 2. Convertir a DataFrames
        df_h1 = _convertir_objetos_a_dataframe(datos_h1)
        df_h2 = _convertir_objetos_a_dataframe(datos_h2)
        df_h3 = _convertir_objetos_a_dataframe(datos_h3)
        
        # 3. Escribir en el archivo Excel Multi-Hoja
        with pd.ExcelWriter(ruta_salida, engine='openpyxl') as writer:
            df_h1.to_excel(writer, sheet_name="CAs Candidatas", index=False)
            df_h2.to_excel(writer, sheet_name="CAs Relevantes", index=False)
            df_h3.to_excel(writer, sheet_name="CAs en Seguimiento", index=False)
            
            # (Opcional: auto-ajustar ancho de columnas)
            
        logger.info(f"Reporte Excel generado exitosamente en: {ruta_salida}")
        return str(ruta_salida)

    except Exception as e:
        logger.error(f"Error al generar el reporte Excel: {e}")
        raise # Propagar el error para que la GUI lo muestre
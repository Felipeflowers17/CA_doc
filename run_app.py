import sys
from pathlib import Path

# --- CONFIGURACIÓN DEL PATH (La parte importante) ---
# 1. Obtener la ruta de la carpeta raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent
# 2. Obtener la ruta de la carpeta 'src'
SRC_DIR = BASE_DIR / 'src'

# 3. Añadir 'src' al path de Python para que encuentre los módulos
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# --- FIN DE LA CONFIGURACIÓN ---


# 4. Ahora que el path está arreglado, importamos la GUI
# (Importamos la función, no el archivo)
from src.gui.gui_main import run_gui

# 5. Ejecutamos la aplicación
if __name__ == "__main__":
    print("Lanzando aplicación...")
    run_gui()
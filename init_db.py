import sys
from pathlib import Path

# --- INICIO DE LA CONFIGURACIÓN DEL PATH ---
# Esto es crucial para que Python encuentre tu carpeta 'src'
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / 'src'

# Añadir 'src' al path de Python
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# --- FIN DE LA CONFIGURACIÓN DEL PATH ---


# IMPORTACIÓN CORRECTA:
# Importamos 'db.db_service' (Python busca en 'src/db/db_service.py')
from src.db.db_service import init_db

if __name__ == "__main__":
    print("Intentando conectar y crear tablas...")
    
    # Esta función llama a Base.metadata.create_all()
    # que está definida en db_service.py
    init_db()
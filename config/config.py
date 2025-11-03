import os
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables de entorno desde el archivo .env
# Apuntamos a la carpeta raíz del proyecto para encontrar .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- Configuración de Base de Datos (PostgreSQL) ---
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ca_monitor")

# URL de conexión para SQLAlchemy
# Formato: "postgresql://usuario:contraseña@host:puerto/nombre_bd"
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# --- Configuración de Scraping ---
URL_BASE_WEB = "https://buscador.mercadopublico.cl"

# Tiempos de espera y delays (en segundos)
TIMEOUT_REQUESTS = 30  # 30 segundos de espera máxima por página
DELAY_ENTRE_PAGINAS = 2 # 2 segundos de pausa entre cada página

# Modo Headless (True = no se ve el navegador, False = se ve el navegador)
MODO_HEADLESS = os.getenv('HEADLESS', 'True').lower() == 'true'
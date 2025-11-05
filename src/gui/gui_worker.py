from PySide6.QtCore import QObject, Signal, QRunnable
from typing import Callable, Any

from src.utils.logger import configurar_logger
logger = configurar_logger('gui_worker')

from src.db.db_service import SessionLocal 

class WorkerSignals(QObject):
    """
    Define las señales disponibles para un hilo trabajador.
    """
    finished = Signal()
    error = Signal(Exception)
    result = Signal(object)
    progress = Signal(str)

class Worker(QRunnable):
    """
    Worker que usa QRunnable, diseñado para ejecutarse en el QThreadPool global.
    """
    
    def __init__(self, task: Callable[..., Any], needs_progress_signal: bool, *args, **kwargs):
        """
        Args:
            task: La función pesada que se ejecutará.
            needs_progress_signal: bool que le dice al worker si debe
                                 inyectar la señal de progreso como segundo argumento.
            *args, **kwargs: Argumentos para pasar a la 'task'.
        """
        super().__init__()
        self.task = task
        self.needs_progress_signal = needs_progress_signal
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals() 

    def run(self):
        """
        El método que se ejecuta en el hilo secundario.
        """
        logger.debug(f"Hilo (QRunnable) iniciando tarea: {self.task.__name__}")
        
        db_session = None
        try:
            db_session = SessionLocal()
            
            if self.needs_progress_signal:
                # La tarea (ej. etl_service) SÍ necesita la señal de progreso
                resultado = self.task(
                    db_session, 
                    self.signals.progress, # Argumento 2
                    *self.args, 
                    **self.kwargs
                )
            else:
                # La tarea (ej. obtener_datos_tab1) NO necesita la señal
                resultado = self.task(
                    db_session, 
                    *self.args, 
                    **self.kwargs
                )
            
            if resultado is not None:
                self.signals.result.emit(resultado)
                
        except Exception as e:
            logger.error(f"Error en el hilo (QRunnable): {e}")
            self.signals.error.emit(e)
        finally:
            if db_session:
                db_session.close()
                
            self.signals.finished.emit()
            logger.debug(f"Hilo (QRunnable) finalizó tarea: {self.task.__name__}")
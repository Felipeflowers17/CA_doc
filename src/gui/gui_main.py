import sys
import webbrowser 
from pathlib import Path
from typing import Callable, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableView, QPushButton, QAbstractItemView, QHeaderView,
    QMenu, QMessageBox, QLineEdit, QStatusBar
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QCursor, QColor
from PySide6.QtCore import Qt, QModelIndex, QThreadPool, Slot

# Importar el logger
from src.utils.logger import configurar_logger
logger = configurar_logger('gui_main')

# --- Importar funciones de la BD ---
from src.db.db_service import (
    obtener_datos_tab1_candidatas,
    obtener_datos_tab2_relevantes,
    obtener_datos_tab3_seguimiento,
    obtener_datos_tab4_ofertadas, # <-- ¡NUEVO!
    gestionar_favorito, 
    gestionar_ofertada, # <-- ¡NUEVO!
    eliminar_ca_definitivamente
)
# --- Importar URL builder ---
from src.scraper.url_builder import construir_url_ficha
# --- Importar Excel Service ---
import os
from src.logic.excel_service import generar_reporte_excel
# --- Importar Worker ---
from src.gui.gui_worker import Worker
# --- Importar Diálogo ---
from src.gui.gui_scraping_dialog import ScrapingDialog 
from src.logic.etl_service import run_full_etl_process
# ---

# (Definiciones de Columnas se quedan igual)
COLUMN_HEADERS = [
    "Score", "Código CA", "Nombre", "Estado", "Monto (CLP)", 
    "Cierre", "Proveedores", "ID Interno"
]
COL_INDEX_CODIGO_CA = 1
COL_INDEX_NOMBRE = 2
COL_INDEX_CA_ID = 7

# --- ¡NUEVOS COLORES! ---
COLOR_FAVORITO = QColor("#EFFF8A")
COLOR_OFERTADA = QColor("#85D9FF")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Monitor de Compras Ágiles (CA)")
        self.setGeometry(100, 100, 1200, 700) 
        
        self.thread_pool = QThreadPool.globalInstance()
        self.is_task_running = False 
        self.running_workers = []
        self.last_error = None
        self.last_export_path = None
        
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Panel de Botones (Global) ---
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        self.scraping_button = QPushButton("Iniciar Nuevo Scraping...")
        self.scraping_button.setFixedHeight(40)
        self.scraping_button.setStyleSheet("background-color: #2a628f; color: white;")
        button_layout.addWidget(self.scraping_button)
        self.refresh_button = QPushButton("Refrescar Datos (BD)")
        self.refresh_button.setFixedHeight(40)
        button_layout.addWidget(self.refresh_button)
        self.export_button = QPushButton("Exportar Reporte Excel")
        self.export_button.setFixedHeight(40)
        button_layout.addWidget(self.export_button)
        button_layout.addStretch() 
        
        # --- Sistema de Pestañas (QTabWidget) ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        # --- Pestaña 1: CAs Candidatas ---
        self.tab_candidatas = QWidget()
        self.tabs.addTab(self.tab_candidatas, "CAs Candidatas (Fase 1)")
        layout_candidatas = QVBoxLayout(self.tab_candidatas)
        self.search_tab1 = QLineEdit()
        self.search_tab1.setPlaceholderText("Filtrar por Código o Nombre...")
        layout_candidatas.addWidget(self.search_tab1)
        self.model_tab1 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.table_tab1 = self.crear_tabla_view(self.model_tab1)
        layout_candidatas.addWidget(self.table_tab1)
        self.table_tab1.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        # --- Pestaña 2: CAs Relevantes ---
        self.tab_relevantes = QWidget()
        self.tabs.addTab(self.tab_relevantes, "CAs Relevantes (Fase 2)")
        layout_relevantes = QVBoxLayout(self.tab_relevantes)
        self.search_tab2 = QLineEdit()
        self.search_tab2.setPlaceholderText("Filtrar por Código o Nombre...")
        layout_relevantes.addWidget(self.search_tab2)
        self.model_tab2 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.table_tab2 = self.crear_tabla_view(self.model_tab2)
        layout_relevantes.addWidget(self.table_tab2)
        self.table_tab2.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        # --- Pestaña 3: CAs en Seguimiento ---
        self.tab_seguimiento = QWidget()
        self.tabs.addTab(self.tab_seguimiento, "CAs en Seguimiento (Favoritos)")
        layout_seguimiento = QVBoxLayout(self.tab_seguimiento)
        self.search_tab3 = QLineEdit()
        self.search_tab3.setPlaceholderText("Filtrar por Código o Nombre...")
        layout_seguimiento.addWidget(self.search_tab3)
        self.model_tab3 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.table_tab3 = self.crear_tabla_view(self.model_tab3)
        layout_seguimiento.addWidget(self.table_tab3)
        self.table_tab3.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        
        # --- ¡NUEVA PESTAÑA 4! ---
        self.tab_ofertadas = QWidget()
        self.tabs.addTab(self.tab_ofertadas, "CAs Ofertadas")
        layout_ofertadas = QVBoxLayout(self.tab_ofertadas)
        self.search_tab4 = QLineEdit()
        self.search_tab4.setPlaceholderText("Filtrar por Código o Nombre...")
        layout_ofertadas.addWidget(self.search_tab4)
        self.model_tab4 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.table_tab4 = self.crear_tabla_view(self.model_tab4)
        layout_ofertadas.addWidget(self.table_tab4)
        self.table_tab4.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        
        # --- Barra de Estado ---
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Listo.")
        
        # --- Conectar señales (botones) ---
        self.scraping_button.clicked.connect(self.on_open_scraping_dialog) 
        self.export_button.clicked.connect(self.on_exportar_excel_thread) 
        self.refresh_button.clicked.connect(self.on_load_data_thread)
        # --- Conectar señales (barras de búsqueda) ---
        self.search_tab1.textChanged.connect(self.on_search_tab1_changed)
        self.search_tab2.textChanged.connect(self.on_search_tab2_changed)
        self.search_tab3.textChanged.connect(self.on_search_tab3_changed)
        self.search_tab4.textChanged.connect(self.on_search_tab4_changed)
        logger.info("Ventana principal (GUI) inicializada.")
        
        # --- Carga Inicial de Datos ---
        self.on_load_data_thread()


    @Slot(str)
    def on_progress_update(self, message: str):
        """Actualiza la barra de estado con un mensaje de progreso."""
        self.statusBar().showMessage(message)


    def start_task(
        self, 
        task: Callable, 
        on_result: Callable, 
        on_error: Callable, 
        on_finished: Callable, 
        on_progress: Callable = None, 
        task_args: tuple = (), 
        task_kwargs: dict = {}
    ):
        """
        Función genérica para iniciar una tarea pesada en el QThreadPool.
        """
        
        needs_progress = (on_progress is not None)
        worker = Worker(task, needs_progress, *task_args, **task_kwargs) 
        
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        
        if on_progress:
            worker.signals.progress.connect(on_progress)
            
        worker.signals.finished.connect(lambda: self.on_worker_finished(worker))
        self.running_workers.append(worker)
        self.thread_pool.start(worker)

    @Slot(Worker)
    def on_worker_finished(self, worker_to_remove: Worker):
        """
        Slot para limpiar la referencia del worker cuando termina.
        """
        logger.debug(f"Worker {worker_to_remove.task.__name__} terminado. Limpiando referencia.")
        try:
            self.running_workers.remove(worker_to_remove)
        except ValueError:
            logger.warning(f"No se pudo encontrar el worker en la lista para eliminar.")


    def set_ui_busy(self, busy: bool):
        """Activa/Desactiva la UI y muestra el cursor de espera."""
        self.is_task_running = busy 
        
        if busy:
            logger.debug("UI Bloqueada (Ocupada=True)")
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            self.refresh_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.scraping_button.setEnabled(False) 
            self.statusBar().showMessage("Ocupado. Por favor, espere...")
        else:
            logger.debug("UI Desbloqueada (Ocupada=False)")
            QApplication.restoreOverrideCursor()
            self.refresh_button.setEnabled(True)
            self.export_button.setEnabled(True)
            self.scraping_button.setEnabled(True) 
            self.statusBar().clearMessage()
    
    # --- Lógica de Scraping ---
    
    def on_open_scraping_dialog(self):
        """
        Abre el diálogo modal para iniciar un nuevo scraping.
        """
        if self.is_task_running:
            QMessageBox.warning(self, "Ocupado", 
                                "La aplicación ya está trabajando. Por favor, espere.")
            return

        dialog = ScrapingDialog(self)
        dialog.start_scraping.connect(self.on_start_full_scraping)
        dialog.exec() 

    @Slot(dict)
    def on_start_full_scraping(self, config: dict):
        """
        Slot: Se llama cuando el diálogo emite la señal 'start_scraping'.
        Inicia el hilo de scraping completo.
        """
        if self.is_task_running: # Doble chequeo
            return
            
        logger.info(f"Recibida configuración de scraping: {config}")
        
        self.set_ui_busy(True) # Bloquear UI
        
        self.start_task(
            task=run_full_etl_process,
            on_result=lambda: logger.info("Proceso ETL completo OK"),
            on_error=self.on_load_chain_error, 
            on_finished=self.on_load_tab1_finished, # Iniciar cadena de refresco
            on_progress=self.on_progress_update,
            task_args=(config,) 
        )

    # --- Lógica de Carga de Datos (Refrescar) ---
    
    def on_load_data_thread(self):
        """
        PUNTO DE ENTRADA para la cadena de carga de datos.
        """
        if self.is_task_running:
            logger.warning("Tareas ya están en ejecución. Ignorando nueva solicitud.")
            return
        self.set_ui_busy(True) 
        logger.info("Solicitud de refresco de datos (con hilos)...")
        self.start_task(
            task=obtener_datos_tab1_candidatas,
            on_result=lambda data: self.poblar_tabla(self.model_tab1, data),
            on_error=self.on_load_chain_error, 
            on_finished=self.on_load_tab1_finished,
            on_progress=None 
        )

    def on_load_tab1_finished(self):
        logger.debug("Hilo Tab 1 finalizado. Iniciando carga Tab 2...")
        self.start_task(
            task=obtener_datos_tab2_relevantes,
            on_result=lambda data: self.poblar_tabla(self.model_tab2, data),
            on_error=self.on_load_chain_error,
            on_finished=self.on_load_tab2_finished,
            on_progress=None 
        )

    def on_load_tab2_finished(self):
        logger.debug("Hilo Tab 2 finalizado. Iniciando carga Tab 3...")
        self.start_task(
            task=obtener_datos_tab3_seguimiento,
            on_result=lambda data: self.poblar_tabla(self.model_tab3, data),
            on_error=self.on_load_chain_error,
            on_finished=self.on_load_tab3_finished,
            on_progress=None 
        )

    def on_load_tab3_finished(self):
        """Slot: Se ejecuta cuando el hilo de la Tab 3 termina."""
        logger.debug("Hilo Tab 3 finalizado. Iniciando carga Tab 4...")
        self.start_task(
            task=obtener_datos_tab4_ofertadas,
            on_result=lambda data: self.poblar_tabla(self.model_tab4, data),
            on_error=self.on_load_chain_error,
            on_finished=self.on_load_tab4_finished, # Llama al nuevo final
            on_progress=None 
        )

    def on_load_tab4_finished(self):
        """Slot: Se ejecuta cuando el hilo de la Tab 4 (el último) termina."""
        logger.info("Carga de todas las tablas completada.")
        self.set_ui_busy(False) # Desbloquear la UI
        self.statusBar().showMessage("¡Datos refrescados exitosamente!", 5000) 

    def on_load_chain_error(self, error: Exception):
        """Manejador de error para la CADENA de carga."""
        logger.critical(f"Error en la cadena de carga: {error}")
        self.set_ui_busy(False) 
        self.statusBar().showMessage(f"Error en la carga: {error}", 5000)
        QMessageBox.critical(self, "Error de Carga", 
                             f"No se pudieron cargar todos los datos:\n{error}")
    
    # --- Tareas de Exportar Excel ---
    
    def on_exportar_excel_thread(self):
        if self.is_task_running:
            logger.warning("Tareas ya están en ejecución. Ignorando nueva solicitud.")
            return
        self.set_ui_busy(True) 
        logger.info("Solicitud de exportar Excel (con hilos)...")
        self.last_export_path = None
        self.last_error = None
        
        self.start_task(
            task=generar_reporte_excel,
            on_result=lambda path: setattr(self, 'last_export_path', path),
            on_error=lambda err: setattr(self, 'last_error', err),
            on_finished=self.on_export_excel_completed,
            on_progress=None 
        )

    def on_export_excel_completed(self):
        """Slot: Se ejecuta al finalizar el hilo de exportación."""
        self.set_ui_busy(False) 
        
        if self.last_error:
            self.statusBar().showMessage(f"Error al exportar: {self.last_error}", 5000)
            QMessageBox.critical(self, "Error de Exportación", 
                                 f"No se pudo generar el reporte:\n{self.last_error}")
        elif self.last_export_path:
            logger.info("Exportación a Excel finalizada.")
            ruta_corta = Path(self.last_export_path).name
            self.statusBar().showMessage(f"Reporte generado: {ruta_corta}", 5000)
            
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Exportación Exitosa")
            msg_box.setText(f"Reporte guardado exitosamente en:\n{self.last_export_path}")
            msg_box.addButton("Abrir Carpeta", QMessageBox.AcceptRole)
            msg_box.addButton("Cerrar", QMessageBox.RejectRole)
            ret = msg_box.exec()
            if ret == QMessageBox.AcceptRole:
                try:
                    os.startfile(Path(self.last_export_path).parent)
                except Exception as e:
                    logger.error(f"No se pudo abrir la carpeta de exportación: {e}")
        
        self.last_export_path = None
        self.last_error = None

    # (Función crear_tabla_view sin cambios)
    def crear_tabla_view(self, model: QStandardItemModel) -> QTableView:
        table_view = QTableView()
        table_view.setModel(model)
        table_view.setSortingEnabled(True)
        table_view.sortByColumn(0, Qt.DescendingOrder) 
        table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        table_view.setEditTriggers(QAbstractItemView.NoEditTriggers) 
        table_view.setSelectionBehavior(QAbstractItemView.SelectRows) 
        table_view.setSelectionMode(QAbstractItemView.SingleSelection) 
        table_view.setAlternatingRowColors(True)
        table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table_view.horizontalHeader().setSectionResizeMode(COL_INDEX_NOMBRE, QHeaderView.Stretch) 
        table_view.setColumnHidden(COL_INDEX_CA_ID, True)
        return table_view

    # --- ¡FUNCIÓN MODIFICADA! ---
    def poblar_tabla(self, model: QStandardItemModel, data: List):
        """Limpia y puebla un modelo de tabla con datos de CaLicitacion."""
        
        model.clear()
        model.setHorizontalHeaderLabels(COLUMN_HEADERS)

        for licitacion in data:
            # --- Lógica de Color (Tu sugerencia) ---
            color = None
            if licitacion.seguimiento: # Comprobar si existe el objeto
                if licitacion.seguimiento.es_ofertada:
                    color = COLOR_OFERTADA
                elif licitacion.seguimiento.es_favorito:
                    color = COLOR_FAVORITO
            
            # --- Crear Items ---
            score_item = QStandardItem()
            score_val = licitacion.puntuacion_final or 0
            score_item.setData(score_val, Qt.DisplayRole) 
            
            codigo = QStandardItem(licitacion.codigo_ca)
            nombre = QStandardItem(licitacion.nombre)
            estado = QStandardItem(licitacion.estado_ca_texto or "N/A")
            
            monto_item = QStandardItem()
            monto_val = licitacion.monto_clp or 0
            monto_item.setData(int(monto_val), Qt.DisplayRole) 
            
            try:
                cierre = licitacion.fecha_cierre.strftime('%Y-%m-%d %H:%M')
            except Exception:
                cierre = "N/A"
            
            prov_item = QStandardItem()
            prov_val = licitacion.proveedores_cotizando or 0
            prov_item.setData(prov_val, Qt.DisplayRole) 
            
            ca_id = QStandardItem(str(licitacion.ca_id)) 

            row_items = [
                score_item, codigo, nombre, estado,
                monto_item, QStandardItem(cierre),
                prov_item, ca_id
            ]
            
            # --- Aplicar Color a la Fila ---
            if color:
                for item in row_items:
                    item.setBackground(color)
            
            model.appendRow(row_items)

    # --- ¡FUNCIÓN MODIFICADA! ---
    def mostrar_menu_contextual(self, position):
        active_tab_index = self.tabs.currentIndex()
        if active_tab_index == 0:
            table_view = self.table_tab1
        elif active_tab_index == 1:
            table_view = self.table_tab2
        elif active_tab_index == 2:
            table_view = self.table_tab3
        elif active_tab_index == 3: # <-- ¡NUEVO!
            table_view = self.table_tab4
        else:
            return
            
        index: QModelIndex = table_view.indexAt(position)
        if not index.isValid():
            return 
            
        model = table_view.model()
        row = index.row()
        try:
            ca_id_item = model.item(row, COL_INDEX_CA_ID)
            ca_id = int(ca_id_item.text())
            codigo_ca_item = model.item(row, COL_INDEX_CODIGO_CA)
            codigo_ca = codigo_ca_item.text()
        except Exception as e:
            logger.error(f"Error al obtener ID de la fila {row}: {e}")
            return
            
        logger.debug(f"Menú contextual para CA ID: {ca_id} (Código: {codigo_ca})")

        menu = QMenu()
        
        accion_marcar_fav = QAction("1. Marcar como Favorito", self)
        accion_marcar_fav.triggered.connect(lambda: self.on_marcar_favorito(ca_id))
        menu.addAction(accion_marcar_fav)

        accion_eliminar_seg = QAction("2. Eliminar Seguimiento", self)
        accion_eliminar_seg.triggered.connect(lambda: self.on_eliminar_seguimiento(ca_id))
        menu.addAction(accion_eliminar_seg)
        
        menu.addSeparator()

        # --- ¡NUEVA ACCIÓN! ---
        accion_marcar_ofertada = QAction("3. Marcar como Ofertada", self)
        accion_marcar_ofertada.triggered.connect(lambda: self.on_marcar_ofertada(ca_id))
        menu.addAction(accion_marcar_ofertada)
        
        accion_eliminar_ofertada = QAction("4. Quitar marca de Ofertada", self)
        accion_eliminar_ofertada.triggered.connect(lambda: self.on_quitar_ofertada(ca_id))
        menu.addAction(accion_eliminar_ofertada)
        
        menu.addSeparator()

        accion_eliminar_def = QAction("5. Eliminar Definitivamente (BD)", self)
        accion_eliminar_def.triggered.connect(lambda: self.on_eliminar_definitivo(ca_id))
        menu.addAction(accion_eliminar_def)
        
        menu.addSeparator()

        accion_ver_web = QAction("6. Ver Ficha Web", self)
        accion_ver_web.triggered.connect(lambda: self.on_ver_ficha_web(codigo_ca))
        menu.addAction(accion_ver_web)

        menu.exec_(table_view.viewport().mapToGlobal(position))
    
    # --- ¡NUEVAS FUNCIONES DE ACCIÓN! ---
    
    def on_marcar_ofertada(self, ca_id: int):
        logger.info(f"Acción: Marcar como ofertada ID: {ca_id}")
        if self.is_task_running:
            return
        self.set_ui_busy(True) 
        self.start_task(
            task=gestionar_ofertada,
            on_result=lambda: logger.debug("Marcado como ofertada OK"),
            on_error=self.on_load_chain_error, 
            on_finished=self.on_load_data_thread, # Refrescar todo
            on_progress=None,
            task_args=(ca_id, True) 
        )

    def on_quitar_ofertada(self, ca_id: int):
        logger.info(f"Acción: Quitar marca de ofertada ID: {ca_id}")
        if self.is_task_running:
            return
        self.set_ui_busy(True) 
        self.start_task(
            task=gestionar_ofertada,
            on_result=lambda: logger.debug("Quitado marca de ofertada OK"),
            on_error=self.on_load_chain_error, 
            on_finished=self.on_load_data_thread, # Refrescar todo
            on_progress=None,
            task_args=(ca_id, False) 
        )

    # (Funciones on_marcar_favorito, on_eliminar_seguimiento, etc., sin cambios)
    
    def on_marcar_favorito(self, ca_id: int):
        logger.info(f"Acción: Marcar como favorito ID: {ca_id}")
        if self.is_task_running:
            return
        self.set_ui_busy(True) 
        self.start_task(
            task=gestionar_favorito,
            on_result=lambda: logger.debug("Marcado como favorito OK"),
            on_error=self.on_load_chain_error, 
            
            # --- ¡LA CORRECCIÓN! ---
            # Llamar al primer eslabón de la cadena, no al punto de entrada.
            on_finished=self.on_load_tab1_finished, 
            
            on_progress=None,
            task_args=(ca_id, True) 
        )

    def on_eliminar_seguimiento(self, ca_id: int):
        logger.info(f"Acción: Eliminar seguimiento ID: {ca_id}")
        if self.is_task_running:
            return
        self.set_ui_busy(True) 
        self.start_task(
            task=gestionar_favorito,
            on_result=lambda: logger.debug("Eliminado seguimiento OK"),
            on_error=self.on_load_chain_error, 
            
            # --- ¡LA CORRECCIÓN! ---
            on_finished=self.on_load_tab1_finished,
            
            on_progress=None,
            task_args=(ca_id, False)
        )

    def on_eliminar_definitivo(self, ca_id: int):
        logger.info(f"Acción: Eliminar definitivamente ID: {ca_id}")
        if self.is_task_running:
            return
        confirm = QMessageBox.warning(
            self, "Confirmación de Eliminación",
            "¿Estás seguro de que quieres eliminar esta CA permanentemente?\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No 
        )
        if confirm == QMessageBox.Yes:
            logger.info(f"Confirmado: Eliminando ID: {ca_id}")
            self.set_ui_busy(True) 
            self.start_task(
                task=eliminar_ca_definitivamente,
                on_result=lambda: logger.debug("Eliminación OK"),
                on_error=self.on_load_chain_error,
                
                # --- ¡LA CORRECCIÓN! ---
                on_finished=self.on_load_tab1_finished, 
                
                on_progress=None,
                task_args=(ca_id,) 
            )
        else:
            logger.info("Eliminación cancelada por el usuario.")
    def on_ver_ficha_web(self, codigo_ca: str):
        logger.info(f"Acción: Ver ficha web: {codigo_ca}")
        url = construir_url_ficha(codigo_ca)
        try:
            webbrowser.open_new_tab(url)
        except Exception as e:
            logger.error(f"No se pudo abrir el navegador: {e}")
            QMessageBox.warning(self, "Error al Abrir", 
                                f"No se pudo abrir el navegador para:\n{url}")
    
    # --- ¡NUEVA FUNCIÓN! ---
    @Slot(str)
    def on_search_tab4_changed(self, text: str):
        """Slot para filtrar la tabla 4."""
        self.filter_table_view(self.table_tab4, text)
        
    # (Funciones de filtro sin cambios)
    
    def on_search_tab1_changed(self, text: str):
        self.filter_table_view(self.table_tab1, text)

    def on_search_tab2_changed(self, text: str):
        self.filter_table_view(self.table_tab2, text)

    def on_search_tab3_changed(self, text: str):
        self.filter_table_view(self.table_tab3, text)

    def filter_table_view(self, table_view: QTableView, text: str):
        model = table_view.model()
        filter_text = text.lower()
        for row in range(model.rowCount()):
            try:
                codigo_ca = model.item(row, COL_INDEX_CODIGO_CA).text().lower()
                nombre = model.item(row, COL_INDEX_NOMBRE).text().lower()
            except AttributeError:
                continue
            if filter_text in codigo_ca or filter_text in nombre:
                table_view.setRowHidden(row, False)
            else:
                table_view.setRowHidden(row, True)

# --- Punto de entrada (sin cambios) ---
def run_gui():
    logger.info("Iniciando aplicación GUI...")
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()
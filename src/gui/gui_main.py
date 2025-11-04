import os
import sys
import webbrowser # <-- ¡Nueva importación!
from pathlib import Path
from typing import List

from src.logic.excel_service import generar_reporte_excel

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableView, QPushButton, QAbstractItemView, QHeaderView,
    QMenu, QMessageBox # <-- ¡Nuevas importaciones!
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction # <-- ¡Nueva importación!
from PySide6.QtCore import Qt, QModelIndex

# Importar el logger
from src.utils.logger import configurar_logger
logger = configurar_logger('gui_main')

# --- Importar funciones de la BD ---
from src.db.db_service import (
    SessionLocal, 
    obtener_datos_tab1_candidatas,
    obtener_datos_tab2_relevantes,
    obtener_datos_tab3_seguimiento,
    gestionar_favorito, # <-- ¡Nueva importación!
    eliminar_ca_definitivamente # <-- ¡Nueva importación!
)
# ---
# --- Importar URL builder ---
from src.scraper.url_builder import construir_url_ficha # <-- ¡Nueva importación!
# ---

# Definimos las columnas que queremos mostrar
COLUMN_HEADERS = [
    "Score", "Código CA", "Nombre", "Estado", "Monto (CLP)", 
    "Cierre", "Proveedores", "ID Interno"
]
# Definimos los índices de las columnas para usarlos
COL_INDEX_CODIGO_CA = 1
COL_INDEX_CA_ID = 7 # (Columna oculta)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Monitor de Compras Ágiles (CA)")
        self.setGeometry(100, 100, 1200, 700) 

        # --- Widget Central y Layout Principal ---
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 1. Panel de Botones (Global) ---
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        
        self.export_button = QPushButton("Exportar Reporte Excel")
        self.export_button.setFixedHeight(40)
        button_layout.addWidget(self.export_button)
        
        self.refresh_button = QPushButton("Refrescar Datos (BD)")
        self.refresh_button.setFixedHeight(40)
        button_layout.addWidget(self.refresh_button)
        
        button_layout.addStretch() 

        # --- 2. Sistema de Pestañas (QTabWidget) ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Pestaña 1: CAs Candidatas ---
        self.tab_candidatas = QWidget()
        self.tabs.addTab(self.tab_candidatas, "CAs Candidatas (Fase 1)")
        layout_candidatas = QVBoxLayout(self.tab_candidatas)
        self.model_tab1 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.table_tab1 = self.crear_tabla_view(self.model_tab1)
        layout_candidatas.addWidget(self.table_tab1)
        # Conectar menú contextual
        self.table_tab1.customContextMenuRequested.connect(self.mostrar_menu_contextual)

        # --- Pestaña 2: CAs Relevantes ---
        self.tab_relevantes = QWidget()
        self.tabs.addTab(self.tab_relevantes, "CAs Relevantes (Fase 2)")
        layout_relevantes = QVBoxLayout(self.tab_relevantes)
        self.model_tab2 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.table_tab2 = self.crear_tabla_view(self.model_tab2)
        layout_relevantes.addWidget(self.table_tab2)
        # Conectar menú contextual
        self.table_tab2.customContextMenuRequested.connect(self.mostrar_menu_contextual)

        # --- Pestaña 3: CAs en Seguimiento ---
        self.tab_seguimiento = QWidget()
        self.tabs.addTab(self.tab_seguimiento, "CAs en Seguimiento (Favoritos)")
        layout_seguimiento = QVBoxLayout(self.tab_seguimiento)
        self.model_tab3 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.table_tab3 = self.crear_tabla_view(self.model_tab3)
        layout_seguimiento.addWidget(self.table_tab3)
        # Conectar menú contextual
        self.table_tab3.customContextMenuRequested.connect(self.mostrar_menu_contextual)

        # --- Conectar señales (botones) ---
        self.export_button.clicked.connect(self.on_exportar_excel)
        self.refresh_button.clicked.connect(self.load_data_to_tables)

        logger.info("Ventana principal (GUI) inicializada.")
        
        # --- Carga Inicial de Datos ---
        self.load_data_to_tables()


    def crear_tabla_view(self, model: QStandardItemModel) -> QTableView:
        """Helper para crear y configurar una QTableView estándar."""
        table_view = QTableView()
        table_view.setModel(model)
        
        # --- ¡NUEVO! Habilitar Menú Contextual ---
        table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Configuración de apariencia
        table_view.setEditTriggers(QAbstractItemView.NoEditTriggers) 
        table_view.setSelectionBehavior(QAbstractItemView.SelectRows) 
        table_view.setSelectionMode(QAbstractItemView.SingleSelection) 
        table_view.setAlternatingRowColors(True)
        
        # Ajustar columnas
        table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table_view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch) 
        
        # Ocultamos la columna 'ID Interno'
        table_view.setColumnHidden(COL_INDEX_CA_ID, True)
        
        return table_view

    def load_data_to_tables(self):
        """Carga/Recarga todos los datos desde la BD a las tablas."""
        logger.info("Refrescando datos desde la Base de Datos...")
        
        db_session = SessionLocal()
        try:
            # Cargar Pestaña 1
            data_tab1 = obtener_datos_tab1_candidatas(db_session)
            self.poblar_tabla(self.model_tab1, data_tab1)
            
            # Cargar Pestaña 2
            data_tab2 = obtener_datos_tab2_relevantes(db_session)
            self.poblar_tabla(self.model_tab2, data_tab2)
            
            # Cargar Pestaña 3
            data_tab3 = obtener_datos_tab3_seguimiento(db_session)
            self.poblar_tabla(self.model_tab3, data_tab3)
            
        except Exception as e:
            logger.critical(f"Error fatal al cargar datos en la GUI: {e}")
            QMessageBox.critical(self, "Error de Base de Datos", 
                                 f"No se pudieron cargar los datos:\n{e}")
        finally:
            db_session.close()
            
        logger.info("Datos refrescados en la GUI.")

    def poblar_tabla(self, model: QStandardItemModel, data: List):
        """Limpia y puebla un modelo de tabla con datos de CaLicitacion."""
        
        model.clear()
        model.setHorizontalHeaderLabels(COLUMN_HEADERS)

        for licitacion in data:
            score = str(licitacion.puntuacion_final)
            codigo = licitacion.codigo_ca
            nombre = licitacion.nombre
            estado = licitacion.estado_ca_texto or "N/A"
            monto = f"{licitacion.monto_clp:,.0f}" if licitacion.monto_clp else "N/A"
            
            try:
                cierre = licitacion.fecha_cierre.strftime('%Y-%m-%d %H:%M')
            except Exception:
                cierre = "N/A"
            
            proveedores = str(licitacion.proveedores_cotizando)
            ca_id = str(licitacion.ca_id) # ID interno

            row_items = [
                QStandardItem(score), QStandardItem(codigo),
                QStandardItem(nombre), QStandardItem(estado),
                QStandardItem(monto), QStandardItem(cierre),
                QStandardItem(proveedores), QStandardItem(ca_id)
            ]
            
            model.appendRow(row_items)

    def on_exportar_excel(self):
        """
        Acción: Llama al excel_service para generar el reporte
        y muestra un diálogo al usuario.
        """
        logger.info("Botón 'Exportar Reporte Excel' presionado.")
        
        # Mostrar un mensaje de "Cargando..." (opcional)
        # (Aquí podríamos poner un cursor de espera)
        
        db_session = SessionLocal()
        try:
            # 1. Llamar al servicio de generación
            ruta_archivo = generar_reporte_excel(db_session)
            
            # 2. Mostrar diálogo de éxito
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Exportación Exitosa")
            msg_box.setText(f"Reporte guardado exitosamente en:\n{ruta_archivo}")
            
            # Añadir un botón para "Abrir Carpeta"
            msg_box.addButton("Abrir Carpeta", QMessageBox.AcceptRole)
            msg_box.addButton("Cerrar", QMessageBox.RejectRole)
            
            ret = msg_box.exec()
            
            if ret == QMessageBox.AcceptRole:
                # Abrir la carpeta contenedora
                try:
                    os.startfile(Path(ruta_archivo).parent)
                except Exception as e:
                    logger.error(f"No se pudo abrir la carpeta de exportación: {e}")

        except Exception as e:
            logger.critical(f"Error fatal al exportar a Excel: {e}")
            QMessageBox.critical(self, "Error de Exportación", 
                                 f"No se pudo generar el reporte:\n{e}")
        finally:
            db_session.close()

    # --- ¡NUEVAS FUNCIONES PARA EL MENÚ CONTEXTUAL! ---

    def mostrar_menu_contextual(self, position):
        """Crea y muestra el menú de clic derecho."""
        
        # Identificar qué tabla generó la señal
        # (podríamos usar sender(), pero es más simple 
        # obtener el índice y el modelo)
        
        # Obtenemos el índice de la celda donde se hizo clic
        # (Usamos la tabla de la pestaña activa)
        active_tab_index = self.tabs.currentIndex()
        if active_tab_index == 0:
            table_view = self.table_tab1
        elif active_tab_index == 1:
            table_view = self.table_tab2
        else:
            table_view = self.table_tab3
            
        index: QModelIndex = table_view.indexAt(position)
        
        if not index.isValid():
            logger.debug("Clic derecho en área vacía de la tabla, no se muestra menú.")
            return # No hacer nada si se hizo clic fuera de una fila

        # Obtenemos los datos de la fila seleccionada
        # (Necesitamos el ID interno y el Código de CA)
        model = table_view.model()
        row = index.row()
        
        # Extraemos el ID y el Código de las columnas
        try:
            ca_id_item = model.item(row, COL_INDEX_CA_ID)
            ca_id = int(ca_id_item.text())
            
            codigo_ca_item = model.item(row, COL_INDEX_CODIGO_CA)
            codigo_ca = codigo_ca_item.text()
        except Exception as e:
            logger.error(f"Error al obtener ID de la fila {row}: {e}")
            return
            
        logger.debug(f"Menú contextual para CA ID: {ca_id} (Código: {codigo_ca})")

        # Crear el menú
        menu = QMenu()
        
        # 1. Marcar como Favorito
        accion_marcar_fav = QAction("1. Marcar como Favorito", self)
        accion_marcar_fav.triggered.connect(lambda: self.on_marcar_favorito(ca_id))
        menu.addAction(accion_marcar_fav)

        # 2. Eliminar Seguimiento
        accion_eliminar_seg = QAction("2. Eliminar Seguimiento", self)
        accion_eliminar_seg.triggered.connect(lambda: self.on_eliminar_seguimiento(ca_id))
        menu.addAction(accion_eliminar_seg)
        
        menu.addSeparator()

        # 3. Eliminar Definitivamente (BD)
        accion_eliminar_def = QAction("3. Eliminar Definitivamente (BD)", self)
        accion_eliminar_def.triggered.connect(lambda: self.on_eliminar_definitivo(ca_id))
        menu.addAction(accion_eliminar_def)
        
        menu.addSeparator()

        # 4. Ver Ficha Web
        accion_ver_web = QAction("4. Ver Ficha Web", self)
        accion_ver_web.triggered.connect(lambda: self.on_ver_ficha_web(codigo_ca))
        menu.addAction(accion_ver_web)

        # Mostrar el menú en la posición global del cursor
        menu.exec_(table_view.viewport().mapToGlobal(position))

    def on_marcar_favorito(self, ca_id: int):
        """Acción: Marca una CA como favorita."""
        logger.info(f"Acción: Marcar como favorito ID: {ca_id}")
        db_session = SessionLocal()
        try:
            gestionar_favorito(db_session, ca_id, es_favorito=True)
        finally:
            db_session.close()
        
        self.load_data_to_tables() # Recargar todas las tablas

    def on_eliminar_seguimiento(self, ca_id: int):
        """Acción: Quita una CA de favoritos."""
        logger.info(f"Acción: Eliminar seguimiento ID: {ca_id}")
        db_session = SessionLocal()
        try:
            gestionar_favorito(db_session, ca_id, es_favorito=False)
        finally:
            db_session.close()
            
        self.load_data_to_tables() # Recargar todas las tablas

    def on_eliminar_definitivo(self, ca_id: int):
        """Acción: Elimina la CA de la BD."""
        logger.info(f"Acción: Eliminar definitivamente ID: {ca_id}")
        
        # --- Diálogo de Confirmación ---
        confirm = QMessageBox.warning(
            self,
            "Confirmación de Eliminación",
            "¿Estás seguro de que quieres eliminar esta CA permanentemente?\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No # Botón por defecto
        )
        
        if confirm == QMessageBox.Yes:
            logger.info(f"Confirmado: Eliminando ID: {ca_id}")
            db_session = SessionLocal()
            try:
                eliminar_ca_definitivamente(db_session, ca_id)
            finally:
                db_session.close()
                
            self.load_data_to_tables() # Recargar todas las tablas
        else:
            logger.info("Eliminación cancelada por el usuario.")

    def on_ver_ficha_web(self, codigo_ca: str):
        """Acción: Abre la ficha en el navegador."""
        logger.info(f"Acción: Ver ficha web: {codigo_ca}")
        url = construir_url_ficha(codigo_ca)
        try:
            webbrowser.open_new_tab(url)
        except Exception as e:
            logger.error(f"No se pudo abrir el navegador: {e}")
            QMessageBox.warning(self, "Error al Abrir", 
                                f"No se pudo abrir el navegador para:\n{url}")


# --- Punto de entrada para ejecutar la aplicación ---
def run_gui():
    logger.info("Iniciando aplicación GUI...")
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()
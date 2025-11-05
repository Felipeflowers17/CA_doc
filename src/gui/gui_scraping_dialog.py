import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, 
    QDateEdit, QLabel, QSpinBox
)
from PySide6.QtCore import QDate, Signal, Slot

class ScrapingDialog(QDialog):
    """
    Diálogo modal para que el usuario seleccione el rango de fechas
    y el límite de páginas para un nuevo scraping.
    """
    
    # Señal que se emite cuando el usuario presiona "Ejecutar"
    # Emite un diccionario con la configuración
    start_scraping = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Iniciar Nuevo Scraping")
        self.setMinimumWidth(350)
        
        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # --- Widgets del Formulario ---
        
        # 1. Fecha Desde
        self.date_from = QDateEdit(calendarPopup=True)
        self.date_from.setDate(QDate.currentDate().addDays(-3)) # Por defecto: hace 3 días
        form_layout.addRow(QLabel("Fecha Desde:"), self.date_from)
        
        # 2. Fecha Hasta
        self.date_to = QDateEdit(calendarPopup=True)
        self.date_to.setDate(QDate.currentDate()) # Por defecto: hoy
        form_layout.addRow(QLabel("Fecha Hasta:"), self.date_to)
        
        # 3. Límite de Páginas
        self.max_pages = QSpinBox()
        self.max_pages.setRange(0, 9999)
        self.max_pages.setValue(5) # Por defecto: 5 páginas
        self.max_pages.setToolTip(
            "Límite de páginas a scrapear.\n"
            "0 = Sin límite (puede tardar mucho)."
        )
        form_layout.addRow(QLabel("Límite de Páginas (0=sin límite):"), self.max_pages)
        
        main_layout.addLayout(form_layout)
        
        # --- Botones (Aceptar/Cancelar) ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.button(QDialogButtonBox.Ok).setText("Ejecutar")
        button_box.button(QDialogButtonBox.Cancel).setText("Cancelar")
        
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)
        
        main_layout.addWidget(button_box)

    @Slot()
    def on_accept(self):
        """
        Se llama al presionar "Ejecutar".
        Valida las fechas y emite la señal 'start_scraping'.
        """
        date_from_obj = self.date_from.date()
        date_to_obj = self.date_to.date()
        
        if date_from_obj > date_to_obj:
            QMessageBox.warning(self, "Error de Fechas", 
                                "La 'Fecha Desde' no puede ser posterior a la 'Fecha Hasta'.")
            return
            
        # Preparar el diccionario de configuración
        config = {
            "date_from": date_from_obj.toString("yyyy-MM-dd"),
            "date_to": date_to_obj.toString("yyyy-MM-dd"),
            "max_paginas": self.max_pages.value()
        }
        
        # Emitir la señal con la configuración
        self.start_scraping.emit(config)
        
        # Cerrar el diálogo
        self.accept()

# --- Para probar el diálogo de forma independiente ---
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMessageBox
    
    app = QApplication(sys.argv)
    
    dialog = ScrapingDialog()
    
    # Conectar la señal para ver qué emite
    def on_start(config):
        print("Señal 'start_scraping' recibida:")
        print(config)
        QMessageBox.information(None, "Configuración Recibida", str(config))

    dialog.start_scraping.connect(on_start)
    
    dialog.exec()
    sys.exit(app.exec())
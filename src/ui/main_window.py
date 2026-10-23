# -*- coding: utf-8 -*-
import os
import cv2
import numpy as np
import matplotlib
# Forzar PyQt6 para matplotlib
os.environ['QT_API'] = 'pyqt6'
matplotlib.use('QtAgg')  # Usar backend Qt con PyQt6
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QTabWidget, QFileDialog, QMessageBox,
                             QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QComboBox, QGridLayout, QGroupBox, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPen

from src.vision.canny_detector import DefectDetector
from src.vision.feature_extractor import FeatureExtractor
from src.database.db_manager import DatabaseManager
from src.neural_network.network import NeuralNetwork
from src.optimization.bin_packing import GlassSheet
from src.optimization.obstacle_avoidance import BinPacker

class MainWindow(QMainWindow):
    def __init__(self, user_id=None, username="Usuario", role="usuario"):
        super().__init__()
        self.user_id = user_id
        self.username = username
        self.role = role
        
        self.setWindowTitle(f"SIAM - Sesion: {username} ({role.upper()})")
        self.setMinimumSize(1024, 768)
        
        self.current_theme = "dark"
        self._init_theme_stylesheets()

        self.db = DatabaseManager()
        self.db.insert_batch("Proveedor Demo", 100, "Lote inicial de prueba")
        self.detector = DefectDetector()
        
        # Registrar el inicio de sesión en el log de actividad
        if self.user_id:
            self.db.log_activity(self.user_id, "Inicio de Sesion", f"El usuario {self.username} ingreso al sistema")
        
        # Inicializar y cargar el 'Cerebro' de la Red Neuronal entrenada (Fase 6)
        try:
            self.nn = NeuralNetwork()
            from src.neural_network.layer import Layer_Dense
            from src.neural_network.activations import Activation_ReLU, Activation_Sigmoid
            
            self.nn.add(Layer_Dense(5, 16))
            self.nn.add(Activation_ReLU())
            self.nn.add(Layer_Dense(16, 16))
            self.nn.add(Activation_ReLU())
            self.nn.add(Layer_Dense(16, 3))
            self.nn.add(Activation_Sigmoid())
            
            if os.path.exists('src/model_weights.pkl'):
                self.nn.load_weights('src/model_weights.pkl')
                self.norm_max = np.load('src/normalization_max.npy')
                self.nn_ready = True
            else:
                self.nn_ready = False
        except Exception as e:
            print("Error cargando la red neuronal:", e)
            self.nn_ready = False
            
        self.current_image_path = None
        self.image_contours = None
        self.image_edges = None
        self.original_image = None
        
        # Soporte para Cámara Web en Vivo (Escaneo Físico)
        self.cap = None
        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self.update_camera_frame)
        
        self.orders = []

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Barra superior con información de usuario, título y selector de Modo Oscuro / Modo Claro
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(8, 2, 8, 4)

        user_info = QLabel(f"👤 {self.username}  |  Rol: {self.role.upper()}")
        user_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #64748B; padding: 4px 8px;")
        top_bar_layout.addWidget(user_info)

        top_bar_layout.addStretch()

        self.header_title = QLabel("Panel de Control Principal - SIAM")
        self.header_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1A73E8; padding: 6px;")
        self.header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_bar_layout.addWidget(self.header_title)

        top_bar_layout.addStretch()

        # Selector de Tema
        theme_container = QHBoxLayout()
        theme_icon = QLabel("🎨")
        theme_icon.setStyleSheet("font-size: 14px;")
        theme_label = QLabel("Tema:")
        theme_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(["🌙 Modo Oscuro", "☀️ Modo Claro"])
        self.theme_selector.currentIndexChanged.connect(self.on_theme_selector_changed)
        theme_container.addWidget(theme_icon)
        theme_container.addWidget(theme_label)
        theme_container.addWidget(self.theme_selector)
        top_bar_layout.addLayout(theme_container)

        main_layout.addLayout(top_bar_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.setup_vision_tab()
        self.setup_optimization_tab()
        self.setup_traceability_tab()
        self.setup_dashboard_tab()
        
        # Solo los administradores ven la pestaña de métricas
        if self.role == 'admin':
            self.setup_admin_tab()

        # Animación de transición suave entre pestañas (Fade-in)
        self.tabs.currentChanged.connect(self.animate_tab_transition)

        # Aplicar tema inicial
        self.apply_theme("dark")

    def setup_vision_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        controls_layout = QHBoxLayout()
        self.btn_load = QPushButton("📁 Cargar Imagen")
        
        self.camera_selector = QComboBox()
        self.camera_selector.setStyleSheet("""
            QComboBox {
                background-color: #0F1520; color: #E0E6ED;
                border: 1px solid #1E293B; border-radius: 6px;
                padding: 8px 12px; font-size: 13px; font-weight: bold;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #0F1520; color: #E0E6ED;
                selection-background-color: #1A73E8;
            }
        """)
        self.camera_selector.addItem("📷 Cámara Color Normal", 1)
        self.camera_selector.addItem("📷 Cámara Infrarroja (IR)", 0)
        
        self.btn_camera = QPushButton("📷 Iniciar Cámara Web")
        self.btn_camera.setStyleSheet("""
            QPushButton {
                background-color: #0284C7; color: #FFFFFF;
                border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        
        self.btn_canny = QPushButton("2. Extraer Bordes (Canny)")
        self.btn_nn = QPushButton("3. Clasificar Defecto (Red Neuronal)")
        self.btn_refresh_vision = QPushButton("🔄 Refrescar Modulo")
        self.btn_refresh_vision.setStyleSheet("""
            QPushButton {
                background-color: #334155; color: #F8FAFC;
                border: 1px solid #475569;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        
        self.btn_canny.setEnabled(False)
        self.btn_nn.setEnabled(False)
        
        self.btn_load.clicked.connect(self.load_image)
        self.btn_camera.clicked.connect(self.toggle_camera)
        self.btn_canny.clicked.connect(self.apply_canny)
        self.btn_nn.clicked.connect(self.classify_defect)
        self.btn_refresh_vision.clicked.connect(self.refresh_vision_tab)
        
        controls_layout.addWidget(self.btn_load)
        controls_layout.addWidget(self.camera_selector)
        controls_layout.addWidget(self.btn_camera)
        controls_layout.addWidget(self.btn_canny)
        controls_layout.addWidget(self.btn_nn)
        controls_layout.addWidget(self.btn_refresh_vision)
        layout.addLayout(controls_layout)
        
        self.vision_display = QLabel("Area de visualizacion de la camara\n(Esperando entrada...)")
        self.vision_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vision_display.setStyleSheet("background-color: #0B0E14; border: 2px dashed #1E293B; font-size: 16px;")
        layout.addWidget(self.vision_display, stretch=1)
        
        # Panel de Control de Calidad y Criterios de Aceptación
        self.qc_card = QWidget()
        self.qc_card.setStyleSheet("""
            QWidget {
                background-color: #0F1520;
                border: 1px solid #1E293B;
                border-radius: 8px;
            }
        """)
        qc_card_layout = QVBoxLayout(self.qc_card)
        qc_card_layout.setContentsMargins(15, 10, 15, 10)
        qc_card_layout.setSpacing(6)
        
        qc_header_layout = QHBoxLayout()
        qc_title = QLabel("🛡️ Control de Calidad y Criterio de Aprobación:")
        qc_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #E0E6ED; border: none;")
        
        self.qc_badge = QLabel("⚪ ESPERANDO ANÁLISIS")
        self.qc_badge.setStyleSheet("""
            font-size: 13px; font-weight: bold; color: #94A3B8;
            background-color: #1E293B; border-radius: 6px; padding: 4px 14px; border: none;
        """)
        self.qc_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        qc_header_layout.addWidget(qc_title)
        qc_header_layout.addStretch()
        qc_header_layout.addWidget(self.qc_badge)
        qc_card_layout.addLayout(qc_header_layout)
        
        self.qc_details = QLabel("Cargue o capture una lámina y presione '3. Clasificar Defecto' para evaluar si el vidrio pasa o es rechazado según parámetros de tolerancia.")
        self.qc_details.setStyleSheet("font-size: 12px; color: #94A3B8; border: none;")
        self.qc_details.setWordWrap(True)
        qc_card_layout.addWidget(self.qc_details)
        
        layout.addWidget(self.qc_card)
        
        self.tabs.addTab(tab, "Vision y Clasificacion IA")

    def setup_optimization_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        controls_layout = QHBoxLayout()
        self.btn_add_order = QPushButton("Anadir Pedido de Corte")
        self.btn_optimize = QPushButton("Generar Plano Digital (Bin Packing)")
        
        self.btn_add_order.clicked.connect(self.add_order)
        self.btn_optimize.clicked.connect(self.generate_cutting_plan)
        
        controls_layout.addWidget(self.btn_add_order)
        controls_layout.addWidget(self.btn_optimize)
        layout.addLayout(controls_layout)
        
        self.optimization_display = QLabel("Lienzo del Plano de Corte\n(Mostrando heuristica de esquive...)")
        self.optimization_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.optimization_display.setStyleSheet("background-color: #0B0E14; border: 2px dashed #1E293B; font-size: 16px;")
        layout.addWidget(self.optimization_display, stretch=1)
        
        self.tabs.addTab(tab, "Optimizacion de Corte")

    def setup_traceability_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.btn_refresh = QPushButton("Actualizar Registros (Consultar BD)")
        self.btn_refresh.clicked.connect(self.refresh_database)
        layout.addWidget(self.btn_refresh)
        
        self.db_table = QTableWidget()
        self.db_table.setColumnCount(7)
        self.db_table.setHorizontalHeaderLabels([
            "ID Defecto", "Batch Lote", "Diagnostico IA", "Coordenadas Falla", "Area Danada", "Control Calidad", "Severidad"
        ])
        self.db_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.db_table, stretch=1)
        
        self.tabs.addTab(tab, "Trazabilidad y Base de Datos")

    def setup_dashboard_tab(self):
        """Pestaña del dashboard gráfico de defectos."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Título y controles
        dashboard_header = QLabel("📊 Dashboard Gráfico de Defectos en Trazabilidad")
        dashboard_header.setStyleSheet("font-size: 18px; font-weight: bold; color: #1A73E8; padding: 10px;")
        dashboard_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dashboard_header)
        
        # Controles de filtro y actualización
        controls_layout = QHBoxLayout()
        
        self.btn_refresh_dashboard = QPushButton("🔄 Actualizar Dashboard")
        self.btn_refresh_dashboard.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: #FFFFFF;
                font-weight: bold; border-radius: 6px; padding: 10px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_refresh_dashboard.clicked.connect(self.refresh_dashboard)
        
        self.combo_chart_type = QComboBox()
        self.combo_chart_type.addItems([
            "Distribución por Tipo de Defecto",
            "Severidad de Defectos", 
            "Estado de Control de Calidad",
            "Mapa Térmico de Defectos",
            "Tendencia Temporal",
            "Correlación Defectos-Eficiencia"
        ])
        self.combo_chart_type.setStyleSheet("""
            QComboBox {
                background-color: #0F1520; color: #E0E6ED;
                border: 1px solid #1E293B; border-radius: 6px;
                padding: 8px 12px; font-size: 13px; font-weight: bold;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #0F1520; color: #E0E6ED;
                selection-background-color: #1A73E8;
            }
        """)
        
        self.combo_time_range = QComboBox()
        self.combo_time_range.addItems(["Últimos 7 días", "Últimos 30 días", "Últimos 90 días", "Todo el período"])
        
        controls_layout.addWidget(self.btn_refresh_dashboard)
        controls_layout.addWidget(QLabel("Gráfico:"))
        controls_layout.addWidget(self.combo_chart_type)
        controls_layout.addWidget(QLabel("Período:"))
        controls_layout.addWidget(self.combo_time_range)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Panel de métricas rápidas
        metrics_group = QGroupBox("📈 Métricas Rápidas")
        metrics_group.setStyleSheet("""
            QGroupBox {
                background-color: #0F1520;
                border: 1px solid #1E293B;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #E0E6ED;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #94A3B8;
            }
        """)
        metrics_layout = QHBoxLayout()
        
        # Widgets para métricas
        self.metric_total = QLabel("Total Defectos: 0")
        self.metric_avg_area = QLabel("Área Promedio: 0 mm²")
        self.metric_rejected = QLabel("Rechazados: 0")
        self.metric_critical = QLabel("Críticos: 0")
        
        self.metrics_group = metrics_group
        self.metric_widgets = [self.metric_total, self.metric_avg_area, self.metric_rejected, self.metric_critical]
        for metric_widget in self.metric_widgets:
            metrics_layout.addWidget(metric_widget)
        
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)
        
        # Área del gráfico principal
        bg_color = self.colors.get('background', '#0F1520') if hasattr(self, 'colors') else '#0F1520'
        self.dashboard_canvas = FigureCanvas(Figure(figsize=(10, 6), facecolor=bg_color))
        self.dashboard_canvas.figure.patch.set_facecolor(bg_color)
        
        self.dashboard_canvas_layout = QVBoxLayout()
        self.dashboard_canvas_layout.addWidget(self.dashboard_canvas)
        layout.addLayout(self.dashboard_canvas_layout, stretch=1)
        
        # Cargar datos iniciales
        self.tabs.addTab(tab, "Dashboard de Defectos")
        self.refresh_dashboard()

    def setup_admin_tab(self):
        """Pestaña exclusiva para administradores: muestra métricas de los usuarios."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Título del módulo
        admin_header = QLabel(f"Panel de Administrador - Bienvenido, {self.username}")
        admin_header.setStyleSheet("font-size: 18px; font-weight: bold; color: #1A73E8; padding: 5px;")
        admin_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(admin_header)
        
        # Botones de control
        btn_layout = QHBoxLayout()
        
        self.btn_refresh_all = QPushButton("🔄 Refrescar Panel Completo")
        self.btn_refresh_all.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: #FFFFFF;
                font-weight: bold; border-radius: 6px; padding: 10px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.btn_refresh_all.clicked.connect(self.refresh_all_admin_tables)
        
        self.btn_refresh_users = QPushButton("Ver Usuarios Registrados")
        self.btn_refresh_users.clicked.connect(self.refresh_users_table)
        
        self.btn_refresh_activity = QPushButton("Ver Historial de Actividad")
        self.btn_refresh_activity.clicked.connect(self.refresh_activity_table)
        
        self.btn_refresh_metrics = QPushButton("Ver Metricas por Usuario")
        self.btn_refresh_metrics.clicked.connect(self.refresh_metrics_table)
        
        btn_layout.addWidget(self.btn_refresh_all)
        btn_layout.addWidget(self.btn_refresh_users)
        btn_layout.addWidget(self.btn_refresh_activity)
        btn_layout.addWidget(self.btn_refresh_metrics)
        layout.addLayout(btn_layout)
        
        # Tabla de usuarios registrados
        users_lbl = QLabel("Usuarios Registrados (Normales y Administradores):")
        users_lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(users_lbl)
        
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(5)
        self.users_table.setHorizontalHeaderLabels(["ID", "Usuario", "Correo", "Telefono", "Rol"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.users_table)
        
        # Tabla de historial de actividad
        activity_lbl = QLabel("Historial de Actividad Completo:")
        activity_lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(activity_lbl)
        
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(5)
        self.activity_table.setHorizontalHeaderLabels(["Usuario", "Rol", "Accion", "Detalle", "Fecha/Hora"])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.activity_table)
        
        # Tabla de métricas resumen
        metrics_lbl = QLabel("Metricas Resumen por Usuario:")
        metrics_lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(metrics_lbl)
        
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(4)
        self.metrics_table.setHorizontalHeaderLabels(["Usuario", "Rol", "Tipo de Accion", "Total Ejecuciones"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.metrics_table)
        
        # Cargar datos automáticamente al inicializar el panel
        self.refresh_all_admin_tables()
        
        self.tabs.addTab(tab, "Panel Administrador")

    # --- LÓGICA DEL MÓDULO ADMIN ---
    
    def refresh_all_admin_tables(self):
        """Refresca todas las tablas del panel de administrador simultáneamente."""
        self.refresh_users_table()
        self.refresh_activity_table()
        self.refresh_metrics_table()

    def refresh_users_table(self):
        rows = self.db.get_all_users()
        self.users_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.users_table.setItem(i, 0, QTableWidgetItem(str(row[0])))
            self.users_table.setItem(i, 1, QTableWidgetItem(str(row[1])))
            self.users_table.setItem(i, 2, QTableWidgetItem(str(row[2])))
            self.users_table.setItem(i, 3, QTableWidgetItem(str(row[3])))
            
            role_str = str(row[4]).upper()
            role_item = QTableWidgetItem(role_str)
            if role_str == 'ADMIN':
                role_item.setForeground(QColor("#38BDF8"))  # Celeste para Admin
            else:
                role_item.setForeground(QColor("#4ADE80"))  # Verde para Usuario Normal
            self.users_table.setItem(i, 4, role_item)

    def refresh_activity_table(self):
        rows = self.db.get_user_activity()
        self.activity_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.activity_table.setItem(i, 0, QTableWidgetItem(str(row[1])))  # username
            
            role_str = str(row[5]).upper() if len(row) > 5 else "USUARIO"
            role_item = QTableWidgetItem(role_str)
            if role_str == 'ADMIN':
                role_item.setForeground(QColor("#38BDF8"))
            else:
                role_item.setForeground(QColor("#4ADE80"))
            self.activity_table.setItem(i, 1, role_item)
            
            self.activity_table.setItem(i, 2, QTableWidgetItem(str(row[2])))  # action
            self.activity_table.setItem(i, 3, QTableWidgetItem(str(row[3] or "")))  # details
            self.activity_table.setItem(i, 4, QTableWidgetItem(str(row[4])))  # timestamp

    def refresh_metrics_table(self):
        rows = self.db.get_user_metrics()
        self.metrics_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(str(row[0])))  # username
            
            role_str = str(row[1]).upper()
            role_item = QTableWidgetItem(role_str)
            if role_str == 'ADMIN':
                role_item.setForeground(QColor("#38BDF8"))
            else:
                role_item.setForeground(QColor("#4ADE80"))
            self.metrics_table.setItem(i, 1, role_item)
            
            self.metrics_table.setItem(i, 2, QTableWidgetItem(str(row[2])))  # action
            self.metrics_table.setItem(i, 3, QTableWidgetItem(str(row[3])))  # count

    # --- LÓGICA DE EVENTOS (WIRING) ---
    
    def display_image(self, cv_img):
        if len(cv_img.shape) == 3:
            h, w, ch = cv_img.shape
            bytes_per_line = ch * w
            rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        else:
            h, w = cv_img.shape
            bytes_per_line = w
            qimg = QImage(cv_img.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            
        pixmap = QPixmap.fromImage(qimg)
        scaled_pixmap = pixmap.scaled(self.vision_display.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.vision_display.setPixmap(scaled_pixmap)

    def update_camera_frame(self):
        """Actualiza el visor con el fotograma en vivo capturado desde la webcam."""
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.display_image(frame)

    def toggle_camera(self):
        """Alterna entre transmisión en vivo y congelar/capturar el fotograma para análisis."""
        if self.cap is not None and self.cap.isOpened():
            # Estado activo: congelar y capturar el cuadro actual
            ret, frame = self.cap.read()
            self.camera_timer.stop()
            self.cap.release()
            self.cap = None
            
            if hasattr(self, 'camera_selector'):
                self.camera_selector.setEnabled(True)
                
            self.btn_camera.setText("📷 Iniciar Cámara Web")
            self.btn_camera.setStyleSheet("""
                QPushButton {
                    background-color: #0284C7; color: #FFFFFF;
                    border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px;
                }
                QPushButton:hover { background-color: #0369A1; }
            """)
            
            if ret and frame is not None:
                self.original_image = frame.copy()
                capture_path = os.path.abspath("captura_camara.png")
                cv2.imwrite(capture_path, self.original_image)
                self.current_image_path = capture_path
                self.display_image(self.original_image)
                self.btn_canny.setEnabled(True)
                
                if self.user_id:
                    self.db.log_activity(self.user_id, "Captura con Camara", "Se escaneo y congelo lamina física desde la webcam")
                
                QMessageBox.information(self, "Captura Exitosa", "Lámina física capturada y congelada en color.\nYa puedes presionar '2. Extraer Bordes (Canny)'.")
            else:
                QMessageBox.warning(self, "Aviso", "No se pudo congelar el cuadro de la cámara.")
        else:
            # Estado inactivo: encender cámara seleccionada (por defecto índice 1: normal a color)
            cam_idx = 1
            if hasattr(self, 'camera_selector'):
                cam_idx = self.camera_selector.currentData()
                self.camera_selector.setEnabled(False)
                
            self.cap = cv2.VideoCapture(cam_idx)
            if not self.cap.isOpened():
                # Respaldo si el índice seleccionado no abre
                fallback_idx = 0 if cam_idx == 1 else 1
                self.cap = cv2.VideoCapture(fallback_idx)
                
            if not self.cap.isOpened():
                self.cap = None
                if hasattr(self, 'camera_selector'):
                    self.camera_selector.setEnabled(True)
                QMessageBox.critical(self, "Cámara No Disponible", "No se pudo acceder a la cámara web de la computadora.\nVerifica que esté conectada y tenga permisos.")
                return
            
            self.camera_timer.start(30)
            self.btn_camera.setText("📸 Congelar / Capturar Lámina")
            self.btn_camera.setStyleSheet("""
                QPushButton {
                    background-color: #DC2626; color: #FFFFFF;
                    border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px;
                }
                QPushButton:hover { background-color: #B91C1C; }
            """)
            self.btn_canny.setEnabled(False)
            self.btn_nn.setEnabled(False)

    def load_image(self):
        # Detener la cámara si estaba transmitiendo
        if self.cap is not None and self.cap.isOpened():
            self.camera_timer.stop()
            self.cap.release()
            self.cap = None
            self.btn_camera.setText("📷 Iniciar Cámara Web")
            self.btn_camera.setStyleSheet("""
                QPushButton {
                    background-color: #0284C7; color: #FFFFFF;
                    border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px;
                }
                QPushButton:hover { background-color: #0369A1; }
            """)
        if hasattr(self, 'camera_selector'):
            self.camera_selector.setEnabled(True)
            
        file_name, _ = QFileDialog.getOpenFileName(self, "Cargar Lamina", "", "Images (*.png *.jpg *.jpeg)")
        if file_name:
            self.current_image_path = file_name
            self.original_image = cv2.imread(file_name)
            self.display_image(self.original_image)
            self.btn_canny.setEnabled(True)
            if self.user_id:
                self.db.log_activity(self.user_id, "Carga de Imagen", f"Archivo: {os.path.basename(file_name)}")

    def apply_canny(self):
        if self.current_image_path:
            self.original_image, self.image_edges, self.image_contours = self.detector.process_image(self.current_image_path)
            img_with_contours = self.original_image.copy()
            cv2.drawContours(img_with_contours, self.image_contours, -1, (0, 255, 0), 2)
            self.display_image(img_with_contours)
            self.btn_nn.setEnabled(True)
            if self.user_id:
                self.db.log_activity(self.user_id, "Deteccion Canny", f"Contornos detectados: {len(self.image_contours)}")

    def evaluate_quality_control(self, defect_type, area, perimeter, circularity):
        """
        Evalúa el estado de control de calidad según parámetros de tolerancia industrial:
        - Rotura: siempre RECHAZADO (falla crítica estructural, peligro de quiebre).
        - Rayon:
            - Si área < 120 mm²: APROBADO CON CONDICIÓN (Leve/Superficial, apto para corte secundario).
            - Si área >= 120 mm²: RECHAZADO (Rayón profundo/extenso, no apto para entrega).
        - Burbuja:
            - Si área < 80 mm²: APROBADO (Microburbuja dentro de norma de tolerancia óptica).
            - Si área >= 80 mm²: RECHAZADO (Burbuja oclusiva no admisible).
        Retorna: (qc_status, severity, recommendation)
        """
        defect_type_lower = defect_type.lower()
        
        if "rotura" in defect_type_lower:
            return (
                "RECHAZADO", 
                "CRÍTICA", 
                "Lámina con fractura estructural. Peligro inminente de quiebre en mesa de corte. Enviar a merma total."
            )
        elif "rayon" in defect_type_lower:
            if area < 120.0:
                return (
                    "APROBADO CON CONDICIÓN", 
                    "LEVE", 
                    f"Rayón superficial dentro de tolerancia ({area:.1f} mm² < 120 mm² límite). Apto para piezas secundarias o pulido."
                )
            else:
                return (
                    "RECHAZADO", 
                    "GRAVE", 
                    f"Rayón extenso o profundo ({area:.1f} mm² >= 120 mm² límite). No cumple con el estándar estético de entrega."
                )
        elif "burbuja" in defect_type_lower:
            if area < 80.0:
                return (
                    "APROBADO", 
                    "TOLERABLE", 
                    f"Micro-burbuja dentro de norma óptica ({area:.1f} mm² < 80 mm² límite). Apto para producción directa."
                )
            else:
                return (
                    "RECHAZADO", 
                    "MODERADA", 
                    f"Burbuja oclusiva visible ({area:.1f} mm² >= 80 mm² límite). Concentración de tensiones no admisible."
                )
        else:
            return (
                "APROBADO", 
                "NINGUNA", 
                "Lámina en óptimo estado. Sin defectos críticos detectados."
            )

    def classify_defect(self):
        if not self.image_contours:
            QMessageBox.warning(self, "Vision", "No se detectaron fallas.")
            return
            
        features = FeatureExtractor.extract_features(self.image_contours[0])
        
        if self.nn_ready:
            features_norm = features / self.norm_max
            output = self.nn.forward(np.array([features_norm]))
            clase_idx = np.argmax(output[0])
            probabilidad = output[0][clase_idx] * 100
            
            clases = ["Burbuja", "Rayon", "Rotura"]
            diagnostico = clases[clase_idx]
            
            # Evaluación automática de Control de Calidad
            qc_status, severity, recommendation = self.evaluate_quality_control(diagnostico, features[0], features[1], features[2])
            
            # Actualización del Badge visual en el panel
            if qc_status == "APROBADO":
                badge_icon = "✅"
                bg_color = "rgba(16, 185, 129, 0.2)"
                border_color = "#10B981"
                text_color = "#34D399"
            elif qc_status == "APROBADO CON CONDICIÓN":
                badge_icon = "⚠️"
                bg_color = "rgba(245, 158, 11, 0.2)"
                border_color = "#F59E0B"
                text_color = "#FBBF24"
            else:
                badge_icon = "❌"
                bg_color = "rgba(239, 68, 68, 0.2)"
                border_color = "#EF4444"
                text_color = "#F87171"
                
            self.qc_badge.setText(f"{badge_icon} ESTADO: {qc_status}")
            self.qc_badge.setStyleSheet(f"""
                font-size: 13px; font-weight: bold; color: {text_color};
                background-color: {bg_color}; border: 1px solid {border_color};
                border-radius: 6px; padding: 4px 14px;
            """)
            
            self.qc_details.setText(
                f"<b>Diagnóstico IA:</b> {diagnostico} ({probabilidad:.1f}%) | "
                f"<b>Severidad:</b> {severity} | "
                f"<b>Área:</b> {features[0]:.1f} mm²<br>"
                f"<b>Criterio Técnico:</b> {recommendation}"
            )
            
            msg = (
                f"DIAGNÓSTICO IA & CONTROL DE CALIDAD:\n\n"
                f"Estado QC: {badge_icon} {qc_status}\n"
                f"Clasificación: {diagnostico} (Confianza: {probabilidad:.1f}%)\n"
                f"Nivel de Severidad: {severity}\n"
                f"Área Dañada: {features[0]:.1f} mm² (Perímetro: {features[1]:.1f}, Circularidad: {features[2]:.2f})\n\n"
                f"Criterio Técnico:\n{recommendation}"
            )
            QMessageBox.information(self, "Control de Calidad", msg)
            
            x, y, w, h = cv2.boundingRect(self.image_contours[0])
            self.db.insert_defect(1, diagnostico, x, y, features[0], qc_status, severity)
            
            if self.user_id:
                self.db.log_activity(self.user_id, "Control de Calidad", f"{qc_status} - {diagnostico} ({severity})")
        else:
            QMessageBox.warning(self, "Error de IA", "El modelo no esta entrenado. Faltan los pesos en src/model_weights.pkl.")

    def refresh_vision_tab(self):
        """Reinicia el visor y el flujo de detección del módulo 1 a su estado original."""
        if hasattr(self, 'camera_timer') and self.camera_timer.isActive():
            self.camera_timer.stop()
        if hasattr(self, 'cap') and self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None
        if hasattr(self, 'btn_camera'):
            self.btn_camera.setText("📷 Iniciar Cámara Web")
            self.btn_camera.setStyleSheet("""
                QPushButton {
                    background-color: #0284C7; color: #FFFFFF;
                    border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px;
                }
                QPushButton:hover { background-color: #0369A1; }
            """)
        if hasattr(self, 'camera_selector'):
            self.camera_selector.setEnabled(True)

        self.current_image_path = None
        self.original_image = None
        self.image_edges = None
        self.image_contours = None
        
        self.btn_canny.setEnabled(False)
        self.btn_nn.setEnabled(False)
        
        self.vision_display.clear()
        self.vision_display.setText("Area de visualizacion de la camara\n(Esperando entrada...)")
        
        if hasattr(self, 'qc_badge'):
            self.qc_badge.setText("⚪ ESPERANDO ANÁLISIS")
            self.qc_badge.setStyleSheet("""
                font-size: 13px; font-weight: bold; color: #94A3B8;
                background-color: #1E293B; border-radius: 6px; padding: 4px 14px; border: none;
            """)
        if hasattr(self, 'qc_details'):
            self.qc_details.setText("Cargue o capture una lámina y presione '3. Clasificar Defecto' para evaluar si el vidrio pasa o es rechazado según parámetros de tolerancia.")
        
        if self.user_id:
            self.db.log_activity(self.user_id, "Refrescar Modulo 1", "Se reinicio el lienzo y estado del modulo de vision")

    # LÓGICA OPTIMIZACIÓN
    def add_order(self):
        w, ok1 = QInputDialog.getInt(self, "Anadir Pedido", "Ancho del corte (mm):", 500, 10, 2000, 10)
        if ok1:
            h, ok2 = QInputDialog.getInt(self, "Anadir Pedido", "Alto del corte (mm):", 500, 10, 2000, 10)
            if ok2:
                order_id = f"Pedido-{len(self.orders)+1}"
                self.orders.append({'id': order_id, 'w': w, 'h': h})
                QMessageBox.information(self, "Exito", f"{order_id} anadido exitosamente.")
                if self.user_id:
                    self.db.log_activity(self.user_id, "Pedido de Corte", f"{order_id}: {w}x{h} mm")

    def generate_cutting_plan(self):
        if not self.orders:
            QMessageBox.warning(self, "Aviso", "No hay pedidos pendientes.")
            return
            
        sheet = GlassSheet(2000, 2000, resolution=10)
        
        defect_coords = None
        if self.image_contours:
            x, y, w, h = cv2.boundingRect(self.image_contours[0])
            sheet.add_defect(x*5, y*5, w*5, h*5)
            defect_coords = (x*5, y*5, w*5, h*5)
            
        packer = BinPacker(sheet)
        placed_pieces = packer.pack(self.orders)
        
        self.draw_cutting_plan(2000, 2000, placed_pieces, defect_coords)
        
        if placed_pieces:
            report = f"EXITO:\nSe lograron acomodar {len(placed_pieces)} de {len(self.orders)} piezas solicitadas."
            if defect_coords:
                report += "\nEl algoritmo esquivo exitosamente el area defectuosa."
            QMessageBox.information(self, "Reporte de Optimizacion", report)
            if self.user_id:
                self.db.log_activity(self.user_id, "Optimizacion Corte", f"Piezas colocadas: {len(placed_pieces)}/{len(self.orders)}")
        else:
            QMessageBox.warning(self, "Alerta", "Ninguna de las piezas pudo ser acomodada.")

    def draw_cutting_plan(self, sheet_w, sheet_h, placed_pieces, defect=None):
        canvas_w, canvas_h = 800, 800
        pixmap = QPixmap(canvas_w, canvas_h)
        pixmap.fill(QColor("#E0E6ED")) 
        
        painter = QPainter(pixmap)
        scale_x = canvas_w / sheet_w
        scale_y = canvas_h / sheet_h
        
        if defect:
            dx, dy, dw, dh = defect
            painter.setBrush(QColor(255, 60, 60, 200))
            painter.setPen(QPen(Qt.GlobalColor.red, 3))
            painter.drawRect(int(dx*scale_x), int(dy*scale_y), int(dw*scale_x), int(dh*scale_y))
            
        painter.setBrush(QColor(26, 115, 232, 180))
        painter.setPen(QPen(QColor("#0F1520"), 2))
        
        for p in placed_pieces:
            x_px, y_px = int(p['x']*scale_x), int(p['y']*scale_y)
            w_px, h_px = int(p['w']*scale_x), int(p['h']*scale_y)
            painter.drawRect(x_px, y_px, w_px, h_px)
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(x_px + 10, y_px + 25, p['id'])
            painter.setPen(QPen(QColor("#0F1520"), 2))
            
        painter.end()
        self.optimization_display.setPixmap(pixmap)

    # LÓGICA BASE DE DATOS
    def refresh_database(self):
        rows = self.db.get_quality_inspections()
        self.db_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            # row_data: (id, batch_id, defect_type, x_coord, y_coord, defect_area, qc_status, severity)
            self.db_table.setItem(row_idx, 0, QTableWidgetItem(f"D-{row_data[0]}"))
            self.db_table.setItem(row_idx, 1, QTableWidgetItem(f"Lote #{row_data[1]}"))
            self.db_table.setItem(row_idx, 2, QTableWidgetItem(str(row_data[2])))
            self.db_table.setItem(row_idx, 3, QTableWidgetItem(f"({row_data[3]:.0f}, {row_data[4]:.0f})"))
            self.db_table.setItem(row_idx, 4, QTableWidgetItem(f"{row_data[5]:.2f} mm²"))
            
            qc_status = str(row_data[6]) if len(row_data) > 6 and row_data[6] else "PENDIENTE"
            qc_item = QTableWidgetItem(qc_status)
            if "APROBADO" in qc_status and "CONDICIÓN" not in qc_status:
                qc_item.setForeground(QColor("#4ADE80"))  # Verde
            elif "CONDICIÓN" in qc_status:
                qc_item.setForeground(QColor("#FBBF24"))  # Amarillo
            else:
                qc_item.setForeground(QColor("#F87171"))  # Rojo
            self.db_table.setItem(row_idx, 5, qc_item)
            
            severity = str(row_data[7]) if len(row_data) > 7 and row_data[7] else "LEVE"
            self.db_table.setItem(row_idx, 6, QTableWidgetItem(severity))
        
        if self.user_id:
            self.db.log_activity(self.user_id, "Consulta BD", "Consulto tabla de inspecciones con control de calidad")

    # --- LÓGICA DEL DASHBOARD GRÁFICO ---
    
    def refresh_dashboard(self):
        """Actualiza el dashboard con los datos más recientes."""
        try:
            # Obtener estadísticas desde la base de datos
            stats = self.db.get_defect_statistics()
            
            # Actualizar métricas rápidas
            if stats['general_stats'] and stats['general_stats'][0]:
                total, avg_area, max_area, min_area, area_total = stats['general_stats']
                self.metric_total.setText(f"Total Defectos: {total}")
                self.metric_avg_area.setText(f"Área Promedio: {avg_area:.1f} mm²")
                
                # Calcular rechazados
                rejected_count = 0
                critical_count = 0
                if stats['qc_stats']:
                    for status, count, _ in stats['qc_stats']:
                        if "RECHAZADO" in str(status):
                            rejected_count += count
                
                if stats['severity_stats']:
                    for severity, count, _ in stats['severity_stats']:
                        if severity in ["CRÍTICA", "GRAVE"]:
                            critical_count += count
                
                self.metric_rejected.setText(f"Rechazados: {rejected_count}")
                self.metric_critical.setText(f"Críticos: {critical_count}")
            
            # Determinar qué gráfico mostrar
            chart_type = self.combo_chart_type.currentText()
            time_range = self.combo_time_range.currentText()
            
            # Limpiar el gráfico anterior
            self.dashboard_canvas.figure.clear()
            
            # Configurar el gráfico según el tipo seleccionado
            if chart_type == "Distribución por Tipo de Defecto":
                self.create_defect_type_chart(stats['defect_stats'])
            elif chart_type == "Severidad de Defectos":
                self.create_severity_chart(stats['severity_stats'])
            elif chart_type == "Estado de Control de Calidad":
                self.create_qc_status_chart(stats['qc_stats'])
            elif chart_type == "Mapa Térmico de Defectos":
                self.create_heatmap_chart(stats['heatmap_data'])
            elif chart_type == "Tendencia Temporal":
                # Obtener datos de tendencia según el rango de tiempo seleccionado
                days = 7 if "7 días" in time_range else 30 if "30 días" in time_range else 90 if "90 días" in time_range else 365
                trend_data = self.db.get_defect_trends(days)
                self.create_trend_chart(trend_data)
            elif chart_type == "Correlación Defectos-Eficiencia":
                correlation_data = self.db.get_efficiency_correlation()
                self.create_correlation_chart(correlation_data)
            
            # Actualizar el canvas
            self.dashboard_canvas.draw()
            
            if self.user_id:
                self.db.log_activity(self.user_id, "Actualizar Dashboard", f"Gráfico: {chart_type}, Periodo: {time_range}")
                
        except Exception as e:
            print(f"Error actualizando dashboard: {e}")
            self.dashboard_canvas.figure.clear()
            ax = self.dashboard_canvas.figure.add_subplot(111)
            ax.text(0.5, 0.5, f"Error cargando datos:\n{str(e)}", 
                   ha='center', va='center', fontsize=14, color=self.colors['text'])
            ax.set_facecolor(self.colors['background'])
            self.dashboard_canvas.draw()

    def create_defect_type_chart(self, defect_stats):
        """Crea gráfico de barras de defectos por tipo."""
        if not defect_stats:
            raise ValueError("No hay datos de defectos para mostrar")
        
        defect_types = [row[0] for row in defect_stats]
        quantities = [row[1] for row in defect_stats]
        avg_areas = [row[2] for row in defect_stats]
        
        ax = self.dashboard_canvas.figure.add_subplot(111)
        
        # Gráfico de barras para cantidades
        bars = ax.bar(defect_types, quantities, color=self.colors['bar_primary'], 
                     alpha=0.8, edgecolor=self.colors['grid'])
        
        # Añadir etiquetas de área promedio
        for i, (bar, avg_area) in enumerate(zip(bars, avg_areas)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{avg_area:.1f}', ha='center', va='bottom', 
                   fontsize=9, color=self.colors['text'])
        
        ax.set_xlabel('Tipo de Defecto', color=self.colors['text'], fontsize=12)
        ax.set_ylabel('Cantidad', color=self.colors['text'], fontsize=12)
        ax.set_title('Distribución de Defectos por Tipo', 
                    color=self.colors['text'], fontsize=14, fontweight='bold')
        ax.set_facecolor(self.colors['background'])
        ax.tick_params(axis='x', rotation=45, colors=self.colors['text'])
        ax.tick_params(axis='y', colors=self.colors['text'])
        ax.grid(True, alpha=0.3, color=self.colors['grid'])
        ax.spines['bottom'].set_color(self.colors['grid'])
        ax.spines['top'].set_color(self.colors['grid'])
        ax.spines['right'].set_color(self.colors['grid'])
        ax.spines['left'].set_color(self.colors['grid'])
        
        self.dashboard_canvas.figure.tight_layout()

    def create_severity_chart(self, severity_stats):
        """Crea gráfico de torta de severidad de defectos."""
        if not severity_stats:
            raise ValueError("No hay datos de severidad para mostrar")
        
        severities = [row[0] for row in severity_stats]
        quantities = [row[1] for row in severity_stats]
        
        # Colores específicos para cada severidad
        severity_colors = {
            'CRÍTICA': self.colors['critical'],
            'GRAVE': self.colors['danger'],
            'MODERADA': self.colors['warning'],
            'LEVE': self.colors['success'],
            'TOLERABLE': '#38BDF8',
            'NINGUNA': '#64748B'
        }
        
        colors = [severity_colors.get(str(severity).upper(), self.colors['bar_primary']) 
                 for severity in severities]
        
        ax = self.dashboard_canvas.figure.add_subplot(111)
        
        # Gráfico de torta
        wedges, texts, autotexts = ax.pie(quantities, labels=severities, colors=colors,
                                         autopct='%1.1f%%', startangle=90)
        
        # Configurar colores de texto
        for text in texts:
            text.set_color(self.colors['text'])
        for autotext in autotexts:
            autotext.set_color(self.colors['background'])
            autotext.set_fontweight('bold')
        
        ax.set_title('Distribución por Severidad', 
                    color=self.colors['text'], fontsize=14, fontweight='bold')
        ax.set_facecolor(self.colors['background'])
        
        # Añadir leyenda
        ax.legend(wedges, severities, title="Severidad", 
                 loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
                 facecolor=self.colors['background'],
                 edgecolor=self.colors['grid'],
                 labelcolor=self.colors['text'])

    def create_qc_status_chart(self, qc_stats):
        """Crea gráfico de barras horizontales para estado de control de calidad."""
        if not qc_stats:
            raise ValueError("No hay datos de control de calidad para mostrar")
        
        statuses = [row[0] for row in qc_stats]
        quantities = [row[1] for row in qc_stats]
        
        # Colores según el estado
        status_colors = []
        for status in statuses:
            status_str = str(status).upper()
            if "APROBADO" in status_str and "CONDICIÓN" not in status_str:
                status_colors.append(self.colors['success'])
            elif "CONDICIÓN" in status_str:
                status_colors.append(self.colors['warning'])
            elif "RECHAZADO" in status_str:
                status_colors.append(self.colors['danger'])
            else:
                status_colors.append(self.colors['bar_primary'])
        
        ax = self.dashboard_canvas.figure.add_subplot(111)
        
        # Gráfico de barras horizontales
        y_pos = range(len(statuses))
        bars = ax.barh(y_pos, quantities, color=status_colors, 
                      alpha=0.8, edgecolor=self.colors['grid'])
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(statuses, color=self.colors['text'])
        ax.set_xlabel('Cantidad', color=self.colors['text'], fontsize=12)
        ax.set_title('Estado de Control de Calidad', 
                    color=self.colors['text'], fontsize=14, fontweight='bold')
        ax.set_facecolor(self.colors['background'])
        ax.tick_params(axis='x', colors=self.colors['text'])
        
        # Añadir valores en las barras
        for bar, quantity in zip(bars, quantities):
            width = bar.get_width()
            ax.text(width + 0.1, bar.get_y() + bar.get_height()/2,
                   f'{quantity}', ha='left', va='center',
                   fontsize=10, color=self.colors['text'])
        
        ax.grid(True, alpha=0.3, color=self.colors['grid'], axis='x')
        ax.spines['bottom'].set_color(self.colors['grid'])
        ax.spines['top'].set_color(self.colors['grid'])
        ax.spines['right'].set_color(self.colors['grid'])
        ax.spines['left'].set_color(self.colors['grid'])
        
        self.dashboard_canvas.figure.tight_layout()

    def create_heatmap_chart(self, heatmap_data):
        """Crea mapa térmico de distribución espacial de defectos."""
        if not heatmap_data:
            raise ValueError("No hay datos de mapa térmico para mostrar")
        
        x_coords = [row[0] for row in heatmap_data]
        y_coords = [row[1] for row in heatmap_data]
        defect_types = [row[2] for row in heatmap_data]
        severities = [row[3] for row in heatmap_data]
        areas = [row[4] for row in heatmap_data]
        
        # Mapear severidad a tamaño del marcador
        severity_sizes = {
            'CRÍTICA': 150,
            'GRAVE': 100,
            'MODERADA': 70,
            'LEVE': 50,
            'TOLERABLE': 30,
            'NINGUNA': 20
        }
        
        sizes = [severity_sizes.get(str(severity).upper(), 50) for severity in severities]
        
        # Mapear tipo de defecto a color
        defect_colors = {
            'Burbuja': '#38BDF8',
            'Rayon': '#F59E0B',
            'Rotura': '#EF4444'
        }
        
        colors = [defect_colors.get(defect_type, '#94A3B8') for defect_type in defect_types]
        
        ax = self.dashboard_canvas.figure.add_subplot(111)
        
        # Gráfico de dispersión
        scatter = ax.scatter(x_coords, y_coords, s=sizes, c=colors, alpha=0.7, 
                           edgecolors='white', linewidths=0.5)
        
        ax.set_xlabel('Coordenada X (mm)', color=self.colors['text'], fontsize=12)
        ax.set_ylabel('Coordenada Y (mm)', color=self.colors['text'], fontsize=12)
        ax.set_title('Mapa Térmico de Defectos', 
                    color=self.colors['text'], fontsize=14, fontweight='bold')
        ax.set_facecolor(self.colors['background'])
        ax.tick_params(axis='x', colors=self.colors['text'])
        ax.tick_params(axis='y', colors=self.colors['text'])
        ax.grid(True, alpha=0.3, color=self.colors['grid'])
        ax.spines['bottom'].set_color(self.colors['grid'])
        ax.spines['top'].set_color(self.colors['grid'])
        ax.spines['right'].set_color(self.colors['grid'])
        ax.spines['left'].set_color(self.colors['grid'])
        
        # Crear leyenda personalizada
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#38BDF8', edgecolor='white', label='Burbuja'),
            Patch(facecolor='#F59E0B', edgecolor='white', label='Rayón'),
            Patch(facecolor='#EF4444', edgecolor='white', label='Rotura')
        ]
        
        ax.legend(handles=legend_elements, loc='upper right',
                 facecolor=self.colors['background'],
                 edgecolor=self.colors['grid'],
                 labelcolor=self.colors['text'])
        
        self.dashboard_canvas.figure.tight_layout()

    def create_trend_chart(self, trend_data):
        """Crea gráfico de línea temporal de tendencia de defectos."""
        if not trend_data:
            raise ValueError("No hay datos de tendencia para mostrar")
        
        dates = [row[0] for row in trend_data]
        quantities = [row[1] for row in trend_data]
        avg_areas = [row[2] for row in trend_data]
        
        ax = self.dashboard_canvas.figure.add_subplot(111)
        
        # Gráfico de línea para cantidad de defectos
        line1 = ax.plot(dates, quantities, label='Cantidad de Defectos', 
                       color=self.colors['bar_primary'], linewidth=2, marker='o')
        
        ax.set_xlabel('Fecha', color=self.colors['text'], fontsize=12)
        ax.set_ylabel('Cantidad de Defectos', color=self.colors['text'], fontsize=12)
        ax.set_title('Tendencia Temporal de Defectos', 
                    color=self.colors['text'], fontsize=14, fontweight='bold')
        ax.set_facecolor(self.colors['background'])
        ax.tick_params(axis='x', rotation=45, colors=self.colors['text'])
        ax.tick_params(axis='y', colors=self.colors['text'])
        ax.grid(True, alpha=0.3, color=self.colors['grid'])
        ax.spines['bottom'].set_color(self.colors['grid'])
        ax.spines['top'].set_color(self.colors['grid'])
        ax.spines['right'].set_color(self.colors['grid'])
        ax.spines['left'].set_color(self.colors['grid'])
        
        # Segundo eje Y para área promedio
        ax2 = ax.twinx()
        line2 = ax2.plot(dates, avg_areas, label='Área Promedio (mm²)', 
                        color=self.colors['danger'], linewidth=2, marker='s', linestyle='--')
        ax2.set_ylabel('Área Promedio (mm²)', color=self.colors['danger'], fontsize=12)
        ax2.tick_params(axis='y', colors=self.colors['danger'])
        
        # Combinar leyendas
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax.legend(lines, labels, loc='upper left',
                 facecolor=self.colors['background'],
                 edgecolor=self.colors['grid'],
                 labelcolor=self.colors['text'])
        
        self.dashboard_canvas.figure.tight_layout()

    def create_correlation_chart(self, correlation_data):
        """Crea gráfico de correlación entre defectos y eficiencia."""
        if not correlation_data or len(correlation_data) < 2:
            raise ValueError("No hay suficientes datos de correlación para mostrar")
        
        defects = [row[1] for row in correlation_data]
        efficiencies = [row[3] for row in correlation_data]
        waste_areas = [row[4] for row in correlation_data]
        
        # Calcular correlación
        if len(defects) > 1:
            correlation_coef = np.corrcoef(defects, efficiencies)[0, 1]
        else:
            correlation_coef = 0
        
        ax = self.dashboard_canvas.figure.add_subplot(111)
        
        # Gráfico de dispersión con tamaño según merma
        scatter = ax.scatter(defects, efficiencies, s=[w/10 for w in waste_areas], 
                           c=efficiencies, cmap='viridis', alpha=0.7, 
                           edgecolors='white', linewidths=0.5)
        
        # Línea de regresión
        if len(defects) > 1 and len(efficiencies) > 1:
            z = np.polyfit(defects, efficiencies, 1)
            p = np.poly1d(z)
            ax.plot(defects, p(defects), "r--", alpha=0.8, linewidth=2,
                   label=f'Correlación: {correlation_coef:.2f}')
        
        ax.set_xlabel('Número de Defectos', color=self.colors['text'], fontsize=12)
        ax.set_ylabel('Eficiencia de Corte (%)', color=self.colors['text'], fontsize=12)
        ax.set_title('Correlación: Defectos vs Eficiencia de Corte', 
                    color=self.colors['text'], fontsize=14, fontweight='bold')
        ax.set_facecolor(self.colors['background'])
        ax.tick_params(axis='x', colors=self.colors['text'])
        ax.tick_params(axis='y', colors=self.colors['text'])
        ax.grid(True, alpha=0.3, color=self.colors['grid'])
        ax.spines['bottom'].set_color(self.colors['grid'])
        ax.spines['top'].set_color(self.colors['grid'])
        ax.spines['right'].set_color(self.colors['grid'])
        ax.spines['left'].set_color(self.colors['grid'])
        
        # Barra de color para eficiencia
        cbar = self.dashboard_canvas.figure.colorbar(scatter, ax=ax)
        cbar.set_label('Eficiencia (%)', color=self.colors['text'])
        cbar.ax.tick_params(colors=self.colors['text'])
        
        # Leyenda para tamaño de puntos (merma)
        from matplotlib.patches import Circle
        legend_elements = [
            Circle((0, 0), radius=5, facecolor='gray', alpha=0.7, 
                   label='Merma pequeña (< 100 mm²)'),
            Circle((0, 0), radius=15, facecolor='gray', alpha=0.7, 
                   label='Merma media (100-500 mm²)'),
            Circle((0, 0), radius=30, facecolor='gray', alpha=0.7, 
                   label='Merma grande (> 500 mm²)')
        ]
        
        ax.legend(handles=legend_elements, loc='upper right',
                 facecolor=self.colors['background'],
                 edgecolor=self.colors['grid'],
                 labelcolor=self.colors['text'])
        
        self.dashboard_canvas.figure.tight_layout()

    # --- GESTIÓN DE TEMAS (MODO OSCURO / MODO CLARO) Y ANIMACIONES ---

    def _init_theme_stylesheets(self):
        """Inicializa las hojas de estilo completas para modo oscuro y claro."""
        self._dark_theme_stylesheet = """
            QMainWindow { background-color: #0B0E14; }
            QWidget { color: #E0E6ED; font-family: 'Segoe UI', Arial, sans-serif; }
            QLabel { color: #E0E6ED; }
            QPushButton {
                background-color: #1A73E8; color: #FFFFFF;
                border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px;
                border: none;
            }
            QPushButton:hover { background-color: #1557B0; }
            QPushButton:disabled { background-color: #1E293B; color: #64748B; }
            QTabWidget::pane { border: 1px solid #1E293B; background: #0F1520; border-radius: 8px; }
            QTabBar::tab {
                background: #0B0E14; color: #94A3B8; padding: 12px 25px; margin-right: 2px;
                font-size: 14px; font-weight: bold; border: 1px solid #1E293B; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #0F1520; color: #FFFFFF; border-top: 3px solid #1A73E8;
            }
            QTableWidget { 
                background-color: #0F1520; color: #E0E6ED; 
                gridline-color: #1E293B; border: 1px solid #1E293B; 
                border-radius: 8px; font-size: 13px;
            }
            QTableWidget::item { padding: 5px; border-bottom: 1px solid #1E293B; }
            QHeaderView::section { 
                background-color: #1E293B; color: #FFFFFF; 
                font-weight: bold; padding: 8px; border: none; 
                border-right: 1px solid #0F1520;
            }
            QComboBox {
                background-color: #0F1520; color: #E0E6ED;
                border: 1px solid #1E293B; border-radius: 6px;
                padding: 7px 12px; font-size: 13px; font-weight: bold;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #0F1520; color: #E0E6ED;
                selection-background-color: #1A73E8; selection-color: #FFFFFF;
            }
            QGroupBox {
                background-color: #0F1520; border: 1px solid #1E293B;
                border-radius: 8px; margin-top: 10px; padding-top: 10px;
                font-weight: bold; color: #E0E6ED;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px;
                padding: 0 5px; color: #94A3B8;
            }
        """

        self._light_theme_stylesheet = """
            QMainWindow { background-color: #F8FAFC; }
            QWidget { color: #0F172A; font-family: 'Segoe UI', Arial, sans-serif; }
            QLabel { color: #0F172A; }
            QPushButton {
                background-color: #1A73E8; color: #FFFFFF;
                border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px;
                border: none;
            }
            QPushButton:hover { background-color: #1557B0; }
            QPushButton:disabled { background-color: #CBD5E1; color: #94A3B8; }
            QTabWidget::pane { border: 1px solid #CBD5E1; background: #FFFFFF; border-radius: 8px; }
            QTabBar::tab {
                background: #E2E8F0; color: #475569; padding: 12px 25px; margin-right: 2px;
                font-size: 14px; font-weight: bold; border: 1px solid #CBD5E1; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF; color: #1A73E8; border-top: 3px solid #1A73E8;
            }
            QTableWidget { 
                background-color: #FFFFFF; color: #0F172A; 
                gridline-color: #E2E8F0; border: 1px solid #CBD5E1; 
                border-radius: 8px; font-size: 13px;
            }
            QTableWidget::item { padding: 5px; border-bottom: 1px solid #E2E8F0; }
            QHeaderView::section { 
                background-color: #F1F5F9; color: #0F172A; 
                font-weight: bold; padding: 8px; border: none; 
                border-right: 1px solid #E2E8F0;
            }
            QComboBox {
                background-color: #FFFFFF; color: #0F172A;
                border: 1px solid #CBD5E1; border-radius: 6px;
                padding: 7px 12px; font-size: 13px; font-weight: bold;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF; color: #0F172A;
                selection-background-color: #1A73E8; selection-color: #FFFFFF;
            }
            QGroupBox {
                background-color: #FFFFFF; border: 1px solid #CBD5E1;
                border-radius: 8px; margin-top: 10px; padding-top: 10px;
                font-weight: bold; color: #0F172A;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px;
                padding: 0 5px; color: #475569;
            }
        """

        self._dark_colors = {
            'background': '#0F1520',
            'text': '#E0E6ED',
            'grid': '#1E293B',
            'bar_primary': '#1A73E8',
            'bar_secondary': '#38BDF8',
            'success': '#10B981',
            'warning': '#F59E0B',
            'danger': '#EF4444',
            'critical': '#DC2626'
        }

        self._light_colors = {
            'background': '#FFFFFF',
            'text': '#0F172A',
            'grid': '#E2E8F0',
            'bar_primary': '#1A73E8',
            'bar_secondary': '#0284C7',
            'success': '#059669',
            'warning': '#D97706',
            'danger': '#DC2626',
            'critical': '#B91C1C'
        }

        self.colors = self._dark_colors

    def apply_theme(self, theme_name):
        """Aplica el tema seleccionado (dark o light) a toda la aplicación y sus gráficos."""
        if theme_name == "light":
            self.current_theme = "light"
            self.setStyleSheet(self._light_theme_stylesheet)
            self.colors = self._light_colors
            if hasattr(self, 'vision_display'):
                self.vision_display.setStyleSheet("background-color: #FFFFFF; border: 2px dashed #CBD5E1; font-size: 16px; color: #475569;")
            if hasattr(self, 'optimization_display'):
                self.optimization_display.setStyleSheet("background-color: #FFFFFF; border: 2px dashed #CBD5E1; font-size: 16px; color: #475569;")
            if hasattr(self, 'qc_card'):
                self.qc_card.setStyleSheet("QWidget { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; }")
            if hasattr(self, 'metric_widgets'):
                for mw in self.metric_widgets:
                    mw.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #0F172A; background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 6px; padding: 10px 15px; min-width: 180px; text-align: center; }")
            if hasattr(self, 'dashboard_canvas'):
                self.dashboard_canvas.figure.patch.set_facecolor('#FFFFFF')
                try:
                    self.refresh_dashboard()
                except Exception:
                    pass
        else:
            self.current_theme = "dark"
            self.setStyleSheet(self._dark_theme_stylesheet)
            self.colors = self._dark_colors
            if hasattr(self, 'vision_display'):
                self.vision_display.setStyleSheet("background-color: #0B0E14; border: 2px dashed #1E293B; font-size: 16px; color: #E0E6ED;")
            if hasattr(self, 'optimization_display'):
                self.optimization_display.setStyleSheet("background-color: #0B0E14; border: 2px dashed #1E293B; font-size: 16px; color: #E0E6ED;")
            if hasattr(self, 'qc_card'):
                self.qc_card.setStyleSheet("QWidget { background-color: #0F1520; border: 1px solid #1E293B; border-radius: 8px; }")
            if hasattr(self, 'metric_widgets'):
                for mw in self.metric_widgets:
                    mw.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #E0E6ED; background-color: #1E293B; border-radius: 6px; padding: 10px 15px; min-width: 180px; text-align: center; }")
            if hasattr(self, 'dashboard_canvas'):
                self.dashboard_canvas.figure.patch.set_facecolor('#0F1520')
                try:
                    self.refresh_dashboard()
                except Exception:
                    pass

    def on_theme_selector_changed(self, index):
        """Manejador del cambio de opción en el selector de modo oscuro / claro."""
        if index == 1:
            self.apply_theme("light")
        else:
            self.apply_theme("dark")

    def animate_tab_transition(self, index):
        """Animación de transición suave (fade-in) entre pestañas."""
        widget = self.tabs.widget(index)
        if widget is not None:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(240)
            anim.setStartValue(0.15)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            
            # Mantener referencias activas para evitar recolección de basura
            self._tab_animation = anim
            self._tab_effect = effect

    def closeEvent(self, event):
        """Asegura liberar los recursos de la camara web al cerrar la aplicacion."""
        if hasattr(self, 'camera_timer') and self.camera_timer.isActive():
            self.camera_timer.stop()
        if hasattr(self, 'cap') and self.cap is not None and self.cap.isOpened():
            self.cap.release()
        event.accept()

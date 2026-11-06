import numpy as np

class GlassSheet:
    """
    Representación matemática de la lámina de vidrio mediante una cuadrícula (Grid 2D).
    Esto nos permite discretizar el espacio en una matriz proporcional y manejar la lógica de colisiones 
    con las imperfecciones (defectos) detectadas por la visión artificial.
    """
    GRID_MODALITY = 20

    @staticmethod
    def validate_sheet_dimensions(width, height):
        """
        Valida que las dimensiones de la lámina estén dentro de los parámetros permitidos.
        Retorna (es_valido, mensaje, unidad_etiqueta).
        """
        try:
            w = int(width)
            h = int(height)
        except (ValueError, TypeError):
            return False, "Las dimensiones de la lámina deben ser valores numéricos enteros.", ""

        if w <= 0 or h <= 0:
            return False, "El ancho y el alto de la lámina deben ser mayores a cero.", ""

        if w <= 20 and h <= 20:
            return True, f"Tamaño de lámina validado correctamente ({w} x {h}).", "u"

        if (w < 100 or h < 100) and (w > 20 or h > 20):
            return False, f"Medida de lámina inválida ({w} x {h}). Verifique las dimensiones ingresadas.", ""

        if w > 2000 or h > 2000:
            return False, f"Medida de lámina fuera del rango permitido ({w} x {h}).", ""

        return True, f"Tamaño de lámina validado correctamente ({w} x {h} mm).", "mm"

    def __init__(self, width, height, resolution=None):
        self.width = int(width)
        self.height = int(height)
        if self.width <= 20 and self.height <= 20:
            self.resolution = 1
        elif resolution is not None:
            self.resolution = max(1, int(resolution))
        else:
            self.resolution = max(1, int(min(self.width, self.height) / 200)) if min(self.width, self.height) >= 200 else 1
        
        # Grid booleano: 0 = Espacio Libre, 1 = Espacio Ocupado o Defectuoso
        cols = max(1, int(np.ceil(self.width / self.resolution)))
        rows = max(1, int(np.ceil(self.height / self.resolution)))
        self.grid = np.zeros((rows, cols), dtype=np.int8)
        
    def add_defect(self, x, y, w, h):
        """
        Marca un área rectangular de la lámina (Bounding Box de la falla) 
        como zona prohibida para el corte.
        """
        rows, cols = self.grid.shape
        r_start = max(0, min(rows - 1, int(y / self.resolution)))
        r_end = max(r_start + 1, min(rows, int(np.ceil((y + h) / self.resolution))))
        c_start = max(0, min(cols - 1, int(x / self.resolution)))
        c_end = max(c_start + 1, min(cols, int(np.ceil((x + w) / self.resolution))))
        
        # Bloqueamos esa zona marcándola con 1
        self.grid[r_start:r_end, c_start:c_end] = 1
        
    def can_place(self, piece_w, piece_h, x, y):
        """Verifica algorítmicamente si una pieza de corte entra en la coordenada."""
        r_start = int(y / self.resolution)
        r_end = int((y + piece_h) / self.resolution)
        c_start = int(x / self.resolution)
        c_end = int((x + piece_w) / self.resolution)
        
        # Verificamos desbordamiento físico (fuera de la lámina madre)
        if r_end > self.grid.shape[0] or c_end > self.grid.shape[1]:
            return False
            
        # Extraemos la sub-matriz de la lámina y verificamos si hay algún 1 (Ocupado/Defecto)
        sub_grid = self.grid[r_start:r_end, c_start:c_end]
        if np.any(sub_grid == 1):
            return False # Hay colisión
            
        return True
        
    def place_piece(self, piece_w, piece_h, x, y):
        """Coloca la pieza y quema (marca) el área en el grid para no solapar la siguiente."""
        if self.can_place(piece_w, piece_h, x, y):
            r_start = int(y / self.resolution)
            r_end = int((y + piece_h) / self.resolution)
            c_start = int(x / self.resolution)
            c_end = int((x + piece_w) / self.resolution)
            
            self.grid[r_start:r_end, c_start:c_end] = 1
            return True
        return False

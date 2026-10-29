import numpy as np

class GlassSheet:
    """
    Representación matemática de la lámina de vidrio mediante una cuadrícula (Grid 2D).
    Esto nos permite discretizar el espacio y manejar la lógica de colisiones 
    con las imperfecciones (defectos) detectadas por la visión artificial.
    """
    def __init__(self, width, height, resolution=10):
        # resolution = 10 significa que cada celda de la matriz equivale a 10x10 milímetros.
        # Discretizar el grid acelera exponencialmente el algoritmo de búsqueda.
        self.width = width
        self.height = height
        self.resolution = resolution
        
        # Grid booleano: 0 = Espacio Libre, 1 = Espacio Ocupado o Defectuoso
        cols = int(width / resolution)
        rows = int(height / resolution)
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

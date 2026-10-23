class BinPacker:
    """
    Algoritmo de Optimización Heurística para resolver el problema de empaque (2D Bin Packing).
    Utiliza una estrategia FFD (First-Fit Decreasing) adaptada a mapas de colisión espaciales.
    """
    def __init__(self, glass_sheet):
        self.sheet = glass_sheet
        self.placed_pieces = []
        
    def pack(self, pieces):
        """
        pieces: Lista de diccionarios con la estructura {'id': string, 'w': int, 'h': int}
        """
        # 1. Heurística FFD: Ordenamos las piezas solicitadas por su área (de mayor a menor).
        # Colocar primero las piezas más grandes reduce drásticamente el porcentaje de merma.
        pieces_sorted = sorted(pieces, key=lambda p: p['w'] * p['h'], reverse=True)
        
        for piece in pieces_sorted:
            placed = False
            # 2. Escaneamos la lámina buscando el primer hueco disponible (estrategia Bottom-Left).
            # Para no evaluar píxel por píxel (muy costoso), usamos un salto (stride) basado en la resolución.
            stride = self.sheet.resolution
            
            for y in range(0, self.sheet.height, stride):
                if placed: break
                for x in range(0, self.sheet.width, stride):
                    
                    # Intentar acomodar la pieza en su orientación original
                    if self.sheet.place_piece(piece['w'], piece['h'], x, y):
                        self.placed_pieces.append({
                            'id': piece['id'], 'x': x, 'y': y, 
                            'w': piece['w'], 'h': piece['h'], 'rotated': False
                        })
                        placed = True
                        break
                        
                    # Si no cabe, intentar acomodar la pieza rotada a 90 grados
                    elif self.sheet.place_piece(piece['h'], piece['w'], x, y):
                        self.placed_pieces.append({
                            'id': piece['id'], 'x': x, 'y': y, 
                            'w': piece['h'], 'h': piece['w'], 'rotated': True
                        })
                        placed = True
                        break
                        
            if not placed:
                print(f"Alerta: La pieza {piece['id']} no cabe debido a las fallas o falta de área útil.")
                
        return self.placed_pieces

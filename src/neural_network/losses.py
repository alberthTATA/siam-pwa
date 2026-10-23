import numpy as np

class Loss_MeanSquaredError:
    """
    Error Cuadrático Medio (MSE).
    Calcula qué tan alejadas están las predicciones de la red respecto a los valores reales (etiquetas).
    """
    def forward(self, y_pred, y_true):
        # Guardamos predicciones y valores reales
        self.y_pred = y_pred
        self.y_true = y_true
        
        # MSE = media((y_true - y_pred)^2)
        # Calculamos la pérdida por cada muestra en el lote (batch)
        sample_losses = np.mean((y_true - y_pred)**2, axis=-1)
        # Retornamos el promedio total del lote
        data_loss = np.mean(sample_losses)
        return data_loss
        
    def backward(self, y_pred, y_true):
        # Cantidad de muestras en el lote (batch size)
        samples = len(y_pred)
        # Cantidad de salidas (neuronas en la capa final)
        outputs = len(y_pred[0])
        
        # La derivada matemática del Error Cuadrático Medio respecto a las predicciones es:
        # dMSE/dPred = -2 * (Verdadero - Predicción) / n_salidas
        self.dinputs = -2 * (y_true - y_pred) / outputs
        
        # Dividimos por el tamaño del lote (samples) para normalizar el gradiente.
        # Así aseguramos que lotes más grandes no den pasos de aprendizaje exagerados.
        self.dinputs = self.dinputs / samples
        return self.dinputs

class Optimizer_SGD:
    """
    Optimizador: Stochastic Gradient Descent (SGD).
    Actualiza los parámetros (pesos y sesgos) empujándolos en la dirección opuesta al gradiente (hacia el mínimo del error).
    """
    def __init__(self, learning_rate=1.0):
        # La tasa de aprendizaje controla qué tan grandes son los pasos que damos al actualizar.
        self.learning_rate = learning_rate
        
    def update_params(self, layer):
        # Nuevos Pesos = Pesos Actuales - (Tasa de Aprendizaje * Gradiente de Pesos)
        layer.weights += -self.learning_rate * layer.dweights
        # Nuevos Sesgos = Sesgos Actuales - (Tasa de Aprendizaje * Gradiente de Sesgos)
        layer.biases += -self.learning_rate * layer.dbiases

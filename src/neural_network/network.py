class NeuralNetwork:
    """
    Orquestador de la Red Neuronal Artificial (Multicapa).
    Gestiona la arquitectura de capas, el paso hacia adelante (Forward),
    hacia atrás (Backpropagation) y el ciclo de entrenamiento.
    """
    def __init__(self):
        # Lista secuencial para guardar las capas (Dense) y funciones de activación
        self.layers = []
        self.loss_function = None
        self.optimizer = None
        
    def add(self, layer):
        """Añade una capa o función de activación a la red."""
        self.layers.append(layer)
        
    def set(self, loss, optimizer):
        """Establece la función de pérdida y el optimizador (SGD, etc.)."""
        self.loss_function = loss
        self.optimizer = optimizer
        
    def forward(self, X):
        """
        Forward Propagation.
        Toma las entradas X iniciales y las pasa secuencialmente por todas las capas.
        """
        self.output = X
        for layer in self.layers:
            self.output = layer.forward(self.output)
        return self.output
        
    def backward(self, output, y_true):
        """
        Backpropagation.
        Calcula el error final y propaga sus derivadas (gradientes) de reversa
        capa por capa aplicando la regla de la cadena.
        """
        # 1. Calculamos el gradiente inicial a partir de la función de pérdida
        dinputs = self.loss_function.backward(output, y_true)
        
        # 2. Propagamos el gradiente hacia atrás por todas las capas (en reversa)
        for layer in reversed(self.layers):
            dinputs = layer.backward(dinputs)
            
    def update_weights(self):
        """
        Actualiza los parámetros matemáticos usando el Optimizador configurado.
        """
        for layer in self.layers:
            if hasattr(layer, 'weights'):
                self.optimizer.update_params(layer)

    def save_weights(self, filepath):
        """Guarda los pesos y sesgos de la red en un archivo."""
        import pickle
        parameters = []
        for layer in self.layers:
            if hasattr(layer, 'weights'):
                parameters.append({'weights': layer.weights, 'biases': layer.biases})
        with open(filepath, 'wb') as f:
            pickle.dump(parameters, f)
            
    def load_weights(self, filepath):
        """Carga los pesos y sesgos previamente entrenados."""
        import pickle
        with open(filepath, 'rb') as f:
            parameters = pickle.load(f)
        idx = 0
        for layer in self.layers:
            if hasattr(layer, 'weights'):
                layer.weights = parameters[idx]['weights']
                layer.biases = parameters[idx]['biases']
                idx += 1

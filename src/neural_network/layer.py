import numpy as np

class Layer_Dense:
    """
    Capa Densa (Totalmente Conectada).
    Cada neurona se conecta a todas las neuronas de la capa anterior.
    """
    def __init__(self, n_inputs, n_neurons):
        # Inicializamos los pesos (weights) con distribución normal aleatoria.
        # Multiplicamos por 0.01 para evitar que valores grandes saturen las funciones de activación.
        # La dimensión es (n_inputs, n_neurons) para optimizar el producto punto.
        self.weights = 0.01 * np.random.randn(n_inputs, n_neurons)
        # Inicializamos los sesgos (biases) en ceros.
        # La dimensión es (1, n_neurons) para sumarse adecuadamente.
        self.biases = np.zeros((1, n_neurons))
        
    def forward(self, inputs):
        # Guardamos las entradas originales porque las necesitaremos para calcular las derivadas en el backprop
        self.inputs = inputs
        # Ecuación de la neurona: Salida = (Entradas · Pesos) + Sesgos
        self.output = np.dot(inputs, self.weights) + self.biases
        return self.output
        
    def backward(self, dvalues):
        # dvalues son los gradientes que vienen de la capa siguiente (o la función de pérdida).
        
        # Gradientes sobre parámetros (Pesos y Sesgos) - Necesarios para actualizar (aprender)
        self.dweights = np.dot(self.inputs.T, dvalues)
        self.dbiases = np.sum(dvalues, axis=0, keepdims=True)
        
        # Gradiente sobre las entradas - Necesario para propagar el error a la capa anterior
        self.dinputs = np.dot(dvalues, self.weights.T)
        
        return self.dinputs

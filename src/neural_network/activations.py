import numpy as np

class ActivationFunction:
    """Clase base abstracta para funciones de activación."""
    def forward(self, inputs):
        raise NotImplementedError
    
    def backward(self, dvalues):
        raise NotImplementedError

class Activation_ReLU(ActivationFunction):
    """
    Rectified Linear Unit (ReLU).
    F(x) = max(0, x)
    Ideal para las capas ocultas ya que mitiga el problema del gradiente desvaneciente.
    """
    def forward(self, inputs):
        # Guardamos los inputs para calcular la derivada después en el backprop
        self.inputs = inputs
        # ReLU: Si es menor a 0, se vuelve 0. Si es mayor, se mantiene.
        self.output = np.maximum(0, inputs)
        return self.output
        
    def backward(self, dvalues):
        # Hacemos una copia de los gradientes que vienen de la capa siguiente (Regla de la cadena)
        self.dinputs = dvalues.copy()
        # La derivada de ReLU es 1 si x > 0, y 0 si x <= 0.
        # Por regla de la cadena: dinputs = dvalues * derivada_relu
        self.dinputs[self.inputs <= 0] = 0
        return self.dinputs

class Activation_Sigmoid(ActivationFunction):
    """
    Función Sigmoide.
    F(x) = 1 / (1 + e^-x)
    Útil para capas de salida donde requerimos probabilidades (0 a 1).
    """
    def forward(self, inputs):
        # Evitamos desbordamientos (overflows) matemáticos restringiendo los límites
        inputs_clipped = np.clip(inputs, -500, 500)
        self.output = 1 / (1 + np.exp(-inputs_clipped))
        return self.output
        
    def backward(self, dvalues):
        # La derivada de la sigmoide respecto a x es: sigmoide(x) * (1 - sigmoide(x))
        # Aplicamos la regla de la cadena multiplicando por dvalues
        self.dinputs = dvalues * (self.output * (1 - self.output))
        return self.dinputs

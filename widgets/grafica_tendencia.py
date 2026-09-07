"""
Grafica de tendencia simple (linea), dibujada a mano con canvas de Kivy.
No usa librerias externas (matplotlib, etc.) para mantener el proyecto
liviano y evitar dependencias extra al empaquetar para Android.
"""

from kivy.factory import Factory
from kivy.graphics import Color, Line
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.uix.widget import Widget


class GraficaTendencia(Widget):
    """
    Dibuja una linea de tendencia a partir de una lista de valores numericos
    (mas antiguo primero, mas reciente al final). None se ignora. Se
    redibuja sola cuando cambian los valores, la posicion o el tamano.
    """

    valores = ListProperty([])
    color_linea = ListProperty([0.05, 0.35, 0.5, 1])

    PADDING = dp(20)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redibujar, size=self._redibujar, valores=self._redibujar)

    def _redibujar(self, *args):
        self.canvas.clear()
        validos = [v for v in self.valores if v is not None]
        if len(validos) < 2:
            return  # hace falta al menos 2 puntos para trazar una linea

        minimo = min(validos)
        maximo = max(validos)
        rango = (maximo - minimo) or 1  # evita division entre 0 si todos son iguales

        x0 = self.x + self.PADDING
        x1 = self.right - dp(8)
        y0 = self.y + self.PADDING
        y1 = self.top - dp(8)

        ancho = max(x1 - x0, 1)
        alto = max(y1 - y0, 1)
        paso_x = ancho / (len(validos) - 1)

        puntos = []
        for i, valor in enumerate(validos):
            x = x0 + i * paso_x
            y = y0 + ((valor - minimo) / rango) * alto
            puntos.extend([x, y])

        with self.canvas:
            Color(0.75, 0.75, 0.75, 1)
            Line(points=[x0, y0, x1, y0], width=1)  # linea base de referencia

            Color(*self.color_linea)
            Line(points=puntos, width=dp(2), joint="round")

            for i in range(0, len(puntos), 2):
                Line(circle=(puntos[i], puntos[i + 1], dp(3)), width=dp(2))


Factory.register("GraficaTendencia", cls=GraficaTendencia)

"""
Grafica de tendencia simple (linea), dibujada a mano con canvas de Kivy.
No usa librerias externas (matplotlib, etc.) para mantener el proyecto
liviano y evitar dependencias extra al empaquetar para Android.

Ademas de la linea, muestra:
- Eje Y: 3 referencias (maximo arriba, medio al centro, minimo abajo) con
  una guia tenue en cada una, y un rotulo arriba a la izquierda con el
  nombre y la unidad de la variable (p.ej. "CE (mS/cm)").
- Eje X: la hora (hora LOCAL del dispositivo, no UTC) debajo de cada punto
  -con fecha corta incluida si los datos abarcan mas de un dia-, mostrando
  solo algunas etiquetas si hay demasiados puntos para que no se
  superpongan, y un rotulo "Hora" centrado debajo.

El canvas de Kivy no puede dibujar texto directamente, asi que todos los
numeros y rotulos se agregan como Label hijos posicionados a mano.
"""

from datetime import datetime, timezone

from kivy.factory import Factory
from kivy.graphics import Color, Line
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.label import Label
from kivy.uix.widget import Widget

_COLOR_TEXTO_EJE = (0.45, 0.45, 0.45, 1)
_COLOR_GUIA = (0.85, 0.85, 0.85, 1)


class GraficaTendencia(Widget):
    """
    Dibuja una linea de tendencia a partir de una lista de valores numericos
    (mas antiguo primero, mas reciente al final). None se ignora. Se
    redibuja sola cuando cambian los valores, la posicion o el tamano.

    fechas (opcional): lista de fechas ISO8601 UTC ("...Z"), mismo indice
    que valores, usada para las etiquetas de hora del eje X. Si no coincide
    en longitud con valores, simplemente no se muestran esas etiquetas.

    rotulo_eje_y: texto del rotulo del eje Y, p.ej. "CE (mS/cm)" o "pH"
    (sin unidad). decimales: cuantos decimales mostrar en los numeros del
    eje Y (1 para pH/CE, 0 para el resto) - lo fija quien usa el widget
    (ver screens/detalle_screen.py), porque depende de que variable es.
    """

    valores = ListProperty([])
    fechas = ListProperty([])
    color_linea = ListProperty([0.05, 0.35, 0.5, 1])
    rotulo_eje_y = StringProperty("")
    decimales = NumericProperty(1)

    # Espacio reservado alrededor del area de trazado: a la izquierda para
    # los numeros del eje Y, arriba para el rotulo del eje Y, abajo para
    # las horas del eje X y el rotulo "Hora".
    PADDING_IZQUIERDA = dp(46)
    PADDING_DERECHA = dp(10)
    PADDING_ARRIBA = dp(20)
    PADDING_ABAJO = dp(30)

    # Ancho minimo que se le reserva a cada etiqueta de hora en el eje X,
    # para decidir cuantas mostrar sin que se superpongan.
    ANCHO_POR_ETIQUETA_HORA = dp(58)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._etiquetas = []
        self.bind(
            pos=self._redibujar,
            size=self._redibujar,
            valores=self._redibujar,
            fechas=self._redibujar,
            rotulo_eje_y=self._redibujar,
            decimales=self._redibujar,
        )

    def _limpiar_etiquetas(self):
        for etiqueta in self._etiquetas:
            self.remove_widget(etiqueta)
        self._etiquetas = []

    def _agregar_etiqueta(self, texto, x, y, tamano, ancla="center"):
        """Agrega un Label como hijo, posicionado a mano en (x, y) segun 'ancla'
        (que borde/punto del texto cae exactamente en esa coordenada)."""
        etiqueta = Label(
            text=texto,
            font_size=tamano,
            color=_COLOR_TEXTO_EJE,
            size_hint=(None, None),
        )
        etiqueta.texture_update()
        etiqueta.size = etiqueta.texture_size
        if ancla == "right":
            etiqueta.pos = (x - etiqueta.width, y - etiqueta.height / 2)
        elif ancla == "left":
            etiqueta.pos = (x, y - etiqueta.height / 2)
        else:
            etiqueta.pos = (x - etiqueta.width / 2, y - etiqueta.height / 2)
        self.add_widget(etiqueta)
        self._etiquetas.append(etiqueta)

    def _formatear_num(self, valor):
        return f"{valor:.{self.decimales}f}"

    @staticmethod
    def _formatear_hora(fecha_iso, multi_dia):
        """Convierte una fecha ISO8601 UTC ("2026-03-01T10:15:00Z") a la hora
        LOCAL del dispositivo, formateada "10:15" (o "01/03 10:15" si
        multi_dia). "--:--" si la fecha no tiene el formato esperado."""
        try:
            momento_utc = datetime.strptime(fecha_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except (TypeError, ValueError):
            return "--:--"
        momento_local = momento_utc.astimezone()  # a la zona horaria del dispositivo
        return momento_local.strftime("%d/%m %H:%M" if multi_dia else "%H:%M")

    @staticmethod
    def _elegir_indices_etiquetas(cantidad, maximo):
        """Elige que indices (de 0 a cantidad-1) llevan etiqueta de hora,
        siempre incluyendo el primero y el ultimo, repartiendo el resto lo
        mas parejo posible, para que no se superpongan."""
        if cantidad <= maximo:
            return list(range(cantidad))
        paso = (cantidad - 1) / (maximo - 1)
        return sorted({round(i * paso) for i in range(maximo)})

    def _redibujar(self, *args):
        self.canvas.clear()
        self._limpiar_etiquetas()

        x0 = self.x + self.PADDING_IZQUIERDA
        x1 = self.right - self.PADDING_DERECHA
        y0 = self.y + self.PADDING_ABAJO
        y1 = self.top - self.PADDING_ARRIBA
        ancho = max(x1 - x0, 1)
        alto = max(y1 - y0, 1)

        if self.rotulo_eje_y:
            self._agregar_etiqueta(
                self.rotulo_eje_y, self.x, self.top - dp(9), "11sp", ancla="left"
            )

        if len(self.fechas) == len(self.valores):
            pares = list(zip(self.valores, self.fechas))
        else:
            pares = [(v, None) for v in self.valores]
        validos = [(v, f) for v, f in pares if v is not None]

        if not validos:
            self._agregar_etiqueta(
                "Sin mediciones para mostrar", (x0 + x1) / 2, (y0 + y1) / 2, "12sp"
            )
            return

        valores_validos = [v for v, _ in validos]
        minimo = min(valores_validos)
        maximo = max(valores_validos)
        if maximo == minimo:
            # Todos los valores son iguales (o hay un solo punto): se
            # ensancha un poco el rango para que la linea/el punto no
            # quede pegado al borde ni se divida entre cero.
            centro = minimo
            margen = abs(centro) * 0.1 or 1
            minimo, maximo = centro - margen, centro + margen
        medio = (minimo + maximo) / 2
        rango = maximo - minimo

        def _y_de(valor):
            return y0 + ((valor - minimo) / rango) * alto

        for valor_referencia, y_referencia in ((maximo, y1), (medio, (y0 + y1) / 2), (minimo, y0)):
            with self.canvas:
                Color(*_COLOR_GUIA)
                Line(points=[x0, y_referencia, x1, y_referencia], width=1)
            self._agregar_etiqueta(
                self._formatear_num(valor_referencia), x0 - dp(6), y_referencia, "11sp", ancla="right"
            )

        if len(validos) == 1:
            valor, fecha = validos[0]
            x_centro = (x0 + x1) / 2
            with self.canvas:
                Color(*self.color_linea)
                Line(circle=(x_centro, _y_de(valor), dp(3.5)), width=dp(2))
            self._agregar_etiqueta("Hora", (x0 + x1) / 2, self.y + dp(6), "10sp")
            if fecha:
                self._agregar_etiqueta(
                    self._formatear_hora(fecha, multi_dia=False), x_centro, self.y + dp(20), "10sp"
                )
            return

        paso_x = ancho / (len(validos) - 1)
        puntos = []
        for i, (valor, _fecha) in enumerate(validos):
            puntos.extend([x0 + i * paso_x, _y_de(valor)])

        with self.canvas:
            Color(*self.color_linea)
            Line(points=puntos, width=dp(2), joint="round")
            for i in range(0, len(puntos), 2):
                Line(circle=(puntos[i], puntos[i + 1], dp(3)), width=dp(2))

        self._agregar_etiqueta("Hora", (x0 + x1) / 2, self.y + dp(6), "10sp")

        fecha_primera = validos[0][1]
        fecha_ultima = validos[-1][1]
        multi_dia = bool(
            fecha_primera and fecha_ultima and fecha_primera[:10] != fecha_ultima[:10]
        )

        maximo_etiquetas = max(2, int(ancho / self.ANCHO_POR_ETIQUETA_HORA))
        indices_con_etiqueta = self._elegir_indices_etiquetas(len(validos), maximo_etiquetas)
        ultimo_indice = len(validos) - 1
        for i in indices_con_etiqueta:
            fecha = validos[i][1]
            if not fecha:
                continue
            x = x0 + i * paso_x
            ancla = "left" if i == 0 else "right" if i == ultimo_indice else "center"
            self._agregar_etiqueta(
                self._formatear_hora(fecha, multi_dia), x, self.y + dp(20), "10sp", ancla=ancla
            )


Factory.register("GraficaTendencia", cls=GraficaTendencia)

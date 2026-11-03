"""
Tarjeta de variable del Dashboard, en forma de fila ancha: caja de valor a
la izquierda, nombre + barra de rango optimo al centro, icono a la derecha.

La barra (cuando hay umbrales configurados y una lectura disponible) se
dibuja a mano con canvas de Kivy, mismo enfoque que
widgets/grafica_tendencia.py: sin librerias externas, y los numeros se
agregan como Label hijos posicionados a mano (un canvas no puede dibujar
texto directamente).

Igual que VariableCard (widgets/common.kv): el fondo se dibuja en
canvas.before sobre un BoxLayout simple, NO con MDCard/MDBoxLayout, porque
BackgroundColorBehavior envuelve el fondo en PushMatrix/Rotate/PopMatrix
(para poder rotar el widget) y esa envoltura deja los hijos invisibles en
cuanto la tarjeta queda dentro de un ScrollView - el mismo problema ya
documentado en VariableCard.
"""

from kivy.factory import Factory
from kivy.graphics import Color, RoundedRectangle, Triangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import AliasProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget


class _BarraEscala(Widget):
    """
    Barra horizontal de rango optimo: fondo rojo (fuera de rango), segmento
    verde en el rango optimo configurado, flecha señalando el valor actual,
    y los 4 numeros de referencia (min/max de la escala, min/max optimo)
    debajo. No dibuja nada si falta algun umbral o el valor actual.

    Escala (se calcula, no se guarda): margen = (optimo_max - optimo_min)/2;
    escala_min = max(0, optimo_min - margen); escala_max = optimo_max + margen.
    Con esa formula el segmento verde siempre ocupa la mitad central de la
    barra (25%-75%), salvo cuando el margen de abajo se recorta por el
    limite de 0.
    """

    minimo_optimo = NumericProperty(None, allownone=True)
    maximo_optimo = NumericProperty(None, allownone=True)
    valor = NumericProperty(None, allownone=True)

    ALTURA_BARRA = dp(8)
    ALTURA_NUMEROS = dp(14)
    ESPACIO_FLECHA = dp(9)
    PADDING_LADOS = dp(4)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._etiquetas = []
        self.bind(
            pos=self._redibujar,
            size=self._redibujar,
            minimo_optimo=self._redibujar,
            maximo_optimo=self._redibujar,
            valor=self._redibujar,
        )

    def _limpiar_etiquetas(self):
        for etiqueta in self._etiquetas:
            self.remove_widget(etiqueta)
        self._etiquetas = []

    def _agregar_etiqueta(self, texto, x, y, ancla="center"):
        etiqueta = Label(
            text=texto, font_size="10sp", color=(0.4, 0.4, 0.4, 1), size_hint=(None, None)
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

    @staticmethod
    def _formatear_num(valor):
        return f"{valor:.0f}" if abs(valor) >= 100 else f"{valor:.1f}"

    def _redibujar(self, *args):
        self.canvas.clear()
        self._limpiar_etiquetas()

        if self.minimo_optimo is None or self.maximo_optimo is None or self.valor is None:
            return  # sin umbrales configurados o sin lectura: no se dibuja nada

        opt_min, opt_max = self.minimo_optimo, self.maximo_optimo
        margen = (opt_max - opt_min) / 2
        escala_min = max(0, opt_min - margen)
        escala_max = opt_max + margen
        rango = (escala_max - escala_min) or 1  # evita division entre 0

        x0 = self.x + self.PADDING_LADOS
        x1 = self.right - self.PADDING_LADOS
        ancho = max(x1 - x0, 1)

        def _x_de(valor):
            fraccion = min(1, max(0, (valor - escala_min) / rango))
            return x0 + fraccion * ancho

        x_opt_min = _x_de(opt_min)
        x_opt_max = _x_de(opt_max)
        # El valor se recorta a la escala: si esta fuera de rango, la
        # flecha queda pegada al extremo correspondiente en vez de salirse.
        x_valor = _x_de(min(max(self.valor, escala_min), escala_max))

        y_numeros = self.y + self.ALTURA_NUMEROS / 2
        y_barra = self.y + self.ALTURA_NUMEROS
        y_flecha = y_barra + self.ALTURA_BARRA + dp(2)

        with self.canvas:
            Color(0.80, 0.30, 0.30, 1)  # fondo: fuera de rango optimo
            RoundedRectangle(
                pos=(x0, y_barra), size=(ancho, self.ALTURA_BARRA), radius=[self.ALTURA_BARRA / 2]
            )

            Color(0.30, 0.65, 0.35, 1)  # segmento: rango optimo configurado
            RoundedRectangle(
                pos=(x_opt_min, y_barra),
                size=(max(x_opt_max - x_opt_min, dp(2)), self.ALTURA_BARRA),
                radius=[self.ALTURA_BARRA / 2],
            )

            Color(0.15, 0.15, 0.15, 1)  # flecha: valor actual
            Triangle(
                points=[
                    x_valor - dp(5), y_flecha + self.ESPACIO_FLECHA,
                    x_valor + dp(5), y_flecha + self.ESPACIO_FLECHA,
                    x_valor, y_flecha,
                ]
            )

        self._agregar_etiqueta(self._formatear_num(escala_min), x0, y_numeros, ancla="left")
        self._agregar_etiqueta(self._formatear_num(escala_max), x1, y_numeros, ancla="right")
        self._agregar_etiqueta(self._formatear_num(opt_min), x_opt_min, y_numeros, ancla="center")
        self._agregar_etiqueta(self._formatear_num(opt_max), x_opt_max, y_numeros, ancla="center")


class TarjetaVariableBarra(ButtonBehavior, BoxLayout):
    """
    Fila de variable del Dashboard. Uso (en .kv):
        TarjetaVariableBarra:
            nombre: "pH"
            valor_texto: "6.0"
            unidad: ""
            icono: "flask-outline"
            md_bg_color: 0.80, 0.92, 0.91, 1
            color_icono: 0.0, 0.35, 0.35, 1
            minimo_optimo: 5.5   # opcional: si se omite (o falta el valor
            maximo_optimo: 6.5   # actual), se muestra sin barra
            valor_numerico: 6.0
            variable_id: "ph"
            callback_tocar: root.ir_a_detalle
    """

    nombre = StringProperty("")
    valor_texto = StringProperty("--")
    unidad = StringProperty("")
    icono = StringProperty("help-circle-outline")
    color_icono = ListProperty([0.25, 0.25, 0.25, 1])
    md_bg_color = ListProperty([1, 1, 1, 1])
    color_borde = ListProperty([0, 0, 0, 0])
    variable_id = StringProperty("")
    callback_tocar = ObjectProperty(None, allownone=True)

    minimo_optimo = NumericProperty(None, allownone=True)
    maximo_optimo = NumericProperty(None, allownone=True)
    valor_numerico = NumericProperty(None, allownone=True)

    def _get_tiene_barra(self):
        return (
            self.minimo_optimo is not None
            and self.maximo_optimo is not None
            and self.valor_numerico is not None
        )

    tiene_barra = AliasProperty(
        _get_tiene_barra, None, bind=("minimo_optimo", "maximo_optimo", "valor_numerico")
    )


Factory.register("_BarraEscala", cls=_BarraEscala)
Factory.register("TarjetaVariableBarra", cls=TarjetaVariableBarra)

Builder.load_string(
    """
<TarjetaVariableBarra>:
    orientation: "horizontal"
    padding: "14dp", "10dp"
    spacing: "10dp"
    size_hint_y: None
    height: "92dp" if root.tiene_barra else "64dp"
    opacity: 0.7 if self.state == "down" else 1
    on_release: root.callback_tocar(root.variable_id) if root.callback_tocar else None

    canvas.before:
        Color:
            rgba: root.md_bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18]

    canvas.after:
        Color:
            rgba: root.color_borde
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, 18]
            width: 2.5

    BoxLayout:
        orientation: "vertical"
        size_hint_x: None
        width: "72dp"

        Widget:
        Label:
            text: root.valor_texto
            bold: True
            font_size: "21sp"
            halign: "center"
            color: 0.12, 0.12, 0.12, 1
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
        Label:
            text: root.unidad
            font_size: "11sp"
            halign: "center"
            color: 0.45, 0.45, 0.45, 1
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1] if root.unidad else 0
        Widget:

    BoxLayout:
        orientation: "vertical"
        size_hint_x: 1
        spacing: "4dp"

        Widget:
        Label:
            text: root.nombre
            bold: True
            font_size: "14sp"
            halign: "center"
            color: 0.28, 0.28, 0.28, 1
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
        _BarraEscala:
            size_hint_y: None
            height: "40dp" if root.tiene_barra else "0dp"
            minimo_optimo: root.minimo_optimo
            maximo_optimo: root.maximo_optimo
            valor: root.valor_numerico
        Widget:

    MDIcon:
        icon: root.icono
        theme_text_color: "Custom"
        text_color: root.color_icono
        font_size: "24sp"
        size_hint: None, None
        size: "30dp", "30dp"
        pos_hint: {"center_y": 0.5}
"""
)

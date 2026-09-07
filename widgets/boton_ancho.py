from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.button import MDButton, MDButtonText


class BotonAncho(MDButton):
    """MDButton pensado para theme_width='Custom' (ancho repartido con
    size_hint_x) que mantiene el icono y el texto centrados.

    KivyMD solo calcula esa posicion una vez, 0.2s despues de crear el
    boton, asumiendo que el ancho final es el del contenido
    (theme_width='Primary'). Si el boton termina mas ancho que su
    contenido (nuestro caso, para repartir el espacio en una fila),
    el icono y el texto quedan pegados al borde izquierdo. Aqui se
    recalcula la posicion cada vez que cambia el ancho real o el texto.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind(width=self._centrar_contenido)
        Clock.schedule_once(self._centrar_contenido, 0.3)

    def add_widget(self, widget, *args, **kwargs):
        resultado = super().add_widget(widget, *args, **kwargs)
        if isinstance(widget, MDButtonText):
            widget.bind(texture_size=self._centrar_contenido)
        return resultado

    def _centrar_contenido(self, *args):
        icono = self._button_icon
        texto = self._button_text
        if texto is None:
            return
        if icono is not None:
            ancho_contenido = icono.width + dp(10) + texto.texture_size[0]
            inicio = max(dp(16), (self.width - ancho_contenido) / 2)
            icono.x = inicio
            texto.x = icono.x + icono.width + dp(10)
        else:
            texto.x = max(dp(16), (self.width - texto.texture_size[0]) / 2)

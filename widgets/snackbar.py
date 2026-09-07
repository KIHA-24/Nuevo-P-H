"""
Snackbar (notificacion flotante breve) reutilizable para toda la app.

No usa kivymd.uix.snackbar.MDSnackbar a proposito: MDSnackbar hereda de
MDCard, que crea un Fbo para el efecto ripple apenas se instancia, y en
este entorno (Windows + backend grafico ANGLE) eso revienta con
"FBO Initialization failed: Incomplete attachment" en cuanto se crea el
widget. Este snackbar casero hace lo mismo visualmente (mensaje flotante
abajo, se cierra solo) pero con canvas.before simple, igual que VariableCard
en widgets/common.kv, evitando esa maquinaria.
"""

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

COLOR_OK = (0.15, 0.35, 0.35, 1)
COLOR_ERROR = (0.55, 0.15, 0.15, 1)


class _Snackbar(BoxLayout):
    def __init__(self, texto, color_fondo, **kwargs):
        ancho = Window.width * 0.9
        super().__init__(
            size_hint=(None, None),
            size=(ancho, dp(48)),
            pos=((Window.width - ancho) / 2, dp(24)),
            padding=(dp(16), dp(12)),
            opacity=0,
            **kwargs,
        )
        with self.canvas.before:
            Color(*color_fondo)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._actualizar_rect, size=self._actualizar_rect)

        self.add_widget(Label(text=texto, color=(1, 1, 1, 1), halign="center"))

    def _actualizar_rect(self, *_args):
        self._rect.pos = self.pos
        self._rect.size = self.size


def mostrar_snackbar(texto, error=False, duracion=3.0):
    """Muestra un mensaje flotante breve al usuario (se cierra solo)."""
    snackbar = _Snackbar(texto, COLOR_ERROR if error else COLOR_OK)
    Window.add_widget(snackbar)
    Animation(opacity=1, d=0.15).start(snackbar)

    def _cerrar(*_args):
        animacion = Animation(opacity=0, d=0.15)
        animacion.bind(on_complete=lambda *_: Window.remove_widget(snackbar))
        animacion.start(snackbar)

    Clock.schedule_once(_cerrar, duracion)

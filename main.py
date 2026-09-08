"""
HydroSmart - Aplicacion movil de monitoreo hidroponico
main.py: solo arma la app (ScreenManager + tema).

Estructura del proyecto:
- widgets/  -> componentes visuales reutilizables (BackTopAppBar, VariableCard)
- screens/  -> una pantalla por archivo (logica) + su .kv (diseno)
- services/ -> conexion a datos (Firebase, cuando este lista)

Integrantes: Kevin Hernandez - Sebastian Caceres
"""

import os
from kivy.lang import Builder
from kivy.utils import platform
from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window

# Los componentes reutilizables se cargan primero, porque los .kv de las
# pantallas los usan (BackTopAppBar, VariableCard).
Builder.load_file(os.path.join(os.path.dirname(__file__), "widgets", "common.kv"))

from screens.login_screen import LoginScreen
from screens.dashboard_screen import DashboardScreen
from screens.detalle_screen import DetalleScreen
from screens.historial_screen import HistorialScreen
from screens.configuracion_screen import ConfiguracionScreen

# Tamano de ventana de referencia SOLO para pruebas en escritorio (simula un movil).
# Esto no afecta como se vera en un celular real / futuro empaquetado a Android.
Window.size = (360, 640)


class HydroSmartManager(ScreenManager):
    """Controlador de navegacion entre pantallas."""
    pass


class HydroSmartApp(MDApp):
    def build(self):
        self.title = "HydroSmart"

        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Teal"

        sm = HydroSmartManager()
        sm.add_widget(LoginScreen())
        sm.add_widget(DashboardScreen())
        sm.add_widget(DetalleScreen())
        sm.add_widget(HistorialScreen())
        sm.add_widget(ConfiguracionScreen())

        return sm


if __name__ == "__main__":
    try:
        HydroSmartApp().run()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        # En Android/iOS no hay consola ni teclado esperando input(), asi que
        # llamarlo ahi lanza EOFError de inmediato y cierra la app - esta
        # pausa es solo para ver la ventana de consola en pruebas de escritorio.
        if platform not in ("android", "ios"):
            input("\nPresiona ENTER para cerrar esta ventana...")
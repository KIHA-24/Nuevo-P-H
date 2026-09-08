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
import traceback
from kivy.utils import platform


def run_app():
    from kivy.lang import Builder
    from kivymd.app import MDApp
    from kivy.uix.screenmanager import ScreenManager, NoTransition
    from kivy.core.window import Window

    # Los componentes reutilizables se cargan primero, porque los .kv de las
    # pantallas los usan (BackTopAppBar, VariableCard).
    Builder.load_file(os.path.join(os.path.dirname(__file__), "widgets", "common.kv"))

    from screens.login_screen import LoginScreen
    from screens.dashboard_screen import DashboardScreen
    from screens.detalle_screen import DetalleScreen
    from screens.historial_screen import HistorialScreen
    from screens.configuracion_screen import ConfiguracionScreen

    if platform not in ("android", "ios"):
        # Tamano de ventana de referencia SOLO para pruebas en escritorio
        # (simula un movil). No aplica en un celular real.
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
            # La transicion por defecto (SlideTransition) renderiza ambas
            # pantallas a texturas via Fbo para animarlas con un shader.
            # En este dispositivo esa creacion de Fbo en cada cambio de
            # pantalla es justo lo que dispara el SIGSEGV nativo dentro del
            # driver de la GPU Adreno (confirmado con adb logcat: crashea en
            # kivy/graphics/vbo.so -> libGLESv2_adreno.so al tocar "Iniciar
            # sesion", justo cuando arranca la transicion hacia dashboard).
            # NoTransition cambia de pantalla al instante sin Fbo ni shader,
            # evitando esa ruta de codigo por completo.
            sm.transition = NoTransition()
            sm.add_widget(LoginScreen())
            sm.add_widget(DashboardScreen())
            sm.add_widget(DetalleScreen())
            sm.add_widget(HistorialScreen())
            sm.add_widget(ConfiguracionScreen())

            if platform == "android":
                # El comportamiento por defecto de Kivy para el boton/gesto
                # "atras" en Android minimiza la app (mActivity.moveTaskToBack),
                # pero esa transicion choca con el hilo de render de Kivy en
                # este dispositivo (GPU Adreno) y tumba el proceso entero con
                # un SIGSEGV en vez de solo minimizar. Por eso lo consumimos
                # nosotros: navegamos entre pantallas propias y, en las
                # pantallas raiz (dashboard/login), no hacemos nada en vez de
                # dejar que Kivy dispare el minimizado que crashea.
                def _manejar_tecla_atras(window, key, *args):
                    if key != 27:
                        return False
                    if sm.current in ("detalle", "historial", "configuracion"):
                        sm.current = "dashboard"
                    return True

                Window.bind(on_keyboard=_manejar_tecla_atras)

            return sm

    HydroSmartApp().run()


def _write_crash_log(error_text):
    """Guarda el error en un archivo de texto dentro de la carpeta de la app,
    para poder revisarlo despues con un explorador de archivos si la pantalla
    de error no se alcanza a ver o a leer completa."""
    try:
        log_path = os.path.join(os.getcwd(), "hydrosmart_crash_log.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(error_text)
        return log_path
    except Exception:
        return None


def _show_crash_screen(error_text):
    """Pantalla minima (solo Kivy base, sin KivyMD) para mostrar el error
    directamente en el celular cuando algo falla al iniciar la app."""
    from kivy.app import App
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.label import Label

    class CrashApp(App):
        def build(self):
            label = Label(
                text="HydroSmart no pudo iniciar:\n\n" + error_text,
                size_hint_y=None,
                halign="left",
                valign="top",
                padding=(20, 20),
            )
            label.bind(
                width=lambda *_: label.setter("text_size")(label, (label.width, None))
            )
            label.bind(
                texture_size=lambda *_: setattr(label, "height", label.texture_size[1])
            )
            scroll = ScrollView()
            scroll.add_widget(label)
            return scroll

    CrashApp().run()


if __name__ == "__main__":
    try:
        run_app()
    except Exception:
        error_text = traceback.format_exc()
        print(error_text)
        log_path = _write_crash_log(error_text)
        if log_path:
            error_text += "\n\nGuardado en:\n" + log_path

        if platform not in ("android", "ios"):
            input("\nPresiona ENTER para cerrar esta ventana...")
        else:
            _show_crash_screen(error_text)

import os
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from screens.base_screen import NavegableScreen
from services import cultivos_store
from services.thingspeak_client import guardar_configuracion, obtener_configuracion
from widgets.snackbar import mostrar_snackbar

Builder.load_file(os.path.join(os.path.dirname(__file__), "configuracion_screen.kv"))

VARIABLES = ["ph", "ce", "temperatura", "humedad", "iluminacion"]


class ConfiguracionScreen(NavegableScreen, MDScreen):
    """Pantalla de configuracion: canal de ThingSpeak y umbrales del cultivo activo."""

    def on_pre_enter(self, *args):
        super().on_pre_enter(*args)
        cultivo = cultivos_store.obtener_cultivo_activo()
        self.ids.barra_superior.title = f"{cultivo['nombre']} - Configuracion"

        self.ids.channel_id.text = cultivo["channel_id"] or ""
        self.ids.read_api_key.text = cultivo["read_api_key"] or ""
        self.ids.write_api_key.text = cultivo["write_api_key"] or ""

        self.ids.switch_tema.active = MDApp.get_running_app().theme_cls.theme_style == "Dark"

        umbrales = obtener_configuracion() or {}
        for variable in VARIABLES:
            self.ids[f"{variable}_min"].text = str(umbrales.get(f"{variable}_min", ""))
            self.ids[f"{variable}_max"].text = str(umbrales.get(f"{variable}_max", ""))

    def cambiar_tema(self, activo):
        MDApp.get_running_app().theme_cls.theme_style = "Dark" if activo else "Light"

    def guardar(self):
        cultivo = cultivos_store.obtener_cultivo_activo()
        cultivos_store.guardar_credenciales(
            cultivo["id"],
            self.ids.channel_id.text.strip(),
            self.ids.read_api_key.text.strip(),
            self.ids.write_api_key.text.strip(),
        )

        umbrales = {}
        try:
            for variable in VARIABLES:
                umbrales[f"{variable}_min"] = float(self.ids[f"{variable}_min"].text)
                umbrales[f"{variable}_max"] = float(self.ids[f"{variable}_max"].text)
        except ValueError:
            mostrar_snackbar("Revisa que todos los umbrales sean numeros validos", error=True)
            return

        for variable in VARIABLES:
            if umbrales[f"{variable}_min"] >= umbrales[f"{variable}_max"]:
                mostrar_snackbar(
                    f"El minimo de {variable} debe ser menor que el maximo", error=True
                )
                return

        guardar_configuracion(umbrales)
        mostrar_snackbar("Configuracion guardada")

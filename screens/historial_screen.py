import os
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import (
    MDListItem,
    MDListItemLeadingIcon,
    MDListItemHeadlineText,
    MDListItemSupportingText,
    MDListItemTertiaryText,
)

from screens.base_screen import NavegableScreen
from services import cultivos_store
from services.thingspeak_client import obtener_historial
from widgets.hilos import ejecutar_en_segundo_plano
from widgets.boton_ancho import BotonAncho

Builder.load_file(os.path.join(os.path.dirname(__file__), "historial_screen.kv"))


class HistorialScreen(NavegableScreen, MDScreen):
    """Pantalla de historial de mediciones."""

    rango_actual = StringProperty("dia")
    _version = 0

    def on_pre_enter(self, *args):
        super().on_pre_enter(*args)
        cultivo = cultivos_store.obtener_cultivo_activo()
        self.ids.barra_superior.title = f"{cultivo['nombre']} - Historial"
        self.cargar_historial(self.rango_actual)

    def cargar_historial(self, rango):
        """
        Consulta el historial para el rango dado ('dia' o 'semana'). La
        consulta a ThingSpeak puede tardar, asi que corre en un hilo aparte
        para no trabar la interfaz mientras espera.
        """
        self.rango_actual = rango
        self.ids.lista_historial.clear_widgets()
        self.ids.mensaje_vacio.text = "Cargando..."
        self.ids.mensaje_vacio.opacity = 1

        self._version += 1
        version = self._version

        def _tarea():
            return obtener_historial(rango=rango)

        def _al_terminar(historial):
            if version != self._version:
                return

            self.ids.lista_historial.clear_widgets()

            if not historial:
                self.ids.mensaje_vacio.text = "No hay mediciones registradas todavia"
                self.ids.mensaje_vacio.opacity = 1
                return

            self.ids.mensaje_vacio.opacity = 0
            for medicion in historial:
                self.ids.lista_historial.add_widget(
                    MDListItem(
                        MDListItemLeadingIcon(icon="chart-timeline-variant"),
                        MDListItemHeadlineText(text=str(medicion.get("fecha", "--"))),
                        MDListItemSupportingText(
                            text=(
                                f"pH: {medicion.get('ph', '--')}   "
                                f"CE: {medicion.get('ce', '--')}   "
                                f"NPK: {medicion.get('n', '--')}/{medicion.get('p', '--')}/{medicion.get('k', '--')}"
                            )
                        ),
                        MDListItemTertiaryText(
                            text=(
                                f"Temp: {medicion.get('temperatura', '--')}°C   "
                                f"Humedad: {medicion.get('humedad', '--')}%   "
                                f"Luz: {medicion.get('iluminacion', '--')} lux"
                            )
                        ),
                    )
                )

        ejecutar_en_segundo_plano(_tarea, _al_terminar)

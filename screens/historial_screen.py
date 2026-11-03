import os
from datetime import datetime, timedelta, timezone

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
from screens.dashboard_screen import ESTADO_TEXTOS, COLOR_BORDE_ALERTA
from services import cultivos_store, lecturas_store
from services.thingspeak_client import obtener_historial
from widgets.hilos import ejecutar_en_segundo_plano
from widgets.boton_ancho import BotonAncho

Builder.load_file(os.path.join(os.path.dirname(__file__), "historial_screen.kv"))

# Mismas variables con umbral que maneja thingspeak_client._VARIABLES_CON_UMBRAL.
VARIABLES_ALERTA = ["ph", "ce", "temperatura", "humedad", "iluminacion"]

NOMBRES_VARIABLE = {
    "ph": "pH",
    "ce": "CE",
    "temperatura": "Temperatura",
    "humedad": "Humedad",
    "iluminacion": "Iluminacion",
}

# Mismos iconos que usa cada VariableCard en el Dashboard, para que una
# alerta de "Temperatura" se reconozca de un vistazo aca tambien.
ICONOS_VARIABLE = {
    "ph": "flask-outline",
    "ce": "flash-outline",
    "temperatura": "thermometer",
    "humedad": "water-percent",
    "iluminacion": "white-balance-sunny",
}

DIAS_RESUMEN_ALERTAS = 7


class HistorialScreen(NavegableScreen, MDScreen):
    """Pantalla de historial: mediciones y resumen de alertas."""

    rango_actual = StringProperty("dia")
    _version = 0

    def on_pre_enter(self, *args):
        super().on_pre_enter(*args)
        cultivo = cultivos_store.obtener_cultivo_activo()
        self.ids.barra_superior.title = f"{cultivo['nombre']} - Historial"
        self.cargar_resumen_alertas()
        self.cargar_historial(self.rango_actual)

    def cargar_resumen_alertas(self):
        """
        Muestra, para el cultivo activo, cuantas veces entro en
        advertencia/critico cada variable en los ultimos
        DIAS_RESUMEN_ALERTAS dias, y el detalle de esas alertas. Son
        consultas locales (SQLite), asi que se hacen directo sin hilo
        aparte como si hace obtener_historial() (que si es de red).
        """
        cultivo = cultivos_store.obtener_cultivo_activo()
        desde = (datetime.now(timezone.utc) - timedelta(days=DIAS_RESUMEN_ALERTAS)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        conteo = lecturas_store.contar_alertas_por_variable(cultivo["id"], desde_fecha=desde)
        for variable in VARIABLES_ALERTA:
            tarjeta = self.ids[f"resumen_{variable}"]
            cantidad = conteo.get(variable, 0)
            tarjeta.valor = str(cantidad)
            # Variables sin ninguna alerta en el periodo quedan discretas
            # en vez de competir visualmente con las que si tuvieron.
            tarjeta.opacity = 1 if cantidad else 0.45

        alertas = lecturas_store.obtener_historial_alertas(cultivo["id"], desde_fecha=desde)
        self.ids.lista_alertas.clear_widgets()

        if not alertas:
            self.ids.mensaje_alertas_vacio.text = "Sin alertas registradas en este periodo"
            self.ids.mensaje_alertas_vacio.opacity = 1
            return

        self.ids.mensaje_alertas_vacio.opacity = 0
        for alerta in alertas:
            variable = alerta["variable"]
            self.ids.lista_alertas.add_widget(
                MDListItem(
                    MDListItemLeadingIcon(
                        icon=ICONOS_VARIABLE.get(variable, "alert-circle-outline"),
                        theme_text_color="Custom",
                        text_color=COLOR_BORDE_ALERTA.get(alerta["estado"], (0.5, 0.5, 0.5, 1)),
                    ),
                    MDListItemHeadlineText(
                        text=(
                            f"{NOMBRES_VARIABLE.get(variable, variable)} - "
                            f"{ESTADO_TEXTOS.get(alerta['estado'], alerta['estado'])}"
                        )
                    ),
                    MDListItemSupportingText(text=f"Desde: {alerta['fecha_inicio']}"),
                    MDListItemTertiaryText(text=f"Hasta: {alerta['fecha_fin'] or 'Activa'}"),
                )
            )

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

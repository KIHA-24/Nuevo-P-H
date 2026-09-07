import os
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivymd.uix.screen import MDScreen

from screens.base_screen import NavegableScreen
from services import cultivos_store
from services.thingspeak_client import (
    obtener_ph,
    obtener_ce,
    obtener_npk,
    obtener_temperatura,
    obtener_humedad,
    obtener_iluminacion,
    obtener_historial,
)
from widgets.hilos import ejecutar_en_segundo_plano
from widgets.boton_ancho import BotonAncho
import widgets.grafica_tendencia  # noqa: F401  (registra GraficaTendencia para el .kv)

Builder.load_file(os.path.join(os.path.dirname(__file__), "detalle_screen.kv"))

VARIABLES = {
    "ph": {
        "titulo": "pH",
        "icono": "flask-outline",
        "color": (0.0, 0.35, 0.35, 1),
        "unidad": "",
        "obtener": obtener_ph,
    },
    "ce": {
        "titulo": "CE",
        "icono": "flash-outline",
        "color": (0.05, 0.35, 0.5, 1),
        "unidad": "",
        "obtener": obtener_ce,
    },
    "npk": {
        "titulo": "NPK",
        "icono": "leaf",
        "color": (0.55, 0.38, 0.05, 1),
        "unidad": "",
        "obtener": obtener_npk,
    },
    "temperatura": {
        "titulo": "Temperatura",
        "icono": "thermometer",
        "color": (0.75, 0.28, 0.05, 1),
        "unidad": "°C",
        "obtener": obtener_temperatura,
    },
    "humedad": {
        "titulo": "Humedad",
        "icono": "water-percent",
        "color": (0.05, 0.3, 0.6, 1),
        "unidad": "%",
        "obtener": obtener_humedad,
    },
    "iluminacion": {
        "titulo": "Iluminacion",
        "icono": "white-balance-sunny",
        "color": (0.65, 0.5, 0.0, 1),
        "unidad": " lux",
        "obtener": obtener_iluminacion,
    },
}


def _serie_desde_historial(variable, historial):
    """Convierte el historial (lista de dicts) en una lista de numeros para graficar."""
    if variable == "npk":
        # Para NPK graficamos el promedio de N, P, K como una sola linea
        serie = []
        for medicion in historial:
            numeros = []
            for campo in ("n", "p", "k"):
                valor = medicion.get(campo)
                try:
                    if valor is not None:
                        numeros.append(float(valor))
                except (TypeError, ValueError):
                    pass
            serie.append(sum(numeros) / len(numeros) if numeros else None)
        return serie

    serie = []
    for medicion in historial:
        valor = medicion.get(variable)
        try:
            serie.append(float(valor) if valor is not None else None)
        except (TypeError, ValueError):
            serie.append(None)
    return serie


class DetalleScreen(NavegableScreen, MDScreen):
    """Pantalla de detalle de una variable especifica (graficas de tendencia)."""

    variable_actual = StringProperty("ph")
    _version = 0

    def on_pre_enter(self, *args):
        super().on_pre_enter(*args)
        cultivo = cultivos_store.obtener_cultivo_activo()
        self.ids.barra_superior.title = f"{cultivo['nombre']} - Detalle"
        self.mostrar_variable(self.variable_actual)

    def mostrar_variable(self, variable):
        """
        Cambia la variable mostrada. La consulta a ThingSpeak puede tardar,
        asi que corre en un hilo aparte para no trabar la interfaz.
        """
        self.variable_actual = variable
        info = VARIABLES[variable]

        self.ids.titulo_variable.text = info["titulo"]
        self.ids.icono_variable.icon = info["icono"]
        self.ids.icono_variable.text_color = info["color"]
        self.ids.grafica_tendencia.color_linea = list(info["color"])
        self.ids.valor_actual.text = "..."
        self.ids.mensaje_historial.text = "Cargando..."

        self._version += 1
        version = self._version

        def _tarea():
            return info["obtener"](), obtener_historial(rango="dia")

        def _al_terminar(resultado):
            if version != self._version:
                return

            valor, historial = resultado
            if variable == "npk" and valor:
                self.ids.valor_actual.text = f"N:{valor['n']}  P:{valor['p']}  K:{valor['k']}"
            elif valor is not None:
                self.ids.valor_actual.text = f"{valor}{info['unidad']}"
            else:
                self.ids.valor_actual.text = "--"

            self.ids.grafica_tendencia.valores = _serie_desde_historial(variable, historial)
            if historial:
                self.ids.mensaje_historial.text = f"{len(historial)} mediciones registradas hoy"
            else:
                self.ids.mensaje_historial.text = "Aun no hay datos historicos para graficar"

        ejecutar_en_segundo_plano(_tarea, _al_terminar)

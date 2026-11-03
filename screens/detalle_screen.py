import os
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivymd.uix.screen import MDScreen

from screens.base_screen import NavegableScreen
from services import cultivos_store
from services.thingspeak_client import (
    obtener_ph,
    obtener_ce,
    obtener_n,
    obtener_p,
    obtener_k,
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
        "rotulo_eje": "pH",
        "decimales": 1,
    },
    "ce": {
        "titulo": "CE",
        "icono": "flash-outline",
        "color": (0.05, 0.35, 0.5, 1),
        "unidad": "",
        "obtener": obtener_ce,
        "rotulo_eje": "CE (mS/cm)",
        "decimales": 1,
    },
    "n": {
        "titulo": "Nitrogeno",
        "icono": "alpha-n-circle-outline",
        "color": (0.15, 0.45, 0.15, 1),
        "unidad": " ppm",
        "obtener": obtener_n,
        "rotulo_eje": "N (ppm)",
        "decimales": 0,
    },
    "p": {
        "titulo": "Fosforo",
        "icono": "alpha-p-circle-outline",
        "color": (0.45, 0.15, 0.55, 1),
        "unidad": " ppm",
        "obtener": obtener_p,
        "rotulo_eje": "P (ppm)",
        "decimales": 0,
    },
    "k": {
        "titulo": "Potasio",
        "icono": "alpha-k-circle-outline",
        "color": (0.60, 0.40, 0.05, 1),
        "unidad": " ppm",
        "obtener": obtener_k,
        "rotulo_eje": "K (ppm)",
        "decimales": 0,
    },
    "temperatura": {
        "titulo": "Temperatura",
        "icono": "thermometer",
        "color": (0.75, 0.28, 0.05, 1),
        "unidad": "°C",
        "obtener": obtener_temperatura,
        "rotulo_eje": "Temp. (°C)",
        "decimales": 0,
    },
    "humedad": {
        "titulo": "Humedad",
        "icono": "water-percent",
        "color": (0.05, 0.3, 0.6, 1),
        "unidad": "%",
        "obtener": obtener_humedad,
        "rotulo_eje": "Humedad (%)",
        "decimales": 0,
    },
    "iluminacion": {
        "titulo": "Iluminacion",
        "icono": "white-balance-sunny",
        "color": (0.65, 0.5, 0.0, 1),
        "unidad": " lux",
        "obtener": obtener_iluminacion,
        "rotulo_eje": "Luz (lux)",
        "decimales": 0,
    },
}


def _serie_desde_historial(variable, historial):
    """Convierte el historial (lista de dicts) en una lista de numeros para graficar."""
    serie = []
    for medicion in historial:
        valor = medicion.get(variable)
        try:
            serie.append(float(valor) if valor is not None else None)
        except (TypeError, ValueError):
            serie.append(None)
    return serie


def _fechas_desde_historial(historial):
    """Fechas (mismo indice que _serie_desde_historial) para las etiquetas de hora del eje X."""
    return [medicion.get("fecha") for medicion in historial]


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
        self.ids.grafica_tendencia.rotulo_eje_y = info["rotulo_eje"]
        self.ids.grafica_tendencia.decimales = info["decimales"]
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
            if valor is not None:
                self.ids.valor_actual.text = f"{valor}{info['unidad']}"
            else:
                self.ids.valor_actual.text = "--"

            self.ids.grafica_tendencia.valores = _serie_desde_historial(variable, historial)
            self.ids.grafica_tendencia.fechas = _fechas_desde_historial(historial)
            if historial:
                self.ids.mensaje_historial.text = f"{len(historial)} mediciones registradas hoy"
            else:
                self.ids.mensaje_historial.text = "Aun no hay datos historicos para graficar"

        ejecutar_en_segundo_plano(_tarea, _al_terminar)

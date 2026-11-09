import os
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.widget import Widget
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogIcon,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogContentContainer,
    MDDialogButtonContainer,
)
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText
from plyer import notification

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
    obtener_estado_general,
    obtener_estados_por_variable,
    obtener_configuracion,
)
from screens.avisos import calcular_avisos
from widgets.hilos import ejecutar_en_segundo_plano
from widgets.snackbar import mostrar_snackbar
from widgets.boton_ancho import BotonAncho
from widgets.tarjeta_variable_barra import TarjetaVariableBarra  # noqa: F401  (registra TarjetaVariableBarra para el .kv)

Builder.load_file(os.path.join(os.path.dirname(__file__), "dashboard_screen.kv"))

ESTADO_TEXTOS = {
    "optimo": "Optimo",
    "advertencia": "Advertencia",
    "critico": "Critico",
    "sin_datos": "Sin datos",
}

COLOR_BORDE_ALERTA = {
    "critico": (0.75, 0.15, 0.15, 1),
    "advertencia": (0.85, 0.6, 0.05, 1),
    "optimo": (0, 0, 0, 0),
    "sin_datos": (0, 0, 0, 0),
}

TIEMPO_MANTENER_PRESIONADO = 0.5


VARIABLES_CON_BARRA = {"ph", "ce", "n", "p", "k"}

# pH y CE se muestran con 1 decimal (valores tipicamente entre 0 y 10); el
# resto se redondea a entero para que el numero no se corte/envuelva en la
# caja de valor, angosta a proposito para dejarle espacio a la barra.
_DECIMALES_VALOR = {"ph": 1, "ce": 1}


def _formatear_valor(variable, valor):
    if valor is None:
        return "--"
    return f"{valor:.{_DECIMALES_VALOR.get(variable, 0)}f}"


class _BotonCultivo(MDButton):
    """
    Boton de una pestaña de cultivo: toque corto = seleccionarlo,
    mantener presionado = abrir el menu de renombrar/eliminar.
    """

    def __init__(self, cultivo_id, al_tocar, al_mantener, *children, **kwargs):
        super().__init__(*children, **kwargs)
        self._cultivo_id = cultivo_id
        self._al_tocar = al_tocar
        self._al_mantener = al_mantener
        self._evento_mantener = None
        self._fue_mantenido = False

    def on_press(self):
        super().on_press()
        self._fue_mantenido = False
        self._evento_mantener = Clock.schedule_once(
            self._disparar_mantener, TIEMPO_MANTENER_PRESIONADO
        )

    def _disparar_mantener(self, *_args):
        self._fue_mantenido = True
        self._al_mantener(self._cultivo_id, self)

    def on_release(self):
        super().on_release()
        if self._evento_mantener:
            self._evento_mantener.cancel()
        if not self._fue_mantenido:
            self._al_tocar(self._cultivo_id)


class DashboardScreen(MDScreen):
    """Pantalla principal: pestañas de cultivos + indicadores en tiempo real."""

    _dialogo = None
    _campo_dialogo = None
    _menu_cultivo = None
    _version_datos = 0
    _evento_auto_actualizacion = None
    INTERVALO_AUTO_ACTUALIZACION = 15  # segundos entre cada refresco automatico

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ultimo estado de alerta avisado de cada variable (ver
        # screens/avisos.py:calcular_avisos). Instancia propia (no atributo
        # de clase) para no compartir el dict entre instancias.
        self._estados_alertados = {}

    def ir_a(self, nombre_pantalla):
        self.manager.current = nombre_pantalla

    def ir_a_detalle(self, variable_id):
        self.manager.get_screen("detalle").variable_actual = variable_id
        self.manager.current = "detalle"

    def cerrar_sesion(self):
        self.manager.get_screen("login").limpiar_campos()
        self.manager.current = "login"

    def on_pre_enter(self, *args):
        super().on_pre_enter(*args)
        self.actualizar_pestanas()
        self.actualizar_datos()
        self._iniciar_auto_actualizacion()

    def on_leave(self, *args):
        super().on_leave(*args)
        self._detener_auto_actualizacion()

    def _iniciar_auto_actualizacion(self):
        """
        Refresca los datos cada INTERVALO_AUTO_ACTUALIZACION segundos mientras
        el Dashboard esta visible. Se detiene solo al salir de la pantalla
        (on_leave), para no seguir consultando ThingSpeak de fondo cuando el
        usuario esta viendo Detalle, Historial o Configuracion.
        """
        self._detener_auto_actualizacion()  # por si ya habia una corriendo, evita duplicados
        self._evento_auto_actualizacion = Clock.schedule_interval(
            lambda dt: self.actualizar_datos(), self.INTERVALO_AUTO_ACTUALIZACION
        )

    def _detener_auto_actualizacion(self):
        if self._evento_auto_actualizacion is not None:
            self._evento_auto_actualizacion.cancel()
            self._evento_auto_actualizacion = None

    def actualizar_pestanas(self):
        """Redibuja la fila de pestañas (una por cultivo) segun cual esta activo."""
        activo = cultivos_store.obtener_cultivo_activo()
        self.ids.titulo_appbar.text = f"{activo['nombre']} - HydroSmart"

        self.ids.fila_cultivos.clear_widgets()
        for cultivo in cultivos_store.listar_cultivos():
            es_activo = cultivo["id"] == activo["id"]
            self.ids.fila_cultivos.add_widget(
                _BotonCultivo(
                    cultivo["id"],
                    self.seleccionar_cultivo,
                    self.abrir_menu_cultivo,
                    MDButtonText(text=cultivo["nombre"]),
                    style="filled" if es_activo else "outlined",
                )
            )

    def seleccionar_cultivo(self, cultivo_id):
        cultivos_store.establecer_cultivo_activo(cultivo_id)
        self.actualizar_pestanas()
        self.actualizar_datos()

    def abrir_menu_cultivo(self, cultivo_id, boton):
        """Menu de mantener-presionado sobre una pestaña: renombrar o eliminar ese cultivo."""
        self._menu_cultivo = MDDropdownMenu(
            caller=boton,
            items=[
                {
                    "text": "Renombrar",
                    "leading_icon": "pencil-outline",
                    "on_release": lambda: self._elegir_renombrar(cultivo_id),
                },
                {
                    "text": "Eliminar",
                    "leading_icon": "trash-can-outline",
                    "on_release": lambda: self._elegir_eliminar(cultivo_id),
                },
            ],
        )
        self._menu_cultivo.open()

    def _elegir_renombrar(self, cultivo_id):
        self._menu_cultivo.dismiss()
        cultivo = next(
            (c for c in cultivos_store.listar_cultivos() if c["id"] == cultivo_id), None
        )
        if not cultivo:
            return

        self._campo_dialogo = MDTextField(
            MDTextFieldHintText(text="Nombre del cultivo"),
            text=cultivo["nombre"],
            mode="outlined",
        )
        self._dialogo = MDDialog(
            MDDialogIcon(icon="pencil-outline"),
            MDDialogHeadlineText(text="Renombrar cultivo"),
            MDDialogContentContainer(
                self._campo_dialogo,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancelar"),
                    style="text",
                    on_release=lambda *_: self._dialogo.dismiss(),
                ),
                MDButton(
                    MDButtonText(text="Guardar"),
                    style="text",
                    on_release=lambda *_: self._guardar_renombre(cultivo_id),
                ),
                spacing="8dp",
            ),
        )
        self._dialogo.open()

    def _guardar_renombre(self, cultivo_id):
        nombre = self._campo_dialogo.text.strip()
        if not nombre:
            return

        cultivos_store.renombrar_cultivo(cultivo_id, nombre)
        self._dialogo.dismiss()
        self.actualizar_pestanas()
        mostrar_snackbar("Cultivo renombrado")

    def _elegir_eliminar(self, cultivo_id):
        self._menu_cultivo.dismiss()
        cultivo = next(
            (c for c in cultivos_store.listar_cultivos() if c["id"] == cultivo_id), None
        )
        if not cultivo:
            return

        self._dialogo = MDDialog(
            MDDialogIcon(icon="trash-can-outline"),
            MDDialogHeadlineText(text="Eliminar cultivo"),
            MDDialogSupportingText(
                text=f"Se va a eliminar '{cultivo['nombre']}' y su configuracion. Esta accion no se puede deshacer."
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancelar"),
                    style="text",
                    on_release=lambda *_: self._dialogo.dismiss(),
                ),
                MDButton(
                    MDButtonText(text="Eliminar"),
                    style="text",
                    on_release=lambda *_: self._confirmar_eliminar(cultivo_id),
                ),
                spacing="8dp",
            ),
        )
        self._dialogo.open()

    def _confirmar_eliminar(self, cultivo_id):
        cultivos_store.eliminar_cultivo(cultivo_id)
        self._dialogo.dismiss()
        self.actualizar_pestanas()
        self.actualizar_datos()
        mostrar_snackbar("Cultivo eliminado")

    def abrir_dialogo_nuevo_cultivo(self):
        self._campo_dialogo = MDTextField(
            MDTextFieldHintText(text="Nombre del cultivo (ej. Lechugas)"),
            mode="outlined",
        )
        self._dialogo = MDDialog(
            MDDialogIcon(icon="sprout"),
            MDDialogHeadlineText(text="Nuevo cultivo"),
            MDDialogContentContainer(
                self._campo_dialogo,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancelar"),
                    style="text",
                    on_release=lambda *_: self._dialogo.dismiss(),
                ),
                MDButton(
                    MDButtonText(text="Crear"),
                    style="text",
                    on_release=lambda *_: self._crear_cultivo_desde_dialogo(),
                ),
                spacing="8dp",
            ),
        )
        self._dialogo.open()

    def _crear_cultivo_desde_dialogo(self):
        nombre = self._campo_dialogo.text.strip()
        if not nombre:
            return

        cultivo = cultivos_store.crear_cultivo(nombre)
        self._dialogo.dismiss()
        self.seleccionar_cultivo(cultivo["id"])

    def actualizar_datos(self):
        """
        Refresca las tarjetas de variables con los datos del cultivo activo.
        La consulta a ThingSpeak puede tardar (es una llamada de red), asi
        que corre en un hilo aparte para no trabar la interfaz mientras espera.
        """
        self._version_datos += 1
        version = self._version_datos

        def _tarea():
            return {
                "ph": obtener_ph(),
                "ce": obtener_ce(),
                "n": obtener_n(),
                "p": obtener_p(),
                "k": obtener_k(),
                "temperatura": obtener_temperatura(),
                "humedad": obtener_humedad(),
                "iluminacion": obtener_iluminacion(),
                "estado": obtener_estado_general(),
                "estados_variables": obtener_estados_por_variable(),
                "configuracion": obtener_configuracion() or {},
            }

        def _al_terminar(datos):
            # Si mientras se esperaba la respuesta se pidieron datos mas
            # nuevos (otro cultivo, otro refresco), esta respuesta ya es vieja.
            if version != self._version_datos:
                return

            umbrales = datos["configuracion"]
            for variable in (
                "ph", "ce", "n", "p", "k", "temperatura", "humedad", "iluminacion"
            ):
                tarjeta = self.ids[f"card_{variable}"]
                tarjeta.valor_texto = _formatear_valor(variable, datos[variable])
                tarjeta.valor_numerico = datos[variable]
                if variable in VARIABLES_CON_BARRA:
                    tarjeta.minimo_optimo = umbrales.get(f"{variable}_min")
                    tarjeta.maximo_optimo = umbrales.get(f"{variable}_max")

            for variable, estado in datos["estados_variables"].items():
                card_id = f"card_{variable}"
                if card_id in self.ids:
                    self.ids[card_id].color_borde = COLOR_BORDE_ALERTA.get(estado, (0, 0, 0, 0))
            self._avisar_variables_en_alerta(datos["estados_variables"], datos, umbrales)

        ejecutar_en_segundo_plano(_tarea, _al_terminar)

    def _avisar_variables_en_alerta(self, estados_variables, valores, umbrales):
        """
        Avisa (snackbar + notificacion nativa) de las variables que entraron
        a advertencia/critico o escalaron de advertencia a critico en este
        refresco - no de las que ya estaban en el mismo estado de alerta en
        el refresco anterior. La decision de que avisar (y si agrupar varios
        avisos en uno) vive en screens/avisos.py, para poder probarla sin
        levantar la app.
        """
        avisos, self._estados_alertados = calcular_avisos(
            self._estados_alertados, estados_variables, valores, umbrales
        )

        # Si hay mas de un aviso individual a la vez, se escalonan (el
        # segundo aparece recien cuando termina la duracion del primero)
        # para que no se encimen visualmente.
        retraso_acumulado = 0.0
        for aviso in avisos:
            duracion = 4.0 if aviso["es_critico"] else 3.0
            Clock.schedule_once(
                lambda _dt, aviso=aviso, duracion=duracion: self._mostrar_aviso(aviso, duracion),
                retraso_acumulado,
            )
            retraso_acumulado += duracion

    def _mostrar_aviso(self, aviso, duracion):
        mostrar_snackbar(aviso["texto"], error=aviso["es_critico"], duracion=duracion)
        self._notificar_nativo(aviso["texto"])

    def _notificar_nativo(self, mensaje):
        """
        Notificacion nativa del sistema operativo, ademas del snackbar: avisa
        aunque el usuario tenga la app minimizada o en segundo plano. plyer
        puede fallar o no estar disponible segun la plataforma (o si en
        Android 13+ no se concedio el permiso POST_NOTIFICATIONS) - eso nunca
        debe romper el resto de la app ni afectar al snackbar, que ya se
        mostro antes de llegar aca.
        """
        try:
            notification.notify(title="HydroSmart - Alerta", message=mensaje, timeout=5)
        except Exception:
            pass

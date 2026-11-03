"""
Simulador de sensores para HydroSmart.

El hardware real todavia no esta listo, asi que esta herramienta manda
lecturas de prueba al canal de ThingSpeak de un cultivo, para poder probar
el resto de la app (dashboard, alertas, graficas, historial) sin esperar
al sensor fisico.

No independiente de services/: para leer los cultivos guardados (con sus
credenciales de ThingSpeak) usa services/lecturas_store.py, que es donde
vive esa informacion desde la migracion a SQLite (datos_locales/lecturas.db).
El envio de lecturas si sigue siendo directo a la API de ThingSpeak, con el
mismo mapeo de campos que usa services/thingspeak_client.py:
    field1=pH, field2=CE, field3=N, field4=P, field5=K,
    field6=Temperatura, field7=Humedad, field8=Iluminacion

Correr con: python simulador/simulador.py
"""

import os
import random
import sys
import threading
import tkinter as tk
from tkinter import ttk

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import lecturas_store

THINGSPEAK_URL = "https://api.thingspeak.com"

# Mismo orden/mapeo que services/thingspeak_client.py:CAMPOS - si eso
# cambia alguna vez, hay que actualizar esta lista tambien a mano (el
# simulador no importa ese archivo a proposito, ver docstring arriba).
CAMPOS = [
    ("ph", "field1", "pH"),
    ("ce", "field2", "CE (mS/cm)"),
    ("n", "field3", "N (ppm)"),
    ("p", "field4", "P (ppm)"),
    ("k", "field5", "K (ppm)"),
    ("temperatura", "field6", "Temperatura (°C)"),
    ("humedad", "field7", "Humedad (%)"),
    ("iluminacion", "field8", "Iluminacion (lux)"),
]

# Valores de referencia para los botones de perfil rapido. No son los
# umbrales reales de ningun cultivo (esos se configuran por cultivo desde
# la app) - son solo puntos de partida razonables para probar los 3 estados
# visuales (optimo/advertencia/critico) sin escribir todo a mano.
PERFILES = {
    "Optimo": {
        "ph": 6.0, "ce": 1.6, "n": 150, "p": 50, "k": 200,
        "temperatura": 22, "humedad": 60, "iluminacion": 14000,
    },
    "Advertencia": {
        "ph": 6.4, "ce": 1.95, "n": 195, "p": 68, "k": 240,
        "temperatura": 25.5, "humedad": 69, "iluminacion": 19500,
    },
    "Critico": {
        "ph": 4.0, "ce": 3.2, "n": 280, "p": 12, "k": 320,
        "temperatura": 35, "humedad": 22, "iluminacion": 500,
    },
}

INTERVALO_AUTO_MS = 20_000
VARIACION_AUTO = 0.03  # +/- 3% por lectura en modo automatico


def _leer_cultivos():
    try:
        return lecturas_store.listar_cultivos()
    except Exception:
        return []


class SimuladorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HydroSmart - Simulador de sensores")
        self.root.resizable(False, False)

        self.cultivos = []
        self.entradas = {}
        self._auto_after_id = None

        self._construir_interfaz()
        self._recargar_cultivos()

    # ---- interfaz -----------------------------------------------------

    def _construir_interfaz(self):
        pad = {"padx": 8, "pady": 4}

        marco_cultivo = ttk.Frame(self.root)
        marco_cultivo.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(marco_cultivo, text="Cultivo:").pack(side="left")

        self.var_cultivo = tk.StringVar()
        self.combo_cultivo = ttk.Combobox(
            marco_cultivo, textvariable=self.var_cultivo, state="readonly", width=28
        )
        self.combo_cultivo.pack(side="left", padx=6)

        ttk.Button(marco_cultivo, text="↻ Recargar", command=self._recargar_cultivos).pack(
            side="left"
        )

        self.label_canal = ttk.Label(self.root, foreground="#555555")
        self.label_canal.grid(row=1, column=0, columnspan=2, sticky="w", padx=8)

        marco_campos = ttk.LabelFrame(self.root, text="Lectura a enviar")
        marco_campos.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        for i, (clave, _campo_ts, etiqueta) in enumerate(CAMPOS):
            fila, columna = divmod(i, 2)
            sub = ttk.Frame(marco_campos)
            sub.grid(row=fila, column=columna, sticky="w", padx=10, pady=4)
            ttk.Label(sub, text=etiqueta, width=16).pack(side="left")
            var = tk.StringVar(value="0")
            entrada = ttk.Entry(sub, textvariable=var, width=10)
            entrada.pack(side="left")
            self.entradas[clave] = var

        marco_perfiles = ttk.Frame(self.root)
        marco_perfiles.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(marco_perfiles, text="Perfil rapido:").pack(side="left")
        for nombre in PERFILES:
            ttk.Button(
                marco_perfiles, text=nombre, command=lambda n=nombre: self._cargar_perfil(n)
            ).pack(side="left", padx=4)

        self.boton_enviar = ttk.Button(
            self.root, text="Enviar lectura", command=self._enviar_manual
        )
        self.boton_enviar.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))

        self.var_auto = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.root,
            text=f"Modo automatico (una lectura cada {INTERVALO_AUTO_MS // 1000}s, con variacion aleatoria)",
            variable=self.var_auto,
            command=self._alternar_modo_automatico,
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=8)

        self.label_estado = ttk.Label(self.root, text="", wraplength=380, justify="left")
        self.label_estado.grid(row=6, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 8))

    # ---- cultivos -------------------------------------------------------

    def _recargar_cultivos(self):
        self.cultivos = _leer_cultivos()
        nombres = [c["nombre"] for c in self.cultivos]
        self.combo_cultivo["values"] = nombres
        if nombres and self.var_cultivo.get() not in nombres:
            self.var_cultivo.set(nombres[0])
        elif not nombres:
            self.var_cultivo.set("")
        self._actualizar_label_canal()
        self.combo_cultivo.bind("<<ComboboxSelected>>", lambda *_: self._actualizar_label_canal())

    def _cultivo_seleccionado(self):
        nombre = self.var_cultivo.get()
        for cultivo in self.cultivos:
            if cultivo["nombre"] == nombre:
                return cultivo
        return None

    def _actualizar_label_canal(self):
        cultivo = self._cultivo_seleccionado()
        if not cultivo:
            self.label_canal.config(text="No hay cultivos guardados en datos_locales/lecturas.db")
        elif not cultivo.get("write_api_key"):
            self.label_canal.config(
                text="Este cultivo no tiene write_api_key configurada "
                "(agregala desde Configuracion en la app)."
            )
        else:
            self.label_canal.config(
                text=f"Canal ThingSpeak: {cultivo.get('channel_id')}"
            )

    # ---- perfiles ---------------------------------------------------------

    def _cargar_perfil(self, nombre):
        for clave, valor in PERFILES[nombre].items():
            self.entradas[clave].set(str(valor))

    # ---- envio ------------------------------------------------------------

    def _leer_valores_actuales(self):
        """Convierte los campos de texto a float. Lanza ValueError si alguno es invalido."""
        return {clave: float(self.entradas[clave].get()) for clave, _, _ in CAMPOS}

    def _enviar_manual(self):
        cultivo = self._cultivo_seleccionado()
        if not cultivo or not cultivo.get("write_api_key"):
            self._mostrar_estado(
                "No se puede enviar: el cultivo seleccionado no tiene write_api_key.", error=True
            )
            return

        try:
            valores = self._leer_valores_actuales()
        except ValueError:
            self._mostrar_estado(
                "Revisa los campos: todos deben ser numeros validos.", error=True
            )
            return

        self.boton_enviar.config(state="disabled")
        self._mostrar_estado("Enviando...", error=False)
        threading.Thread(
            target=self._enviar_en_hilo, args=(cultivo["write_api_key"], valores), daemon=True
        ).start()

    def _enviar_en_hilo(self, write_api_key, valores):
        resultado = _enviar_lectura(write_api_key, valores)
        self.root.after(0, self._procesar_resultado_envio, resultado)

    def _procesar_resultado_envio(self, resultado):
        self.boton_enviar.config(state="normal")
        exito, mensaje = resultado
        self._mostrar_estado(mensaje, error=not exito)

    def _mostrar_estado(self, mensaje, error):
        self.label_estado.config(text=mensaje, foreground="#a03030" if error else "#206020")

    # ---- modo automatico ----------------------------------------------------

    def _alternar_modo_automatico(self):
        if self.var_auto.get():
            cultivo = self._cultivo_seleccionado()
            if not cultivo or not cultivo.get("write_api_key"):
                self._mostrar_estado(
                    "No se puede activar el modo automatico: falta write_api_key.", error=True
                )
                self.var_auto.set(False)
                return
            self._mostrar_estado(
                f"Modo automatico activado: enviando cada {INTERVALO_AUTO_MS // 1000}s.",
                error=False,
            )
            self._tick_automatico()
        else:
            if self._auto_after_id is not None:
                self.root.after_cancel(self._auto_after_id)
                self._auto_after_id = None
            self._mostrar_estado("Modo automatico detenido.", error=False)

    def _tick_automatico(self):
        cultivo = self._cultivo_seleccionado()
        if not cultivo or not cultivo.get("write_api_key"):
            self._mostrar_estado(
                "Cultivo sin write_api_key: modo automatico detenido.", error=True
            )
            self.var_auto.set(False)
            return

        try:
            valores = self._leer_valores_actuales()
        except ValueError:
            valores = {clave: v for clave, v in PERFILES["Optimo"].items()}

        # Pequena variacion aleatoria sobre el valor actual de cada campo,
        # para simular sensores reales fluctuando en cada lectura.
        for clave, _, _ in CAMPOS:
            nuevo_valor = valores[clave] * (1 + random.uniform(-VARIACION_AUTO, VARIACION_AUTO))
            valores[clave] = round(nuevo_valor, 2)
            self.entradas[clave].set(str(valores[clave]))

        threading.Thread(
            target=self._enviar_en_hilo, args=(cultivo["write_api_key"], valores), daemon=True
        ).start()

        self._auto_after_id = self.root.after(INTERVALO_AUTO_MS, self._tick_automatico)


def _enviar_lectura(write_api_key, valores):
    """
    Manda una lectura a ThingSpeak. Retorna (exito: bool, mensaje: str).

    Mismo patron que services/thingspeak_client.py: timeout=5 y todo el
    request envuelto en try/except para no romper la interfaz si no hay
    internet o ThingSpeak no responde.
    """
    params = {"api_key": write_api_key}
    for clave, campo_ts, _ in CAMPOS:
        params[campo_ts] = valores[clave]

    try:
        respuesta = requests.get(f"{THINGSPEAK_URL}/update", params=params, timeout=5)
        respuesta.raise_for_status()
    except requests.RequestException as error:
        return False, f"Error de conexion con ThingSpeak: {error}"

    entry_id = respuesta.text.strip()
    if entry_id == "0":
        return False, (
            "ThingSpeak rechazo el envio (entry_id 0). La causa mas comun es el "
            "limite de 1 actualizacion cada 15 segundos de las cuentas gratis - "
            "espera unos segundos e intenta de nuevo."
        )
    return True, f"Lectura enviada correctamente (entry #{entry_id})."


def main():
    root = tk.Tk()
    SimuladorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

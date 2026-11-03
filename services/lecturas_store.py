"""
Base de datos local (SQLite) del proyecto HydroSmart: datos_locales/lecturas.db.

Guarda todo lo que antes vivia en archivos JSON sueltos, para no perder
datos si la app se cierra a medio escribir uno de esos archivos:

- "lecturas": cache/historial de lecturas de ThingSpeak que SI llegaron
  bien, para que thingspeak_client.py pueda recurrir a la ultima lectura
  conocida de un cultivo cuando no hay internet o ThingSpeak no responde.
- "alertas": historial de cuando una variable (ph, ce, temperatura,
  humedad, iluminacion) entra o sale de advertencia/critico, para poder
  responder cosas como "el pH estuvo fuera de rango 3 veces esta semana".
- "cultivos": los cultivos que el usuario monitorea (antes en
  datos_locales/cultivos.json). La usa services/cultivos_store.py.
- "configuracion": los umbrales min/max de cada variable por cultivo
  (antes en datos_locales/configuracion_{cultivo_id}.json). La usa
  services/thingspeak_client.py.

conectar() migra automaticamente, la primera vez que se abre la base en
todo el proceso, cualquier dato viejo que todavia este en esos archivos
JSON (ver _migrar_datos_legacy) - asi nadie pierde cultivos o umbrales ya
guardados al actualizar la app. Los JSON migrados se renombran agregando
".migrado" en vez de borrarse.

Ningun otro archivo debe abrir lecturas.db directamente: todo pasa por las
funciones de aqui abajo.
"""

import glob
import json
import os
import sqlite3
from datetime import datetime, timezone

_RUTA_DB = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "datos_locales", "lecturas.db"
)

# Cuantas lecturas como maximo se guardan por cultivo. Al insertar una
# lectura nueva se borran las mas viejas que sobren, para que la base no
# crezca sin limite con el tiempo.
_MAX_LECTURAS_POR_CULTIVO = 1000

_CAMPOS_NUMERICOS = ["ph", "ce", "n", "p", "k", "temperatura", "humedad", "iluminacion"]

# Variables que tienen umbrales configurables (mismo set que
# thingspeak_client._VARIABLES_CON_UMBRAL - no se importa ese modulo desde
# aca para no crear una dependencia circular, asi que si esa lista cambia
# alguna vez hay que actualizar esta tambien a mano).
_VARIABLES_CONFIG = ["ph", "ce", "n", "p", "k", "temperatura", "humedad", "iluminacion"]

_migracion_hecha = False


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def conectar():
    """
    Abre (y si hace falta crea) datos_locales/lecturas.db con todas sus
    tablas, y dispara la migracion de JSON viejo la primera vez que se
    llama en todo el proceso. Usada tanto por las funciones de este
    archivo como por cultivos_store.py.
    """
    os.makedirs(os.path.dirname(_RUTA_DB), exist_ok=True)
    conexion = sqlite3.connect(_RUTA_DB)
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cultivo_id TEXT NOT NULL,
            fecha TEXT NOT NULL,
            ph REAL,
            ce REAL,
            n REAL,
            p REAL,
            k REAL,
            temperatura REAL,
            humedad REAL,
            iluminacion REAL
        )
        """
    )
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cultivo_id TEXT NOT NULL,
            variable TEXT NOT NULL,
            estado TEXT NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT
        )
        """
    )
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS cultivos (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            channel_id TEXT,
            read_api_key TEXT,
            write_api_key TEXT
        )
        """
    )
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS configuracion (
            cultivo_id TEXT NOT NULL,
            variable TEXT NOT NULL,
            minimo REAL,
            maximo REAL,
            PRIMARY KEY (cultivo_id, variable)
        )
        """
    )
    _migrar_datos_legacy(conexion)
    return conexion


# ---- migracion de los JSON viejos ----------------------------------------


def _desglosar_umbrales(umbrales):
    filas = []
    for variable in _VARIABLES_CONFIG:
        minimo = umbrales.get(f"{variable}_min")
        maximo = umbrales.get(f"{variable}_max")
        if minimo is not None or maximo is not None:
            filas.append((variable, minimo, maximo))
    return filas


def _migrar_cultivos_json(conexion, carpeta):
    ruta = os.path.join(carpeta, "cultivos.json")
    if not os.path.exists(ruta):
        return
    if conexion.execute("SELECT 1 FROM cultivos LIMIT 1").fetchone():
        return  # ya hay cultivos en SQLite: no pisamos nada

    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            cultivos = json.load(archivo)
        with conexion:
            for cultivo in cultivos:
                conexion.execute(
                    """
                    INSERT OR REPLACE INTO cultivos
                        (id, nombre, channel_id, read_api_key, write_api_key)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        cultivo.get("id"),
                        cultivo.get("nombre"),
                        cultivo.get("channel_id"),
                        cultivo.get("read_api_key"),
                        cultivo.get("write_api_key"),
                    ),
                )
        os.replace(ruta, ruta + ".migrado")
    except (OSError, ValueError, KeyError, sqlite3.Error):
        pass  # si algo sale mal, el .json original queda intacto para reintentar


def _migrar_configuracion_json(conexion, carpeta):
    for ruta in glob.glob(os.path.join(carpeta, "configuracion_*.json")):
        cultivo_id = os.path.basename(ruta)[len("configuracion_") : -len(".json")]

        if conexion.execute(
            "SELECT 1 FROM configuracion WHERE cultivo_id = ? LIMIT 1", (cultivo_id,)
        ).fetchone():
            continue  # este cultivo ya tiene configuracion en SQLite

        try:
            with open(ruta, "r", encoding="utf-8") as archivo:
                umbrales = json.load(archivo)
            with conexion:
                for variable, minimo, maximo in _desglosar_umbrales(umbrales):
                    conexion.execute(
                        """
                        INSERT OR REPLACE INTO configuracion (cultivo_id, variable, minimo, maximo)
                        VALUES (?, ?, ?, ?)
                        """,
                        (cultivo_id, variable, minimo, maximo),
                    )
            os.replace(ruta, ruta + ".migrado")
        except (OSError, ValueError, sqlite3.Error):
            pass


def _migrar_datos_legacy(conexion):
    """
    Migra a SQLite los datos que hayan quedado en cultivos.json y/o
    configuracion_*.json, una sola vez por proceso (se llama automaticamente
    desde conectar(), asi corre transparentemente antes de que cualquier
    funcion de cultivos_store o thingspeak_client pida datos).

    Los archivos migrados con exito se renombran agregando ".migrado" en
    vez de borrarse, por si hay que recuperarlos a mano.
    """
    global _migracion_hecha
    if _migracion_hecha:
        return
    _migracion_hecha = True

    carpeta = os.path.dirname(_RUTA_DB)
    _migrar_cultivos_json(conexion, carpeta)
    _migrar_configuracion_json(conexion, carpeta)


# ---- lecturas (cache/historial de ThingSpeak) -----------------------------


def guardar_lectura(cultivo_id, datos: dict):
    """
    Guarda una lectura exitosa de ThingSpeak como respaldo local.

    datos: dict con las claves ph, ce, n, p, k, temperatura, humedad,
    iluminacion (las que falten quedan como NULL) y opcionalmente "fecha"
    (si no viene, se usa el momento actual en UTC).
    """
    fecha = datos.get("fecha") or _ahora()

    conexion = conectar()
    try:
        with conexion:
            conexion.execute(
                """
                INSERT INTO lecturas
                    (cultivo_id, fecha, ph, ce, n, p, k, temperatura, humedad, iluminacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cultivo_id, fecha, *(datos.get(campo) for campo in _CAMPOS_NUMERICOS)),
            )
            # Solo nos quedamos con las _MAX_LECTURAS_POR_CULTIVO mas
            # recientes de este cultivo; el resto se borra.
            conexion.execute(
                """
                DELETE FROM lecturas
                WHERE cultivo_id = ? AND id NOT IN (
                    SELECT id FROM lecturas
                    WHERE cultivo_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (cultivo_id, cultivo_id, _MAX_LECTURAS_POR_CULTIVO),
            )
    finally:
        conexion.close()


def obtener_ultima_fecha_guardada(cultivo_id):
    """
    Retorna la fecha (string, tal cual la manda ThingSpeak) de la ultima
    lectura guardada de un cultivo, o None si todavia no hay ninguna.
    Sirve para no guardar la misma lectura mas de una vez: el dashboard
    pregunta cada 15s, pero el sensor real tarda mas en mandar un dato
    nuevo, asi que ThingSpeak devuelve la misma ultima fila varias veces
    seguidas.
    """
    conexion = conectar()
    try:
        fila = conexion.execute(
            "SELECT fecha FROM lecturas WHERE cultivo_id = ? ORDER BY id DESC LIMIT 1",
            (cultivo_id,),
        ).fetchone()
    finally:
        conexion.close()
    return fila[0] if fila else None


def obtener_ultimas_lecturas(cultivo_id, cantidad=100):
    """
    Retorna las ultimas `cantidad` lecturas guardadas de un cultivo, de
    mas reciente a mas antigua. Cada elemento tiene la misma forma que
    thingspeak_client.obtener_historial(): {"fecha", "ph", "ce", "n", "p",
    "k", "temperatura", "humedad", "iluminacion"}.
    """
    conexion = conectar()
    try:
        filas = conexion.execute(
            """
            SELECT fecha, ph, ce, n, p, k, temperatura, humedad, iluminacion
            FROM lecturas
            WHERE cultivo_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (cultivo_id, cantidad),
        ).fetchall()
    finally:
        conexion.close()

    return [
        {
            "fecha": fila[0],
            "ph": fila[1],
            "ce": fila[2],
            "n": fila[3],
            "p": fila[4],
            "k": fila[5],
            "temperatura": fila[6],
            "humedad": fila[7],
            "iluminacion": fila[8],
        }
        for fila in filas
    ]


# ---- alertas ---------------------------------------------------------------

_ESTADOS_DE_ALERTA = ("advertencia", "critico")


def registrar_cambio_estado(cultivo_id, variable, estado_nuevo):
    """
    Lleva el historial de alertas de una variable de un cultivo.

    - Si estado_nuevo es "advertencia" o "critico" y no hay ya una alerta
      abierta (fecha_fin NULL) para este cultivo+variable, abre una fila
      nueva con fecha_inicio=ahora.
    - Si estado_nuevo es "optimo" o "sin_datos" y hay una alerta abierta,
      la cierra (fecha_fin=ahora).
    - Si estado_nuevo es igual al estado de la alerta ya abierta (o si de
      cualquier forma ya hay una alerta en curso), no hace nada - evita
      filas duplicadas mientras la variable sigue mal.
    """
    conexion = conectar()
    try:
        with conexion:
            fila_abierta = conexion.execute(
                """
                SELECT id FROM alertas
                WHERE cultivo_id = ? AND variable = ? AND fecha_fin IS NULL
                """,
                (cultivo_id, variable),
            ).fetchone()

            if estado_nuevo in _ESTADOS_DE_ALERTA:
                if fila_abierta is None:
                    conexion.execute(
                        """
                        INSERT INTO alertas (cultivo_id, variable, estado, fecha_inicio)
                        VALUES (?, ?, ?, ?)
                        """,
                        (cultivo_id, variable, estado_nuevo, _ahora()),
                    )
            elif fila_abierta is not None:
                conexion.execute(
                    "UPDATE alertas SET fecha_fin = ? WHERE id = ?",
                    (_ahora(), fila_abierta[0]),
                )
    finally:
        conexion.close()


def obtener_historial_alertas(cultivo_id, desde_fecha=None):
    """
    Retorna todas las alertas (abiertas y cerradas) de un cultivo, de mas
    reciente a mas antigua. Cada elemento: {"variable", "estado",
    "fecha_inicio", "fecha_fin"} (fecha_fin es None si sigue activa).

    Si se pasa desde_fecha, solo se incluyen las que empezaron en o
    despues de esa fecha.
    """
    conexion = conectar()
    try:
        if desde_fecha:
            filas = conexion.execute(
                """
                SELECT variable, estado, fecha_inicio, fecha_fin
                FROM alertas
                WHERE cultivo_id = ? AND fecha_inicio >= ?
                ORDER BY id DESC
                """,
                (cultivo_id, desde_fecha),
            ).fetchall()
        else:
            filas = conexion.execute(
                """
                SELECT variable, estado, fecha_inicio, fecha_fin
                FROM alertas
                WHERE cultivo_id = ?
                ORDER BY id DESC
                """,
                (cultivo_id,),
            ).fetchall()
    finally:
        conexion.close()

    return [
        {"variable": fila[0], "estado": fila[1], "fecha_inicio": fila[2], "fecha_fin": fila[3]}
        for fila in filas
    ]


def contar_alertas_por_variable(cultivo_id, desde_fecha):
    """
    Cuenta cuantas alertas (advertencia + critico juntas) tuvo cada
    variable de un cultivo desde `desde_fecha` en adelante. Retorna un
    dict, ej. {"ph": 3, "temperatura": 1} - las variables sin alertas en
    ese periodo no aparecen en el dict.
    """
    conexion = conectar()
    try:
        filas = conexion.execute(
            """
            SELECT variable, COUNT(*) FROM alertas
            WHERE cultivo_id = ? AND fecha_inicio >= ?
            GROUP BY variable
            """,
            (cultivo_id, desde_fecha),
        ).fetchall()
    finally:
        conexion.close()

    return {variable: cantidad for variable, cantidad in filas}


# ---- configuracion (umbrales min/max por cultivo) -------------------------


def guardar_configuracion(cultivo_id, umbrales: dict):
    """
    Guarda los umbrales (min/max) de las variables con alerta de un
    cultivo, reemplazando por completo los que hubiera antes (mismo
    comportamiento que el JSON viejo, que se sobreescribia entero en
    cada guardado). umbrales, ejemplo: {"ph_min": 5.5, "ph_max": 6.5, ...}
    """
    conexion = conectar()
    try:
        with conexion:
            conexion.execute("DELETE FROM configuracion WHERE cultivo_id = ?", (cultivo_id,))
            for variable, minimo, maximo in _desglosar_umbrales(umbrales):
                conexion.execute(
                    """
                    INSERT OR REPLACE INTO configuracion (cultivo_id, variable, minimo, maximo)
                    VALUES (?, ?, ?, ?)
                    """,
                    (cultivo_id, variable, minimo, maximo),
                )
    finally:
        conexion.close()


def obtener_configuracion(cultivo_id):
    """
    Retorna los umbrales guardados de un cultivo como dict
    {"ph_min": ..., "ph_max": ..., ...}, o None si todavia no hay ninguno.
    """
    conexion = conectar()
    try:
        filas = conexion.execute(
            "SELECT variable, minimo, maximo FROM configuracion WHERE cultivo_id = ?",
            (cultivo_id,),
        ).fetchall()
    finally:
        conexion.close()

    if not filas:
        return None

    umbrales = {}
    for variable, minimo, maximo in filas:
        umbrales[f"{variable}_min"] = minimo
        umbrales[f"{variable}_max"] = maximo
    return umbrales


# ---- cultivos ---------------------------------------------------------------
# CRUD de bajo nivel sobre la tabla "cultivos". La logica de mas alto nivel
# (cultivo activo, crear con valores por defecto, etc.) vive en
# services/cultivos_store.py - aca solo esta el acceso a la tabla.


def listar_cultivos():
    """Retorna todos los cultivos guardados (sin crear ninguno por defecto)."""
    conexion = conectar()
    try:
        filas = conexion.execute(
            "SELECT id, nombre, channel_id, read_api_key, write_api_key FROM cultivos"
        ).fetchall()
    finally:
        conexion.close()

    return [
        {
            "id": fila[0],
            "nombre": fila[1],
            "channel_id": fila[2],
            "read_api_key": fila[3],
            "write_api_key": fila[4],
        }
        for fila in filas
    ]


def insertar_cultivo(cultivo: dict):
    """Inserta un cultivo nuevo tal cual (dict con id/nombre/channel_id/read_api_key/write_api_key)."""
    conexion = conectar()
    try:
        with conexion:
            conexion.execute(
                """
                INSERT INTO cultivos (id, nombre, channel_id, read_api_key, write_api_key)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cultivo["id"],
                    cultivo["nombre"],
                    cultivo.get("channel_id"),
                    cultivo.get("read_api_key"),
                    cultivo.get("write_api_key"),
                ),
            )
    finally:
        conexion.close()


def renombrar_cultivo(cultivo_id, nuevo_nombre):
    conexion = conectar()
    try:
        with conexion:
            conexion.execute(
                "UPDATE cultivos SET nombre = ? WHERE id = ?", (nuevo_nombre, cultivo_id)
            )
    finally:
        conexion.close()


def eliminar_cultivo(cultivo_id):
    conexion = conectar()
    try:
        with conexion:
            conexion.execute("DELETE FROM cultivos WHERE id = ?", (cultivo_id,))
    finally:
        conexion.close()


def guardar_credenciales_cultivo(cultivo_id, channel_id, read_api_key, write_api_key):
    conexion = conectar()
    try:
        with conexion:
            conexion.execute(
                """
                UPDATE cultivos
                SET channel_id = ?, read_api_key = ?, write_api_key = ?
                WHERE id = ?
                """,
                (channel_id, read_api_key, write_api_key, cultivo_id),
            )
    finally:
        conexion.close()

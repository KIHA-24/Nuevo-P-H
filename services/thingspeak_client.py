"""
Capa de conexion con ThingSpeak (base de datos del proyecto HydroSmart).

Este archivo es el UNICO lugar donde se debe hablar con ThingSpeak.
Ninguna pantalla (screens/) debe hacer requests directamente: todas pasan
por estas funciones, asi el dia que cambie el proveedor de datos o la
estructura de los campos, solo se edita este archivo.

Como conectar un canal real:
1. Crear una cuenta y un canal en https://thingspeak.com
2. Activar 8 campos en el canal, en este orden (asi quedan mapeados abajo):
   field1=pH, field2=CE, field3=N, field4=P, field5=K,
   field6=Temperatura, field7=Humedad, field8=Iluminacion
3. Cargar el Channel ID y las API Keys de ese canal en la pantalla de
   Configuracion, asociados al cultivo correspondiente (ver services/cultivos_store.py).

Cada cultivo tiene su propio canal, y todas las funciones de aqui abajo
trabajan siempre sobre el "cultivo activo". Mientras ese cultivo no tenga
canal configurado, las funciones devuelven None/listas vacias para que el
resto de la app no se rompa.
"""

import sqlite3
import time

import requests

from services import cultivos_store, lecturas_store

THINGSPEAK_URL = "https://api.thingspeak.com"

CAMPOS = {
    "ph": "field1",
    "ce": "field2",
    "n": "field3",
    "p": "field4",
    "k": "field5",
    "temperatura": "field6",
    "humedad": "field7",
    "iluminacion": "field8",
}

# Cache muy simple (por cultivo) para no pedir la misma lectura 6 veces
# seguidas cuando el dashboard llama a obtener_ph(), obtener_ce(), etc. una
# detras de otra.
_TIEMPO_CACHE_SEGUNDOS = 5
_cache_por_cultivo = {}


def _canal_configurado(cultivo):
    return bool(cultivo["channel_id"] and cultivo["read_api_key"])


def _pedir_json(url, params):
    try:
        respuesta = requests.get(url, params=params, timeout=5)
        respuesta.raise_for_status()
        return respuesta.json()
    except (requests.RequestException, ValueError):
        return None


def _feed_a_valores_normalizados(feed):
    """Convierte un feed de ThingSpeak (field1..field8 + created_at) al
    formato ph/ce/n/p/k/... que usa lecturas_store."""
    valores = {"fecha": feed.get("created_at")}
    for nombre, campo in CAMPOS.items():
        try:
            valores[nombre] = float(feed[campo]) if feed.get(campo) is not None else None
        except (TypeError, ValueError):
            valores[nombre] = None
    return valores


def _respaldar_lectura_local(cultivo_id, feed):
    """Guarda una lectura exitosa en el cache local, salvo que sea la
    misma que ya tenemos guardada (mismo "created_at"): el dashboard
    pregunta a ThingSpeak cada 15s, pero el sensor real tarda mas en
    mandar un dato nuevo, asi que sin este chequeo se duplicaria la
    misma lectura una y otra vez. Guardado silencioso: si el disco
    falla, no debe romper el flujo normal de la app."""
    try:
        fecha_nueva = feed.get("created_at")
        if fecha_nueva and fecha_nueva == lecturas_store.obtener_ultima_fecha_guardada(cultivo_id):
            return
        lecturas_store.guardar_lectura(cultivo_id, _feed_a_valores_normalizados(feed))
    except sqlite3.Error:
        pass


def _fila_local_a_feed(fila):
    """Convierte una fila de lecturas_store de vuelta al formato
    field1..field8 que espera el resto de este archivo (_valor_campo,
    obtener_ph, etc.), agregando "offline": True para que quien la reciba
    sepa que no es una lectura fresca de ThingSpeak."""
    if not fila:
        return None
    feed = {"created_at": fila["fecha"], "offline": True}
    for nombre, campo in CAMPOS.items():
        feed[campo] = fila.get(nombre)
    return feed


def _ultima_lectura_local(cultivo_id):
    try:
        filas = lecturas_store.obtener_ultimas_lecturas(cultivo_id, cantidad=1)
    except sqlite3.Error:
        return None
    return _fila_local_a_feed(filas[0]) if filas else None


def _obtener_ultima_lectura(forzar=False):
    """Pide a ThingSpeak la ultima lectura del cultivo activo, con cache de unos segundos.

    Si ThingSpeak no responde:
    - y ya habia una lectura en cache (aunque este vencida), se sigue
      devolviendo esa en vez de pisarla con None.
    - y no habia nada en cache, se recurre a la ultima lectura guardada en
      lecturas_store (ver _fila_local_a_feed) marcada como "offline".
    """
    cultivo = cultivos_store.obtener_cultivo_activo()
    if not _canal_configurado(cultivo):
        return None

    cache = _cache_por_cultivo.setdefault(cultivo["id"], {"datos": None, "momento": 0})
    ahora = time.time()
    cache_vieja = ahora - cache["momento"] > _TIEMPO_CACHE_SEGUNDOS
    if forzar or cache_vieja or cache["datos"] is None:
        datos = _pedir_json(
            f"{THINGSPEAK_URL}/channels/{cultivo['channel_id']}/feeds/last.json",
            {"api_key": cultivo["read_api_key"]},
        )
        if datos:
            _respaldar_lectura_local(cultivo["id"], datos)
            cache["datos"] = datos
            cache["momento"] = ahora
        elif cache["datos"] is None:
            cache["datos"] = _ultima_lectura_local(cultivo["id"])
            cache["momento"] = ahora
        # Si ThingSpeak fallo pero cache["datos"] ya tenia una lectura
        # buena de un pedido anterior, se deja tal cual (no se pisa con
        # None), para no perder la ultima lectura conocida.

    return cache["datos"]


def _valor_campo(nombre_campo):
    lectura = _obtener_ultima_lectura()
    if not lectura:
        return None

    valor = lectura.get(CAMPOS[nombre_campo])
    if valor is None:
        return None

    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def obtener_ph():
    """Retorna el valor mas reciente de pH, o None si no hay canal/lectura."""
    return _valor_campo("ph")


def obtener_ce():
    """Retorna el valor mas reciente de CE (conductividad electrica)."""
    return _valor_campo("ce")


def obtener_n():
    """Retorna el valor mas reciente de Nitrogeno (ppm)."""
    return _valor_campo("n")


def obtener_p():
    """Retorna el valor mas reciente de Fosforo (ppm)."""
    return _valor_campo("p")


def obtener_k():
    """Retorna el valor mas reciente de Potasio (ppm)."""
    return _valor_campo("k")


def obtener_npk():
    """Retorna el NPK mas reciente como dict {'n': .., 'p': .., 'k': ..}, o None."""
    n, p, k = obtener_n(), obtener_p(), obtener_k()
    if n is None and p is None and k is None:
        return None
    return {"n": n, "p": p, "k": k}


def obtener_temperatura():
    """Retorna la temperatura mas reciente (°C)."""
    return _valor_campo("temperatura")


def obtener_humedad():
    """Retorna la humedad mas reciente (%)."""
    return _valor_campo("humedad")


def obtener_iluminacion():
    """Retorna la iluminacion solar mas reciente (lux)."""
    return _valor_campo("iluminacion")


_VARIABLES_CON_UMBRAL = {
    "ph": obtener_ph,
    "ce": obtener_ce,
    "n": obtener_n,
    "p": obtener_p,
    "k": obtener_k,
    "temperatura": obtener_temperatura,
    "humedad": obtener_humedad,
    "iluminacion": obtener_iluminacion,
}


_MARGEN_ADVERTENCIA = 0.15  # 15% del rango, cerca de cualquiera de los dos bordes


def _estado_de_valor(valor, minimo, maximo):
    if valor is None or minimo is None or maximo is None:
        return "sin_datos"
    if not (minimo <= valor <= maximo):
        return "critico"
    rango = maximo - minimo
    if rango > 0:
        margen = rango * _MARGEN_ADVERTENCIA
        if valor <= minimo + margen or valor >= maximo - margen:
            return "advertencia"
    return "optimo"


def obtener_estados_por_variable():
    """
    Retorna el estado (optimo/advertencia/critico/sin_datos) de CADA
    variable con umbral configurado, por separado. Se usa para resaltar
    en el Dashboard cual tarjeta especifica esta fuera de rango, en vez
    de solo mostrar un estado general.

    Como efecto secundario (silencioso, no afecta lo que se retorna) deja
    registrado en lecturas_store cuando una variable entra o sale de
    advertencia/critico, para armar un historial de alertas.
    """
    cultivo = cultivos_store.obtener_cultivo_activo()
    umbrales = obtener_configuracion() or {}
    estados = {}
    for nombre, obtener in _VARIABLES_CON_UMBRAL.items():
        minimo = umbrales.get(f"{nombre}_min")
        maximo = umbrales.get(f"{nombre}_max")
        estado = _estado_de_valor(obtener(), minimo, maximo)
        estados[nombre] = estado
        try:
            lecturas_store.registrar_cambio_estado(cultivo["id"], nombre, estado)
        except sqlite3.Error:
            pass
    return estados


def obtener_estado_general():
    """
    Calcula el estado general del cultivo activo a partir del estado de
    cada variable individual (ver obtener_estados_por_variable):
    'sin_datos' si falta configuracion/lecturas, 'critico' si alguna
    esta fuera de rango, 'advertencia' si alguna esta cerca del limite,
    'optimo' si todas estan comodamente dentro de rango.
    """
    if not obtener_configuracion():
        return "sin_datos"

    estados = [e for e in obtener_estados_por_variable().values() if e != "sin_datos"]
    if not estados:
        return "sin_datos"
    if "critico" in estados:
        return "critico"
    if "advertencia" in estados:
        return "advertencia"
    return "optimo"


def obtener_historial(rango="dia"):
    """
    Retorna una lista de mediciones historicas del cultivo activo.
    rango: 'dia' (ultimas ~100 lecturas) o 'semana' (ultimas ~500 lecturas).
    Cada elemento: {"fecha", "ph", "ce", "n", "p", "k", "temperatura", "humedad", "iluminacion"}
    """
    cultivo = cultivos_store.obtener_cultivo_activo()
    if not _canal_configurado(cultivo):
        return []

    cantidad = 100 if rango == "dia" else 500
    datos = _pedir_json(
        f"{THINGSPEAK_URL}/channels/{cultivo['channel_id']}/feeds.json",
        {"api_key": cultivo["read_api_key"], "results": cantidad},
    )
    if not datos:
        # ThingSpeak no respondio: usamos el respaldo local en vez de
        # dejar el historial vacio. obtener_ultimas_lecturas() entrega
        # mas-reciente-primero (para ese otro uso es lo que conviene),
        # pero aca hace falta mas-antiguo-primero, igual que el camino
        # normal de ThingSpeak (feeds.json), asi que se invierte el orden.
        try:
            lecturas = lecturas_store.obtener_ultimas_lecturas(cultivo["id"], cantidad=cantidad)
        except sqlite3.Error:
            return []
        return list(reversed(lecturas))

    historial = []
    for lectura in datos.get("feeds", []):
        historial.append(
            {
                "fecha": lectura.get("created_at"),
                "ph": lectura.get(CAMPOS["ph"]),
                "ce": lectura.get(CAMPOS["ce"]),
                "n": lectura.get(CAMPOS["n"]),
                "p": lectura.get(CAMPOS["p"]),
                "k": lectura.get(CAMPOS["k"]),
                "temperatura": lectura.get(CAMPOS["temperatura"]),
                "humedad": lectura.get(CAMPOS["humedad"]),
                "iluminacion": lectura.get(CAMPOS["iluminacion"]),
            }
        )
    return historial


def guardar_configuracion(umbrales: dict):
    """
    Guarda los umbrales optimos del cultivo activo (tabla "configuracion"
    de lecturas.db).
    umbrales, ejemplo: {"ph_min": 5.5, "ph_max": 6.5, "ce_min": 1.2, "ce_max": 2.0}
    """
    cultivo = cultivos_store.obtener_cultivo_activo()
    lecturas_store.guardar_configuracion(cultivo["id"], umbrales)


def obtener_configuracion():
    """Retorna los umbrales guardados del cultivo activo, o None si aun no hay ninguno."""
    cultivo = cultivos_store.obtener_cultivo_activo()
    return lecturas_store.obtener_configuracion(cultivo["id"])

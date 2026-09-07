"""
Manejo de los "cultivos" que el usuario monitorea (ej. Lechugas, Tomates).

Cada cultivo tiene su propio canal de ThingSpeak (ver services/thingspeak_client.py)
y sus propios umbrales configurados, para poder llevar el monitoreo de varios
cultivos en paralelo. Todo se guarda localmente en datos_locales/cultivos.json.

Ninguna pantalla debe leer/escribir ese archivo directamente: todas pasan por
estas funciones.
"""

import json
import os
import uuid

_RUTA_CULTIVOS = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "datos_locales", "cultivos.json"
)

_cultivo_activo_id = None


def _leer_todos():
    try:
        with open(_RUTA_CULTIVOS, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (FileNotFoundError, ValueError):
        return []


def _guardar_todos(cultivos):
    os.makedirs(os.path.dirname(_RUTA_CULTIVOS), exist_ok=True)
    with open(_RUTA_CULTIVOS, "w", encoding="utf-8") as archivo:
        json.dump(cultivos, archivo)


def _nuevo_cultivo(nombre):
    return {
        "id": uuid.uuid4().hex[:8],
        "nombre": nombre,
        "channel_id": None,
        "read_api_key": None,
        "write_api_key": None,
    }


def listar_cultivos():
    """Retorna todos los cultivos guardados. Si no hay ninguno, crea uno por defecto."""
    cultivos = _leer_todos()
    if not cultivos:
        cultivos = [_nuevo_cultivo("Mi cultivo")]
        _guardar_todos(cultivos)
    return cultivos


def crear_cultivo(nombre):
    """Crea un cultivo nuevo (sin canal de ThingSpeak asignado todavia) y lo guarda."""
    cultivos = _leer_todos()
    cultivo = _nuevo_cultivo(nombre)
    cultivos.append(cultivo)
    _guardar_todos(cultivos)
    return cultivo


def renombrar_cultivo(cultivo_id, nuevo_nombre):
    """Cambia el nombre de un cultivo existente."""
    cultivos = _leer_todos()
    for cultivo in cultivos:
        if cultivo["id"] == cultivo_id:
            cultivo["nombre"] = nuevo_nombre
            break
    _guardar_todos(cultivos)


def eliminar_cultivo(cultivo_id):
    """
    Elimina un cultivo de la lista. Si era el cultivo activo, se desactiva
    (obtener_cultivo_activo elegira otro automaticamente la proxima vez).
    """
    global _cultivo_activo_id
    cultivos = [c for c in _leer_todos() if c["id"] != cultivo_id]
    _guardar_todos(cultivos)

    if _cultivo_activo_id == cultivo_id:
        _cultivo_activo_id = None


def guardar_credenciales(cultivo_id, channel_id, read_api_key, write_api_key):
    """Asocia (o actualiza) el canal de ThingSpeak de un cultivo existente."""
    cultivos = _leer_todos()
    for cultivo in cultivos:
        if cultivo["id"] == cultivo_id:
            cultivo["channel_id"] = channel_id or None
            cultivo["read_api_key"] = read_api_key or None
            cultivo["write_api_key"] = write_api_key or None
            break
    _guardar_todos(cultivos)


def establecer_cultivo_activo(cultivo_id):
    """Marca que pantallas como Dashboard/Detalle/Historial/Configuracion trabajen sobre este cultivo."""
    global _cultivo_activo_id
    _cultivo_activo_id = cultivo_id


def obtener_cultivo_activo():
    """Retorna el cultivo activo. Si todavia no se eligio ninguno, usa el primero de la lista."""
    global _cultivo_activo_id
    cultivos = listar_cultivos()

    for cultivo in cultivos:
        if cultivo["id"] == _cultivo_activo_id:
            return cultivo

    _cultivo_activo_id = cultivos[0]["id"]
    return cultivos[0]

"""
Manejo de los "cultivos" que el usuario monitorea (ej. Lechugas, Tomates).

Cada cultivo tiene su propio canal de ThingSpeak (ver services/thingspeak_client.py)
y sus propios umbrales configurados, para poder llevar el monitoreo de varios
cultivos en paralelo. Se guarda en la tabla "cultivos" de
datos_locales/lecturas.db (antes era datos_locales/cultivos.json; ver
services/lecturas_store.py para la migracion automatica de ese archivo viejo).

Ninguna pantalla debe leer/escribir esa tabla directamente: todas pasan por
estas funciones.
"""

import uuid

from services import lecturas_store

_cultivo_activo_id = None


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
    cultivos = lecturas_store.listar_cultivos()
    if not cultivos:
        return [crear_cultivo("Mi cultivo")]
    return cultivos


def crear_cultivo(nombre):
    """Crea un cultivo nuevo (sin canal de ThingSpeak asignado todavia) y lo guarda."""
    cultivo = _nuevo_cultivo(nombre)
    lecturas_store.insertar_cultivo(cultivo)
    return cultivo


def renombrar_cultivo(cultivo_id, nuevo_nombre):
    """Cambia el nombre de un cultivo existente."""
    lecturas_store.renombrar_cultivo(cultivo_id, nuevo_nombre)


def eliminar_cultivo(cultivo_id):
    """
    Elimina un cultivo de la lista. Si era el cultivo activo, se desactiva
    (obtener_cultivo_activo elegira otro automaticamente la proxima vez).
    """
    global _cultivo_activo_id
    lecturas_store.eliminar_cultivo(cultivo_id)

    if _cultivo_activo_id == cultivo_id:
        _cultivo_activo_id = None


def guardar_credenciales(cultivo_id, channel_id, read_api_key, write_api_key):
    """Asocia (o actualiza) el canal de ThingSpeak de un cultivo existente."""
    lecturas_store.guardar_credenciales_cultivo(
        cultivo_id, channel_id or None, read_api_key or None, write_api_key or None
    )


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

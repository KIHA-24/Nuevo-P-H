"""
Cuentas de usuario locales (sin backend externo ni dependencias nuevas, para
poder compilarse igual en el APK). La tabla "usuarios" vive en
datos_locales/lecturas.db (ver services/lecturas_store.py).

La contrasena nunca se guarda en texto plano: se deriva con PBKDF2-HMAC-SHA256
(hashlib, de la libreria estandar) usando una sal aleatoria (secrets) propia
por usuario, asi dos cuentas con la misma contrasena terminan con hashes
distintos.
"""

import hashlib
import hmac
import secrets

from services import lecturas_store

_ITERACIONES_PBKDF2 = 200_000
_LARGO_SAL_BYTES = 16

_LARGO_MINIMO_USUARIO = 3
_LARGO_MINIMO_CONTRASENA = 6


def _calcular_hash(contrasena, sal_bytes):
    return hashlib.pbkdf2_hmac(
        "sha256", contrasena.encode("utf-8"), sal_bytes, _ITERACIONES_PBKDF2
    )


def crear_usuario(usuario, contrasena):
    """
    Crea una cuenta local nueva. Retorna (ok, mensaje): mensaje es el error a
    mostrar al usuario cuando ok es False, o "" cuando ok es True.
    """
    usuario = usuario.strip()

    if len(usuario) < _LARGO_MINIMO_USUARIO or " " in usuario:
        return False, "El usuario debe tener al menos 3 caracteres"
    if len(contrasena) < _LARGO_MINIMO_CONTRASENA:
        return False, "La contraseña debe tener al menos 6 caracteres"
    if lecturas_store.obtener_usuario(usuario) is not None:
        return False, "Ese usuario ya existe"

    sal = secrets.token_bytes(_LARGO_SAL_BYTES)
    hash_contrasena = _calcular_hash(contrasena, sal)
    lecturas_store.insertar_usuario(usuario, sal.hex(), hash_contrasena.hex())
    return True, ""


def validar_usuario(usuario, contrasena):
    """True si existe esa cuenta (sin distinguir mayusculas) y la contrasena coincide."""
    fila = lecturas_store.obtener_usuario(usuario.strip())
    if fila is None:
        return False

    sal = bytes.fromhex(fila["sal"])
    hash_esperado = bytes.fromhex(fila["hash"])
    hash_calculado = _calcular_hash(contrasena, sal)
    return hmac.compare_digest(hash_calculado, hash_esperado)

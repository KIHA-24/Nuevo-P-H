"""
Logica pura de avisos de alerta del Dashboard.

Decide, variable por variable, cuando corresponde avisarle al usuario
(snackbar + notificacion nativa) segun como cambia su estado entre
refrescos. No depende de Kivy/KivyMD ni de services/ - solo recibe datos ya
calculados por la pantalla - para poder probarla sin levantar la app.

Antes el Dashboard avisaba segun el estado GENERAL del cultivo (una unica
tarjeta de estado que ya no existe). Ahora cada variable se seguimiento por
separado: una variable avisa solo cuando ENTRA a advertencia/critico, o
cuando ESCALA de advertencia a critico - no en cada refresco mientras siga
igual, y vuelve a poder avisar si primero pasa por optimo.
"""

ORDEN_VARIABLES = ("ph", "ce", "n", "p", "k", "temperatura", "humedad", "iluminacion")

NOMBRES_VARIABLE = {
    "ph": "pH",
    "ce": "CE",
    "n": "N",
    "p": "P",
    "k": "K",
    "temperatura": "Temp.",
    "humedad": "Hum.",
    "iluminacion": "Luz",
}

UNIDADES_VARIABLE = {
    "ph": "",
    "ce": "mS/cm",
    "n": "ppm",
    "p": "ppm",
    "k": "ppm",
    "temperatura": "°C",
    "humedad": "%",
    "iluminacion": "lux",
}

# pH y CE se muestran con 1 decimal (valores tipicamente entre 0 y 10); el
# resto se redondea a entero - mismo criterio que usan las tarjetas del
# Dashboard (screens/dashboard_screen.py: _DECIMALES_VALOR).
_DECIMALES = {"ph": 1, "ce": 1}

_ESTADOS_DE_ALERTA = ("advertencia", "critico")

# A partir de esta cantidad de avisos nuevos en el mismo refresco, se
# agrupan en un solo mensaje en vez de mostrar uno por variable.
UMBRAL_AGRUPADO = 3


def _formatear_num(variable, valor):
    if valor is None:
        return "--"
    return f"{valor:.{_DECIMALES.get(variable, 0)}f}"


def _es_nueva_alerta(estado_previo, estado_actual):
    """
    True si corresponde avisar de nuevo:
    - estado_previo is None: la variable no estaba siendo seguida como
      alerta (estaba en optimo/sin_datos, o es la primera vez) -> ENTRA.
    - estado_previo == "advertencia" y estado_actual == "critico" -> ESCALA.
    Bajar de critico a advertencia, o repetir el mismo estado, no genera
    un aviso nuevo (pero el estado igual se actualiza para el proximo
    refresco, ver calcular_avisos).
    """
    if estado_previo is None:
        return True
    return estado_previo == "advertencia" and estado_actual == "critico"


def _mensaje_individual(variable, estado, valor, umbrales):
    nombre = NOMBRES_VARIABLE[variable]
    unidad = UNIDADES_VARIABLE[variable]
    valor_con_unidad = f"{_formatear_num(variable, valor)} {unidad}".strip()

    minimo = umbrales.get(f"{variable}_min") if umbrales else None
    maximo = umbrales.get(f"{variable}_max") if umbrales else None
    rango = f"{_formatear_num(variable, minimo)} a {_formatear_num(variable, maximo)}"

    verbo = "fuera de rango" if estado == "critico" else "cerca del límite"
    return f"{nombre} {verbo}: {valor_con_unidad} (óptimo {rango})"


def _mensaje_agrupado(variables, estados):
    nombres = ", ".join(NOMBRES_VARIABLE[variable] for variable in variables)
    todas_criticas = all(estados[variable] == "critico" for variable in variables)
    calificativo = "fuera de rango" if todas_criticas else "requieren atención"
    return f"{len(variables)} variables {calificativo}: {nombres}"


def calcular_avisos(estados_previos, estados_actuales, valores, umbrales):
    """
    estados_previos: dict variable -> "advertencia"/"critico" de las
        variables que ya estaban en alerta en el refresco anterior (las que
        estan en optimo/sin_datos no deben aparecer aca - ver estados_nuevos
        que devuelve esta misma funcion, pensado para pasarlo tal cual como
        estados_previos del proximo refresco).
    estados_actuales: dict variable -> estado de este refresco
        (optimo/advertencia/critico/sin_datos), tal cual lo entrega
        services.thingspeak_client.obtener_estados_por_variable().
    valores: dict variable -> valor numerico actual (o None); puede traer
        claves extra (p.ej. "estado"), se ignoran.
    umbrales: dict "{variable}_min"/"{variable}_max" -> numero, tal cual lo
        entrega services.thingspeak_client.obtener_configuracion() (o {}/None
        si el cultivo todavia no tiene umbrales configurados).

    Retorna (avisos, estados_nuevos):
    - avisos: lista de {"texto": str, "es_critico": bool}, de 0 a N
      elementos (1-2 avisos individuales si hay 1-2 variables nuevas en
      alerta, o exactamente 1 agrupado si hay 3 o mas).
    - estados_nuevos: dict actualizado para pasar como estados_previos en el
      proximo refresco (solo quedan las variables en advertencia/critico).
    """
    estados_nuevos = {}
    variables_nuevas = []

    for variable in ORDEN_VARIABLES:
        estado_actual = estados_actuales.get(variable, "sin_datos")
        if estado_actual not in _ESTADOS_DE_ALERTA:
            continue  # optimo o sin_datos: se olvida, no queda rastro

        estados_nuevos[variable] = estado_actual
        if _es_nueva_alerta(estados_previos.get(variable), estado_actual):
            variables_nuevas.append(variable)

    if not variables_nuevas:
        return [], estados_nuevos

    if len(variables_nuevas) >= UMBRAL_AGRUPADO:
        avisos = [
            {
                "texto": _mensaje_agrupado(variables_nuevas, estados_nuevos),
                "es_critico": any(estados_nuevos[v] == "critico" for v in variables_nuevas),
            }
        ]
    else:
        avisos = [
            {
                "texto": _mensaje_individual(
                    variable, estados_nuevos[variable], (valores or {}).get(variable), umbrales
                ),
                "es_critico": estados_nuevos[variable] == "critico",
            }
            for variable in variables_nuevas
        ]

    return avisos, estados_nuevos

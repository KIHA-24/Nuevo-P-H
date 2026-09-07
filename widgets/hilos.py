"""
Ayuda para no trabar la interfaz mientras se espera una respuesta de red
(ThingSpeak). Sin esto, cada pantalla que pide datos se queda "pegada"
(Windows llega a mostrar "no responde") mientras dura la peticion HTTP.
"""

import threading

from kivy.clock import Clock


def ejecutar_en_segundo_plano(tarea, al_terminar):
    """
    Corre 'tarea' (una funcion sin argumentos, puede tardar) en un hilo
    aparte y, cuando termina, llama a 'al_terminar(resultado)' de vuelta en
    el hilo principal — el unico seguro para tocar widgets de Kivy.
    """

    def _trabajo():
        resultado = tarea()
        Clock.schedule_once(lambda _dt: al_terminar(resultado))

    threading.Thread(target=_trabajo, daemon=True).start()

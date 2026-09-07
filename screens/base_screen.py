class NavegableScreen:
    """
    Mixin para pantallas que solo necesitan volver al Dashboard.
    Evita repetir el mismo metodo 'volver' en detalle, historial y configuracion.
    """

    def volver(self):
        self.manager.current = "dashboard"

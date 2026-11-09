import os
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen

from services.usuarios_store import crear_usuario
from widgets.snackbar import mostrar_snackbar

Builder.load_file(os.path.join(os.path.dirname(__file__), "registro_screen.kv"))


class RegistroScreen(MDScreen):
    """Pantalla de creacion de una cuenta local nueva."""

    def limpiar_campos(self):
        self.ids.usuario.text = ""
        self.ids.contrasena.text = ""
        self.ids.confirmar_contrasena.text = ""

    def volver(self):
        self.limpiar_campos()
        self.manager.current = "login"

    def crear_cuenta(self, usuario, contrasena, confirmar_contrasena):
        if usuario.strip() == "" or contrasena == "" or confirmar_contrasena == "":
            mostrar_snackbar("Ingrese usuario y contraseña", error=True)
            return

        if contrasena != confirmar_contrasena:
            mostrar_snackbar("Las contraseñas no coinciden", error=True)
            return

        ok, mensaje = crear_usuario(usuario, contrasena)
        if not ok:
            mostrar_snackbar(mensaje, error=True)
            return

        self.limpiar_campos()
        mostrar_snackbar("Cuenta creada")
        self.manager.current = "login"

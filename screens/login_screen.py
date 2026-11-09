import os
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen

from services.usuarios_store import validar_usuario
from widgets.snackbar import mostrar_snackbar

Builder.load_file(os.path.join(os.path.dirname(__file__), "login_screen.kv"))


class LoginScreen(MDScreen):
    """Pantalla de inicio de sesion."""

    def validar_login(self, usuario, contrasena):
        if usuario.strip() == "" or contrasena.strip() == "":
            mostrar_snackbar("Ingrese usuario y contraseña", error=True)
            return

        if validar_usuario(usuario, contrasena):
            self.manager.current = "dashboard"
        else:
            mostrar_snackbar("Usuario o contraseña incorrectos", error=True)

    def ir_a_registro(self):
        self.manager.current = "registro"

    def limpiar_campos(self):
        self.ids.usuario.text = ""
        self.ids.contrasena.text = ""

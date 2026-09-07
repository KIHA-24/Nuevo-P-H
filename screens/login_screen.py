import os
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen

from widgets.snackbar import mostrar_snackbar

Builder.load_file(os.path.join(os.path.dirname(__file__), "login_screen.kv"))


class LoginScreen(MDScreen):
    """Pantalla de inicio de sesion."""

    def validar_login(self, usuario, contrasena):
        # TODO: reemplazar por validacion real (Firebase Authentication)
        if usuario.strip() != "" and contrasena.strip() != "":
            self.manager.current = "dashboard"
        else:
            mostrar_snackbar("Usuario o contrasena invalidos", error=True)

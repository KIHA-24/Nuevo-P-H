"""
HydroSmart p4a hook.

Both native crashes we've hit on the real device (SIGSEGV in the Adreno
GL driver, called from kivy/graphics/vbo.so, tid=SDLThread) happened right
after the soft keyboard closed - once from the Android back key while a
TextInput had focus, once from tapping "Iniciar sesion" right after typing
in the password field. Android's default windowSoftInputMode (unset here,
so it falls back to the theme's default) resizes the app's window/surface
when the keyboard shows or hides, which appears to race with Kivy's render
thread on this GPU and corrupt its GL state.

python-for-android's SDL2 bootstrap template has no buildozer.spec option
to set windowSoftInputMode, so this hook patches the plain-text
AndroidManifest.xml (already rendered from the template, not yet compiled
by aapt/gradle) right after it's generated, forcing android:windowSoftInputMode
="adjustPan" on the main activity so the window never resizes for the
keyboard.
"""
import re


def after_apk_build(toolchain):
    manifest_path = "AndroidManifest.xml"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_xml = f.read()

    if "windowSoftInputMode" in manifest_xml:
        return

    patched_xml, count = re.subn(
        r'(<activity\s+android:name="org\.kivy\.android\.PythonActivity")',
        r'\1 android:windowSoftInputMode="adjustPan"',
        manifest_xml,
        count=1,
    )
    if count == 0:
        raise Exception(
            "HydroSmart hook: could not find the PythonActivity tag in "
            "AndroidManifest.xml to patch windowSoftInputMode"
        )

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(patched_xml)

from pythonforandroid.recipe import PyProjectRecipe


class MaterialyoucolorRecipe(PyProjectRecipe):
    stl_lib_name = "c++_shared"
    # HydroSmart fix: python-for-android's own recipe pins 2.0.10 (Jan 2025),
    # which predates materialyoucolor's dynamiccolor/color_spec.py module.
    # KivyMD 2.0.0's theming.py imports that module directly, so the stock
    # recipe version crashes the app on Android with
    # "ModuleNotFoundError: No module named 'materialyoucolor.dynamiccolor.color_spec'"
    # even though the top-level package imports fine. Bumped to the latest
    # upstream release, which does include it (verified against the actual
    # release tarball). Not fixed upstream in python-for-android yet.
    version = "3.0.4"
    url = "https://github.com/T-Dynamos/materialyoucolor-python/releases/download/v{version}/materialyoucolor-{version}.tar.gz"

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env['LDCXXSHARED'] = env['CXX'] + ' -shared'
        return env


recipe = MaterialyoucolorRecipe()

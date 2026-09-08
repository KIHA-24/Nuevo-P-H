import sh
import os
import shutil

from multiprocessing import cpu_count
from pathlib import Path
from os.path import join

from packaging.version import Version
from pythonforandroid.logger import shprint, info, warning
from pythonforandroid.recipe import Recipe
from pythonforandroid.util import (
    BuildInterruptingException,
    current_directory,
    ensure_dir,
)
from pythonforandroid.prerequisites import OpenSSLPrerequisite

HOSTPYTHON_VERSION_UNSET_MESSAGE = "The hostpython recipe must have set version"

SETUP_DIST_NOT_FIND_MESSAGE = "Could not find Setup.dist or Setup in Python build"


class HostPython3Recipe(Recipe):
    """
    The hostpython3's recipe.

    .. versionchanged:: 2019.10.06.post0
        Refactored from deleted class ``python.HostPythonRecipe`` into here.

    .. versionchanged:: 0.6.0
        Refactored into  the new class
        :class:`~pythonforandroid.python.HostPythonRecipe`
    """

    version = "3.14.2"

    url = "https://github.com/python/cpython/archive/refs/tags/v{version}.tar.gz"
    """The default url to download our host python recipe. This url will
    change depending on the python version set in attribute :attr:`version`."""

    build_subdir = "native-build"
    """Specify the sub build directory for the hostpython3 recipe. Defaults
    to ``native-build``."""

    patches = ["fix_ensurepip.patch"]

    # apply version guard
    def download(self):
        python_recipe = Recipe.get_recipe("python3", self.ctx)
        if python_recipe.version != self.version:
            raise BuildInterruptingException(
                f"python3 should have same version as hostpython3, {python_recipe.version} != {self.version}"
            )
        super().download()

    @property
    def _exe_name(self):
        """
        Returns the name of the python executable depending on the version.
        """
        if not self.version:
            raise BuildInterruptingException(HOSTPYTHON_VERSION_UNSET_MESSAGE)
        return "python"

    @property
    def python_exe(self):
        """Returns the full path of the hostpython executable."""
        return join(self.local_bin, self._exe_name)

    def get_recipe_env(self, arch=None):
        env = os.environ.copy()
        openssl_prereq = OpenSSLPrerequisite()
        if env.get("PKG_CONFIG_PATH", ""):
            env["PKG_CONFIG_PATH"] = os.pathsep.join(
                [openssl_prereq.pkg_config_location, env["PKG_CONFIG_PATH"]]
            )
        else:
            env["PKG_CONFIG_PATH"] = openssl_prereq.pkg_config_location
        return env

    def should_build(self, arch):
        if Path(self.python_exe).exists():
            # no need to build, but we must set hostpython for our Context
            self.ctx.hostpython = self.python_exe
            return False
        return True

    def get_build_container_dir(self, arch=None):
        choices = self.check_recipe_choices()
        dir_name = "-".join([self.name] + choices)
        return join(self.ctx.build_dir, "other_builds", dir_name, "desktop")

    def get_build_dir(self, arch=None):
        """
        .. note:: Unlike other recipes, the hostpython build dir doesn't
            depend on the target arch
        """
        return join(self.get_build_container_dir(), self.name)

    def get_path_to_python(self):
        return join(self.get_build_dir(), self.build_subdir)

    @property
    def site_root(self):
        return join(self.get_path_to_python(), "root")

    @property
    def site_bin(self):
        return join(self.site_root, self.site_dir, "bin")

    @property
    def local_dir(self):
        return join(self.site_root, "usr/local/")

    @property
    def local_bin(self):
        return join(self.local_dir, "bin")

    @property
    def site_dir(self):
        p_version = Version(self.version)
        return join(
            self.site_root,
            f"usr/local/lib/python{p_version.major}.{p_version.minor}/site-packages/",
        )

    @property
    def stdlib_dir(self):
        p_version = Version(self.version)
        return join(
            self.local_dir,
            f"lib/python{p_version.major}.{p_version.minor}",
        )

    @property
    def _pip(self):
        return join(self.local_bin, "pip3")

    @property
    def pip(self):
        return sh.Command(self._pip)

    def fix_pip_shebangs(self):

        if not os.path.exists(self.local_bin):
            return

        for filename in os.listdir(self.local_bin):
            if not filename.startswith("pip"):
                continue

            pip_path = os.path.join(self.local_bin, filename)

            with open(pip_path, "rb") as file:
                file_lines = file.read().splitlines()

            file_lines[0] = f"#!{self.python_exe}".encode()

            with open(pip_path, "wb") as file:
                file.write(b"\n".join(file_lines) + b"\n")

    def ensure_venv_module(self, recipe_build_dir):
        """
        HydroSmart fix: python-for-android's own p4a_android_build /
        run_pymodules_install steps rely on this hostpython being able to
        `import venv` (used to create an isolated pip environment). We've
        seen this hostpython3 build end up without a working venv module in
        CI (cause not fully pinned down - possibly environment/PYTHONPATH
        interference from an earlier recipe in the same process), which
        crashes any requirement that isn't covered by its own p4a recipe
        (i.e. anything installed via plain pip, like most pure-Python
        KivyMD dependencies). This defensively verifies `import venv`
        actually works after the build, and repairs it by copying Lib/venv
        straight from the extracted CPython source if not.
        """
        check = sh.Command(self.python_exe)
        try:
            check("-c", "import venv")
            return
        except sh.ErrorReturnCode:
            pass

        warning(
            "hostpython3: 'import venv' failed after build, repairing by "
            "copying Lib/venv from source into the installed stdlib"
        )
        source_venv_dir = join(recipe_build_dir, "Lib", "venv")
        dest_venv_dir = join(self.stdlib_dir, "venv")
        if not Path(source_venv_dir).is_dir():
            raise BuildInterruptingException(
                f"hostpython3: cannot repair venv module, "
                f"{source_venv_dir} does not exist either"
            )
        if Path(dest_venv_dir).exists():
            shutil.rmtree(dest_venv_dir)
        shutil.copytree(source_venv_dir, dest_venv_dir)

        # verify again, fail loudly with a clear message if still broken
        check("-c", "import venv")
        info("hostpython3: venv module repaired successfully")

    def build_arch(self, arch):
        env = self.get_recipe_env(arch)

        recipe_build_dir = self.get_build_dir(arch.arch)

        # Create a subdirectory to actually perform the build
        build_dir = join(recipe_build_dir, self.build_subdir)
        ensure_dir(build_dir)

        # Configure the build
        with current_directory(build_dir):
            if not Path("config.status").exists():
                shprint(
                    sh.Command(join(recipe_build_dir, "configure")),
                    "--prefix",
                    self.local_dir,
                    _env=env,
                )

        with current_directory(recipe_build_dir):
            # Create the Setup file. This copying from Setup.dist is
            # the normal and expected procedure before Python 3.8, but
            # after this the file with default options is already named "Setup"
            setup_dist_location = join("Modules", "Setup.dist")
            if Path(setup_dist_location).exists():
                shprint(sh.cp, setup_dist_location, join(build_dir, "Modules", "Setup"))
            else:
                # Check the expected file does exist
                setup_location = join("Modules", "Setup")
                if not Path(setup_location).exists():
                    raise BuildInterruptingException(SETUP_DIST_NOT_FIND_MESSAGE)

            shprint(sh.make, "-j", str(cpu_count()), "-C", build_dir, _env=env)

        with current_directory(build_dir):
            shprint(sh.make, "install", _env=env)

        with current_directory(recipe_build_dir):
            # make a copy of the python executable giving it the name we want,
            # because we got different python's executable names depending on
            # the fs being case-insensitive (Mac OS X, Cygwin...) or
            # case-sensitive (linux)...so this way we will have an unique name
            # for our hostpython, regarding the used fs
            for exe_name in ["python.exe", "python"]:
                exe = join(self.get_path_to_python(), exe_name)
                if Path(exe).is_file():
                    shprint(sh.cp, exe, self.python_exe)
                    break

        ensure_dir(self.site_root)
        self.ctx.hostpython = self.python_exe

        # HydroSmart fix: always (not just on a fresh ./configure) make sure
        # pip and the venv module are usable - see ensure_venv_module() above.
        shprint(
            sh.Command(self.python_exe),
            "-m",
            "ensurepip",
            "-U",
            _env={"HOME": "/tmp", "PATH": self.local_bin},
        )
        self.fix_pip_shebangs()
        self.ensure_venv_module(recipe_build_dir)


recipe = HostPython3Recipe()

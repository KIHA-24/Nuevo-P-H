[app]

# (str) Title of your application
title = HydroSmart

# (str) Package name
package.name = hydrosmart

# (str) Package domain (needed for android/ios packaging)
package.domain = org.hydrosmart

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (leave empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (str) Application versioning (method 1)
version = 0.1

# (list) Application requirements
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.1,kivymd==2.0.0,requests,pillow

# (str) Custom local recipes to override the default python-for-android ones.
# python3/__init__.py here is a copy of the upstream recipe with one line
# added to get_recipe_env(): it skips CPython's own autoconf check that
# turns implicit function declarations into a hard compile error, which
# otherwise breaks building CPython's grp module for Android (Android's
# libc doesn't declare setgrent/getgrent/endgrent). Not fixed upstream yet.
p4a.local_recipes = ./p4a-recipes

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (list) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = android.permission.INTERNET

# (int) Target Android API, should be as high as possible.
#android.api = 33

# (int) Minimum API your APK / AAB will support.
#android.minapi = 24

# (str) Android NDK version to use
android.ndk = 25b

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1

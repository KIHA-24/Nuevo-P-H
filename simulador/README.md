# Simulador de sensores HydroSmart

Herramienta de desarrollo, **no forma parte de la app**: no se empaqueta en
el APK (no toca `buildozer.spec`) y no modifica nada dentro de `screens/`,
`services/` ni `widgets/`.

## Para que sirve

Mientras el hardware real (sensores fisicos) no esta listo, esta herramienta
manda lecturas de prueba directamente al canal de ThingSpeak de un cultivo,
para poder probar el resto de la app (dashboard, alertas, graficas,
historial) con datos que sí llegan.

## Como correrlo

```
python simulador/simulador.py
```

Usa Tkinter (incluido en Python) y `requests` (ya es dependencia del
proyecto), asi que no hace falta instalar nada nuevo si ya tienes el
entorno de la app funcionando.

## Como usarlo

1. Elegi el cultivo desde el dropdown (se lee de
   `datos_locales/cultivos.json`, mismo archivo que usa la app). Si acabas
   de agregar o editar credenciales desde la pantalla de Configuracion de
   la app mientras el simulador ya estaba abierto, usa el boton
   "↻ Recargar".
2. Llena los 8 campos (pH, CE, N, P, K, Temperatura, Humedad,
   Iluminacion) a mano, o usa uno de los 3 botones de perfil rapido
   (Optimo / Advertencia / Critico) como punto de partida y edita lo que
   quieras despues.
3. Boton "Enviar lectura": manda esos valores al canal del cultivo
   seleccionado.
4. Checkbox "Modo automatico": si lo activas, manda una lectura cada 20
   segundos con una pequena variacion aleatoria (±3%) sobre los valores
   actuales de los campos, para simular sensores fluctuando y ver moverse
   las graficas de tendencia. Se detiene destildando el mismo checkbox.

## Notas

- El cultivo seleccionado debe tener `write_api_key` configurada (se
  agrega desde la pantalla de Configuracion en la app). Si falta, el
  simulador lo avisa y no deja enviar.
- ThingSpeak (cuenta gratis) solo acepta **1 actualizacion cada 15
  segundos** por canal. Si mandas lecturas mas seguido (o el modo
  automatico de dos cultivos comparte canal), el simulador va a mostrar el
  mensaje de rechazo - no es un bug, es el limite de la cuenta gratis.

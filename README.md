# Sistema de correos y clasificación de ofertas — APK

Repo del sistema nuevo de ofertas laborales de APK Cultural Exchange:
lee ofertas (primero las del scraper, luego las que llegan por correo),
las clasifica, las deja en el Formato Único, evita duplicados y calcula
el match con porcentaje contra el perfil del participante.

## Estado (25 nov 2026, v1)

- Clasificador listo y probado: **24 pruebas, todas pasan**.
- Probado con 10 ofertas reales del scraper: **5 con etiqueta completa,
  2 solo con carrera, 3 sin etiqueta** (programas rotativos, los define
  el asesor). El match del perfil ejemplo da 90% en las dos de recepción.
- La parte de correos está bloqueada hasta tener el acceso al correo
  donde llegan las ofertas (Sonia o Luciana) y a los portales.

## Archivos

- `clasificador_ofertas.py`: el clasificador. Solo Python estándar, sin dependencias.
- `test_clasificador.py`: 24 pruebas.
- `probar_con_scraper.py`: pasa 10 ofertas reales por el clasificador.
- `ofertas_reales_10.json`: las 10 ofertas textuales del scraper.
- `resultado_prueba_scraper.txt`: la salida de la prueba.

## Cómo correrlo

```bash
python3 -m unittest test_clasificador -v   # las 24 pruebas
python3 probar_con_scraper.py              # la prueba con ofertas reales
```

## Qué hace

1. **Etiquetas**: normaliza el puesto a (carrera, especialidad, posición)
   con la lista del borrador del 21 nov 2026. Sinónimos confirmados:
   camarero/a → mesero/a, host → anfitrión/a, "social media program" y
   "creador de contenido" → Marketing. Vocabulario del scraper incluido
   (server, front office, culinary, etc.).
2. **Formato Único**: arma los 22 campos del doc del 23 nov 2026.
   Lo que no viene queda "por confirmar"; nunca se inventa.
3. **Anti-duplicados**: clave sponsor + puesto normalizado + ubicación +
   fecha de inicio aproximada (año-mes). La misma oferta por portal y
   por correo da la misma clave.
4. **Match con porcentaje**: pesos del ejemplo de la reunión (carrera 40,
   experiencia 25, educación 15, inglés 10, preferencias 10). Devuelve
   el % más qué coincidió y qué falta. Los honores no restan.
5. **Clasifica correo**: oferta / no es oferta / revisar (heurística v1).

## Reglas

- Lo exacto va en la etiqueta; el match sale con porcentaje, no exacto.
- Solo lo marcado "Confirmado en la reunión" es dato de APK; las filas
  "Propuesta" del borrador son un punto de partida y el equipo las corrige.
- Los pesos exactos y el % mínimo para avisar al asesor los define el equipo.

## Datos del scraper

- Fuente: `frontend/public/jobs.json` del repo `apk_ofertas_laborales`,
  387 ofertas activas, generado el 18 nov 2026.
- Ojo: el dato público del scraper casi nunca trae el sponsor (`company`
  en null, lo sanitiza el generador), así que la clave anti-duplicados va
  con el sponsor vacío en esos casos. El sponsor real está en la base
  privada del scraper o llega en el correo.
- Los datos tenían 7 días al 25 nov 2026 (último commit 18 nov, aunque el
  flujo corre a diario): confirmar con Ale/Zair si es normal.

## Qué falta

- Acceso al correo de ofertas y a los portales de los sponsors.
- Dónde corre el sistema nuevo.
- Confirmar las etiquetas en estado "Propuesta" y los pesos exactos.
- Conectar con el scraper y con el sistema de CV (repos separados hoy).

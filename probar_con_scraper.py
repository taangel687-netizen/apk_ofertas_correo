#!/usr/bin/env python3
"""Prueba del clasificador con 10 ofertas reales del scraper.

Fuente: frontend/public/jobs.json del repo apk-peru/apk_ofertas_laborales,
generado el 18 nov 2026 (total declarado: 387 ofertas activas). Las 10
ofertas están textuales en ofertas_reales_10.json.

El perfil es el EJEMPLO ILUSTRATIVO del borrador del 21 nov (no es un
aplicante real): turismo, recepción, 1 año de experiencia, estudios afines,
sin inglés acreditado, prefiere hotelería.
Correr: python3 probar_con_scraper.py
"""

import json

from clasificador_ofertas import (
    a_formato_unico,
    clave_duplicado,
    mapear_oferta_scraper,
    match,
)

PERFIL_EJEMPLO = {
    "carrera": "Turismo",
    "experiencia_anios": 1,
    "estudios_afines": True,
    "ingles": "",
    "preferencias": ["hotelería"],
}


def main():
    with open("ofertas_reales_10.json", encoding="utf-8") as fh:
        jobs = json.load(fh)
    print("Ofertas reales: %d (de 387 activas en jobs.json, generado 18 nov 2026)"
          % len(jobs))
    print()
    n_ok = n_parcial = n_sin = 0
    for i, job in enumerate(jobs, 1):
        cruda = mapear_oferta_scraper(job)
        f = a_formato_unico(
            cruda, fuente="portal (scraper)",
            archivo_origen="jobs.json #%s" % job["share_id"],
            correlativo=i)
        f["experiencia_min_anios"] = cruda["experiencia_min_anios"]
        f["requiere_estudios"] = cruda["requiere_estudios"]
        m = match(f, PERFIL_EJEMPLO)
        etiqueta = "%s / %s / %s" % (f["carrera"], f["especialidad"], f["posicion"])
        if f["posicion"] != "por confirmar" and f["carrera"] != "por confirmar":
            n_ok += 1
        elif f["carrera"] != "por confirmar":
            n_parcial += 1
        else:
            n_sin += 1
        print("%d. %s | %s | %s | %s"
              % (i, job["title"], job.get("company") or "sponsor: por confirmar",
                 f["ubicacion"], f["programa"]))
        print("   etiqueta: %s" % etiqueta)
        print("   match con perfil ejemplo (turismo/recepción): %s%% | coincide: %s | falta: %s"
              % (m["porcentaje"],
                 ", ".join(m["que_coincidio"]) or "-",
                 ", ".join(m["que_falta"]) or "-"))
        print("   clave duplicado: %s" % clave_duplicado(f))
        if f["notas"]:
            print("   notas: %s" % f["notas"])
    print()
    print("Resumen: %d con etiqueta completa, %d solo con carrera, "
          "%d sin etiqueta (por confirmar)." % (n_ok, n_parcial, n_sin))


if __name__ == "__main__":
    main()

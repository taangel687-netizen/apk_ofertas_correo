#!/usr/bin/env python3
"""
Clasificador de ofertas laborales de APK — v1 (25 nov 2026).

Qué hace:
  1. Normaliza el puesto de una oferta a la etiqueta canónica (carrera, especialidad,
     posición) según el borrador de carreras del 21 nov 2026.
  2. Arma el Formato Único de Oferta (22 campos, doc del 23 nov 2026).
  3. Calcula la clave anti-duplicados (sponsor + puesto normalizado + ubicación
     + fecha de inicio aproximada) contra el scraper y el correo.
  4. Calcula el match con porcentaje contra el perfil del participante.
  5. Clasifica un correo: oferta de trabajo o no (heurística v1).

Reglas que vienen de la reunión del 20 nov y de los documentos (no inventadas):
  - Lo exacto va en la ETIQUETA (los sinónimos se normalizan a una sola etiqueta);
    el MATCH sale con porcentaje, no exacto.
  - Pesos del ejemplo propuesto en la reunión (40/25/15/10/10). Los pesos exactos
    y el porcentaje mínimo para avisar los define el equipo: aquí van como
    PESOS_EJEMPLO y se pueden cambiar en un solo lugar.
  - Los honores valen menos en el porcentaje, NUNCA restan (aclarado por Angel).
  - Lo que no viene en la fuente queda "por confirmar": nunca se inventa.
  - Solo lo marcado "Confirmado en la reunión" es dato de APK; las filas
    "Propuesta" del borrador son un punto de partida y el equipo las corrige.

No lee correo ni portales: eso necesita el acceso al correo (de Sonia o Luciana)
y a los portales, que a 25 nov 2026 sigue pendiente. Este módulo trabaja con
ofertas ya estructuradas (las del scraper o las que lleguen por correo).
"""

from __future__ import annotations

import re
import unicodedata

POR_CONFIRMAR = "por confirmar"

# ---------------------------------------------------------------------------
# 1. Etiquetas canónicas (borrador 21 nov 2026, Alcance 1)
#    (carrera, especialidad, posición canónica, estado)
# ---------------------------------------------------------------------------
ETIQUETAS = [
    ("Gastronomía", "Cocina", "cocinero/a", "Propuesta"),
    ("Gastronomía", "Cocina", "ayudante de cocina", "Propuesta"),
    ("Gastronomía", "Cocina", "panadero/a - pastelero/a", "Propuesta"),
    ("Gastronomía", "Servicio de sala", "mesero/a", "Propuesta"),
    ("Gastronomía", "Servicio de sala", "bartender", "Propuesta"),
    ("Gastronomía", "Servicio de sala", "anfitrión/a", "Propuesta"),
    ("Hotelería", "Recepción", "recepcionista", "Propuesta"),
    ("Hotelería", "Recepción", "botones", "Propuesta"),
    ("Hotelería", "Recepción", "conserje", "Propuesta"),
    ("Hotelería", "Housekeeping", "camarero/a de pisos", "Propuesta"),
    ("Hotelería", "Housekeeping", "lavandería", "Propuesta"),
    ("Hotelería", "Alimentos y bebidas", "mesero/a", "Propuesta"),
    ("Hotelería", "Alimentos y bebidas", "bartender", "Propuesta"),
    ("Turismo", "Guía", "guía turístico/a", "Confirmado en la reunión"),
    ("Turismo", "Recepción", "recepcionista", "Confirmado en la reunión"),
    ("Turismo", "Ventas y reservas", "agente de viajes", "Propuesta"),
    ("Turismo", "Ventas y reservas", "reservas", "Propuesta"),
]

# Sinónimos que se normalizan a la etiqueta canónica.
# Clave: forma normalizada del texto; valor: etiqueta canónica.
SINONIMOS_POSICION = {
    "camarero": "mesero/a",
    "camarera": "mesero/a",
    "mesero": "mesero/a",
    "mesera": "mesero/a",
    "host": "anfitrión/a",
    "hostess": "anfitrión/a",
    "anfitrion": "anfitrión/a",
    "anfitriona": "anfitrión/a",
    "recepcionista": "recepcionista",
    "front desk": "recepcionista",
    "guia turistico": "guía turístico/a",
    "tour guide": "guía turístico/a",
    "cocinero": "cocinero/a",
    "cocinera": "cocinero/a",
    "bartender": "bartender",
    "barman": "bartender",
    "botones": "botones",
    "bellboy": "botones",
    "conserje": "conserje",
    "concierge": "conserje",
    "agente de viajes": "agente de viajes",
    "travel agent": "agente de viajes",
    "ayudante de cocina": "ayudante de cocina",
    "kitchen helper": "ayudante de cocina",
    "panadero": "panadero/a - pastelero/a",
    "pastelero": "panadero/a - pastelero/a",
    "camarero de pisos": "camarero/a de pisos",
    "housekeeping": "camarero/a de pisos",
    "lavanderia": "lavandería",
    "laundry": "lavandería",
    "reservas": "reservas",
    "reservations": "reservas",
    # Vocabulario del scraper (ofertas reales de jobs.json, 18 nov 2026).
    "server": "mesero/a",
    "food and beverage": "mesero/a",
    "f b": "mesero/a",
    "culinary": "cocinero/a",
    "cocina": "cocinero/a",
    "recepcion": "recepcionista",
    "front office": "recepcionista",
}

# Sinónimos confirmados en la reunión: van a marketing aunque se llamen distinto.
SINONIMOS_CARRERA = {
    "social media program": "Marketing",
    "creador de contenido": "Marketing",
    "content creator": "Marketing",
    "social media": "Marketing",
}

# Carreras del Alcance 2 (borrador 21 nov: por definir). Solo se etiqueta la carrera.
ALCANCE2 = {
    "accounting": "Administración",
    "contabilidad": "Administración",
    "engineering": "Ingeniería",
    "ingenieria": "Ingeniería",
    "architecture": "Arquitectura",
    "arquitectura": "Arquitectura",
    "marketing": "Marketing",
}

# Pesos del ejemplo propuesto en la reunión (a confirmar por el equipo).
PESOS_EJEMPLO = {
    "carrera": 0.40,
    "experiencia": 0.25,
    "educacion": 0.15,
    "ingles": 0.10,
    "preferencias": 0.10,
}

# Niveles de inglés, de menor a mayor (en español y en inglés, como vienen del scraper).
NIVEL_INGLES = {"básico": 1, "basico": 1, "basic": 1, "intermedio": 2,
                "intermediate": 2, "avanzado": 3, "advanced": 3,
                "excellent": 3, "excelente": 3, "fluent": 3}

ESTADOS = ["nueva", "avisada al asesor", "confirmada", "enviada al participante"]


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples, para comparar."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def clasificar_puesto(texto_puesto: str, texto_oferta: str = ""):
    """
    Devuelve (carrera, especialidad, posición canónica, estado, nota) o
    (None, None, None, None, "por confirmar: ...") si no se reconoce.

    Si la posición existe en más de una carrera (ej. recepcionista en
    Hotelería y en Turismo), el contexto del texto decide: "hotel" tira a
    Hotelería, "turismo/viaje/agencia" tira a Turismo; sin contexto queda
    Hotelería (primera en la lista) y se anota para que el asesor revise.
    Los programas rotativos (varias áreas) no se etiquetan: los define el asesor.
    """
    texto = normalizar(texto_puesto or "")
    contexto = normalizar(f"{texto_puesto or ''} {texto_oferta or ''}")
    if not texto:
        return None, None, None, None, "por confirmar: puesto vacío"

    # Programa rotativo: cubre varias áreas, no es una sola posición.
    if any(p in contexto for p in ("rotational", "rotacion", "rotation")):
        return None, None, None, None, \
            "por confirmar: programa rotativo, varias áreas; lo define el asesor"

    # Sinónimos de carrera confirmados (ej. social media program -> Marketing).
    for sinonimo, carrera in SINONIMOS_CARRERA.items():
        if normalizar(sinonimo) in contexto:
            return (carrera, POR_CONFIRMAR, normalizar(sinonimo),
                    "Confirmado en la reunión",
                    "Posición fuera del Alcance 1: se etiqueta solo la carrera, "
                    "la especialidad la define el equipo.")

    # Posición por sinónimo: gana el término más específico (el más largo).
    posicion = SINONIMOS_POSICION.get(texto)
    if posicion is None:
        for sinonimo, canonica in sorted(SINONIMOS_POSICION.items(),
                                         key=lambda kv: -len(kv[0])):
            if len(sinonimo) >= 4 and normalizar(sinonimo) in contexto:
                posicion = canonica
                break
    if posicion is None:
        # Carreras del Alcance 2 (por definir): solo se etiqueta la carrera.
        for palabra, carrera in ALCANCE2.items():
            if normalizar(palabra) in contexto:
                return (carrera, POR_CONFIRMAR, POR_CONFIRMAR,
                        "Alcance 2 por definir",
                        "Carrera fuera del Alcance 1: la especialidad y la "
                        "posición las define el equipo.")
        return None, None, None, None, "por confirmar: posición no está en la lista"

    candidatos = [e for e in ETIQUETAS if e[2] == posicion]
    if len(candidatos) == 1:
        carrera, especialidad, _, estado = candidatos[0]
        return carrera, especialidad, posicion, estado, ""
    # Posición en más de una carrera: el contexto decide.
    nota = ""
    if "hotel" in contexto or "hospedaje" in contexto or "alojamiento" in contexto:
        elegido = [e for e in candidatos if e[0] == "Hotelería"]
    elif "turismo" in contexto or "viaje" in contexto or "agencia" in contexto:
        elegido = [e for e in candidatos if e[0] == "Turismo"]
    else:
        elegido = []
    if not elegido:
        elegido = candidatos[:1]
        nota = "Revisar carrera: la posición existe en más de una carrera."
    carrera, especialidad, _, estado = elegido[0]
    return carrera, especialidad, posicion, estado, nota


MESES_ES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "setiembre": "09", "octubre": "10",
            "noviembre": "11", "diciembre": "12"}


def clave_duplicado(oferta: dict) -> str:
    """
    Dos ofertas son la MISMA si coinciden en: sponsor + puesto normalizado
    (en minúsculas, sin sinónimos) + ubicación + fecha de inicio aproximada.
    """
    sponsor = normalizar(str(oferta.get("sponsor", "")))
    puesto = oferta.get("posicion_canonica") or oferta.get("posicion") or ""
    if not puesto or puesto == POR_CONFIRMAR:
        puesto = oferta.get("puesto", "")
    puesto = normalizar(str(puesto))
    ubicacion = normalizar(str(oferta.get("ubicacion", "")))
    inicio = normalizar(str(oferta.get("fecha_inicio", "")))
    # Fecha aproximada: año-mes, aunque el mes venga escrito ("junio 2027").
    m = re.search(r"(20\d\d)[- /]?(\d{1,2})?", inicio)
    if m:
        mes = m.group(2)
        if not mes:
            for nombre, num in MESES_ES.items():
                if nombre in inicio:
                    mes = num
                    break
        inicio = m.group(1) + ("-" + mes.zfill(2) if mes else "")
    return "|".join([sponsor, puesto, ubicacion, inicio])


CAMPOS_FORMATO_UNICO = [
    "id_oferta", "fuente", "sponsor", "programa", "puesto", "carrera",
    "especialidad", "posicion", "texto original del puesto", "ubicacion",
    "fecha_inicio", "fecha_fin / duracion", "salario / pago", "horas",
    "ingles requerido", "experiencia requerida", "fecha_cierre", "estado",
    "asesor", "archivo_origen", "duplicado_de", "notas",
]

# Campos que no pueden quedar en "por confirmar": sin ellos no se avisa.
CAMPOS_OBLIGATORIOS = [
    "id_oferta", "fuente", "sponsor", "programa", "puesto", "carrera",
    "especialidad", "posicion", "texto original del puesto", "ubicacion",
    "fecha_cierre", "estado", "archivo_origen", "duplicado_de",
]


def a_formato_unico(oferta_cruda: dict, fuente: str, archivo_origen: str,
                    correlativo: int, sponsor: str = "") -> dict:
    """
    Arma los 22 campos del Formato Único desde una oferta cruda.
    Lo que no viene queda "por confirmar": nunca se inventa.
    """
    puesto = str(oferta_cruda.get("puesto", "") or "")
    carrera, especialidad, posicion, estado_etiqueta, nota = clasificar_puesto(
        puesto, str(oferta_cruda.get("texto", "") or ""))
    fecha_cierre = oferta_cruda.get("fecha_cierre") or POR_CONFIRMAR
    if fecha_cierre == POR_CONFIRMAR:
        fecha_cierre = (str(oferta_cruda.get("fecha_recepcion", "")) or POR_CONFIRMAR) + \
            " (por confirmar, urgente por fecha de recepción)" \
            if oferta_cruda.get("fecha_recepcion") else POR_CONFIRMAR
    notas = []
    if nota:
        notas.append(nota)
    if estado_etiqueta == "Propuesta":
        notas.append("Etiqueta en estado Propuesta (borrador 21 nov): el equipo la confirma.")
    if oferta_cruda.get("notas"):
        notas.append(str(oferta_cruda["notas"]))
    return {
        "id_oferta": f"OF-2026-{correlativo:04d}",
        "fuente": fuente,
        "sponsor": oferta_cruda.get("sponsor") or sponsor or POR_CONFIRMAR,
        "programa": oferta_cruda.get("programa") or POR_CONFIRMAR,
        "puesto": puesto or POR_CONFIRMAR,
        "carrera": carrera or POR_CONFIRMAR,
        "especialidad": especialidad or POR_CONFIRMAR,
        "posicion": posicion or POR_CONFIRMAR,
        "texto original del puesto": puesto or POR_CONFIRMAR,
        "ubicacion": oferta_cruda.get("ubicacion") or POR_CONFIRMAR,
        "fecha_inicio": oferta_cruda.get("fecha_inicio") or POR_CONFIRMAR,
        "fecha_fin / duracion": oferta_cruda.get("fecha_fin") or oferta_cruda.get("duracion") or POR_CONFIRMAR,
        "salario / pago": oferta_cruda.get("salario") or POR_CONFIRMAR,
        "horas": oferta_cruda.get("horas") or POR_CONFIRMAR,
        "ingles requerido": oferta_cruda.get("ingles") or POR_CONFIRMAR,
        "experiencia requerida": oferta_cruda.get("experiencia") or POR_CONFIRMAR,
        "fecha_cierre": fecha_cierre,
        "estado": "nueva",
        "asesor": oferta_cruda.get("asesor") or POR_CONFIRMAR,
        "archivo_origen": archivo_origen,
        "duplicado_de": oferta_cruda.get("duplicado_de") or "",
        "notas": "; ".join(notas),
    }


def _puntaje_carrera(oferta: dict, perfil: dict) -> float:
    """1.0 si la posición de la oferta vale para la carrera del participante."""
    posicion = oferta.get("posicion")
    carrera_perfil = perfil.get("carrera")
    if not posicion or not carrera_perfil:
        return 0.0
    validas = [e for e in ETIQUETAS
               if e[2] == posicion and e[0].lower() == str(carrera_perfil).lower()]
    if validas:
        return 1.0
    # La posición existe pero en otra carrera: no suma en carrera.
    return 0.0


def _puntaje_experiencia(oferta: dict, perfil: dict) -> float:
    """Según años del participante frente a lo que pide la oferta."""
    requerido = oferta.get("experiencia_min_anios")
    anios = perfil.get("experiencia_anios", 0) or 0
    if requerido is None:
        return 1.0
    if anios <= 0:
        return 0.0
    if anios >= requerido:
        return 1.0
    return round(anios / requerido, 2)


def _puntaje_educacion(oferta: dict, perfil: dict) -> float:
    if not oferta.get("requiere_estudios"):
        return 1.0
    if perfil.get("estudios_afines"):
        return 1.0
    if perfil.get("estudios"):
        return 0.5
    return 0.0


def _puntaje_ingles(oferta: dict, perfil: dict) -> float:
    requerido = normalizar(str(oferta.get("ingles requerido") or ""))
    tiene = normalizar(str(perfil.get("ingles") or ""))
    if not requerido or requerido == normalizar(POR_CONFIRMAR):
        return 1.0
    if not tiene:
        return 0.0
    req = NIVEL_INGLES.get(requerido)
    ten = NIVEL_INGLES.get(tiene)
    if req is None or ten is None:
        return 0.5
    if ten >= req:
        return 1.0
    if ten == req - 1:
        return 0.5
    return 0.0


def _puntaje_preferencias(oferta: dict, perfil: dict) -> float:
    prefs = [normalizar(str(p)) for p in (perfil.get("preferencias") or [])
             if normalizar(str(p))]
    if not prefs:
        return 0.5
    area = normalizar(str(oferta.get("carrera") or ""))
    ubic = normalizar(str(oferta.get("ubicacion") or ""))
    aciertos = sum(1 for p in prefs if p in area or p in ubic)
    if aciertos == len(prefs):
        return 1.0
    if aciertos >= 1:
        return 0.5
    return 0.0


def match(oferta: dict, perfil: dict, pesos: dict | None = None) -> dict:
    """
    Match con porcentaje. oferta y perfil usan los campos del Formato Único
    (oferta) y del formulario corto del participante (perfil).
    Devuelve porcentaje, puntaje por factor, qué coincidió y qué falta.
    Los honores NO entran como resta: solo valen menos (no se descuentan).
    """
    pesos = pesos or PESOS_EJEMPLO
    puntajes = {
        "carrera": _puntaje_carrera(oferta, perfil),
        "experiencia": _puntaje_experiencia(oferta, perfil),
        "educacion": _puntaje_educacion(oferta, perfil),
        "ingles": _puntaje_ingles(oferta, perfil),
        "preferencias": _puntaje_preferencias(oferta, perfil),
    }
    total = sum(puntajes[k] * pesos[k] for k in pesos)
    porcentaje = round(total * 100, 1)
    nombres = {
        "carrera": "carrera",
        "experiencia": "experiencia",
        "educacion": "educación",
        "ingles": "inglés",
        "preferencias": "preferencias",
    }
    coincide = [nombres[k] for k, v in puntajes.items() if v >= 1.0]
    falta = [nombres[k] for k, v in puntajes.items() if v < 1.0]
    return {
        "porcentaje": porcentaje,
        "puntajes": puntajes,
        "que_coincidio": coincide,
        "que_falta": falta,
    }


def es_oferta_trabajo(texto: str) -> str:
    """
    Clasifica un correo: 'oferta', 'no es oferta' o 'revisar'.
    Heurística v1 por palabras clave; el asesor confirma lo dudoso.
    """
    t = normalizar(texto or "")
    if not t:
        return "revisar"
    senales_oferta = [
        "vacancy", "vacante", "position", "puesto", "job offer", "oferta",
        "we are looking", "se busca", "hiring", "contratacion", "sponsor",
        "internship", "trainee", "work and travel", "camp counselor",
        "au pair", "seasonal", "employer", "empleador",
    ]
    senales_no_oferta = [
        "gracias por", "thank you for", "confirmacion de pago", "payment confirmation",
        "unsubscribe", "darse de baja", "newsletter", "boletin",
    ]
    if any(s in t for s in senales_no_oferta) and not any(
            s in t for s in ["vacancy", "vacante", "position", "puesto"]):
        return "no es oferta"
    if any(s in t for s in senales_oferta):
        return "oferta"
    return "revisar"


def mapear_oferta_scraper(job: dict) -> dict:
    """
    Convierte una entrada de jobs.json (scraper) al formato crudo del clasificador.
    Reglas v1, documentadas:
      - program_type "Trainee" -> Trainee; "Intern" -> Internship USA, salvo que
        el país sea España (Internship España).
      - fecha_inicio: earliest_start_date si viene, si no start_date (a veces es
        texto libre, ej. "Early 2027").
      - El dato público del scraper NO trae el sponsor (company suele ser null:
        el generador lo sanitiza); queda por confirmar.
      - Si pide experiencia previa sin años, se toma 1 año (regla v1).
      - Si pide estudiantes/egresados, requiere estudios.
    """
    titulo = str(job.get("title") or "")
    company = job.get("company")
    partes_ubic = [job.get("location"), job.get("state"), job.get("country")]
    ubicacion = ", ".join(str(p) for p in partes_ubic if p)
    ptype = str(job.get("program_type") or "").strip().lower()
    pais = str(job.get("country") or "").strip().lower()
    if ptype == "trainee":
        programa = "Trainee"
    elif ptype == "intern":
        programa = "Internship España" if pais in ("spain", "españa") else "Internship USA"
    elif ptype:
        programa = str(job.get("program_type"))
    else:
        programa = POR_CONFIRMAR
    contexto = " ".join(str(job.get(k) or "") for k in
                        ("category", "description", "full_description", "training_plan"))
    texto_req = normalizar(
        str(job.get("requirements") or "") + " " + str(job.get("candidate_profile") or ""))
    notas = []
    if not company:
        notas.append("Sponsor no viene en el dato público del scraper (por confirmar).")
    if "sala" in normalizar(titulo) and "cocina" in normalizar(titulo):
        notas.append("Cubre cocina y sala; la etiqueta es la de cocina.")
    return {
        "puesto": titulo,
        "sponsor": company or "",
        "ubicacion": ubicacion,
        "programa": programa,
        "fecha_inicio": job.get("earliest_start_date") or job.get("start_date") or "",
        "fecha_fin": job.get("end_date") or "",
        "duracion": job.get("duration_text") or "",
        "salario": job.get("compensation_text") or "",
        "horas": str(job.get("hours_per_week")) if job.get("hours_per_week") else "",
        "ingles": job.get("english_level") or "",
        "experiencia": job.get("requirements") or job.get("candidate_profile") or "",
        "experiencia_min_anios": 1 if ("experience" in texto_req or "experiencia" in texto_req) else None,
        "requiere_estudios": ("student" in texto_req or "graduate" in texto_req
                              or "estudiante" in texto_req or "egresado" in texto_req),
        "fecha_cierre": job.get("listing_expires") or "",
        "fecha_recepcion": str(job.get("first_seen") or "")[:10],
        "texto": contexto,
        "notas": "; ".join(notas),
    }


if __name__ == "__main__":
    demo = a_formato_unico(
        {"puesto": "Recepcionista de hotel", "sponsor": "CHI",
         "ubicacion": "Orlando, Florida", "programa": "Internship USA",
         "ingles": "intermedio", "texto": "Hotel receptionist, Orlando FL"},
        fuente="portal", archivo_origen="scraper_chi.json", correlativo=1)
    print("Formato único (demo):")
    for k, v in demo.items():
        print(f"  {k}: {v}")
    perfil = {"carrera": "Turismo", "experiencia_anios": 1,
              "estudios_afines": True, "ingles": "básico",
              "preferencias": ["hotelería"]}
    oferta = dict(demo)
    oferta["experiencia_min_anios"] = 2
    print("\nMatch (demo):", match(oferta, perfil))
    print("Clave duplicado:", clave_duplicado(demo))

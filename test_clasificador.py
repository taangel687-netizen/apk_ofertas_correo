#!/usr/bin/env python3
"""Pruebas del clasificador v1. Correr: python3 -m unittest test_clasificador -v"""

import unittest

from clasificador_ofertas import (
    POR_CONFIRMAR,
    a_formato_unico,
    clasificar_puesto,
    clave_duplicado,
    es_oferta_trabajo,
    match,
)


class TestEtiquetas(unittest.TestCase):
    def test_camarero_es_mesero(self):
        carrera, esp, pos, _, _ = clasificar_puesto("Camarero/a")
        self.assertEqual(pos, "mesero/a")
        self.assertIn(carrera, ("Gastronomía", "Hotelería"))

    def test_host_es_anfitrion(self):
        _, _, pos, _, _ = clasificar_puesto("HOST")
        self.assertEqual(pos, "anfitrión/a")

    def test_recepcionista_hotel_es_hoteleria(self):
        carrera, esp, pos, _, _ = clasificar_puesto(
            "Recepcionista", "Hotel receptionist, Orlando FL")
        self.assertEqual((carrera, esp, pos),
                         ("Hotelería", "Recepción", "recepcionista"))

    def test_recepcionista_turismo_es_turismo(self):
        carrera, esp, pos, _, _ = clasificar_puesto(
            "Recepcionista", "Agencia de turismo, recepción")
        self.assertEqual((carrera, esp, pos),
                         ("Turismo", "Recepción", "recepcionista"))

    def test_social_media_es_marketing(self):
        carrera, _, pos, estado, _ = clasificar_puesto("Social Media Program")
        self.assertEqual(carrera, "Marketing")
        self.assertEqual(estado, "Confirmado en la reunión")

    def test_creador_contenido_es_marketing(self):
        carrera, _, _, estado, _ = clasificar_puesto("Creador de contenido")
        self.assertEqual(carrera, "Marketing")
        self.assertEqual(estado, "Confirmado en la reunión")

    def test_puesto_desconocido_queda_por_confirmar(self):
        carrera, _, _, _, nota = clasificar_puesto("Astronauta")
        self.assertIsNone(carrera)
        self.assertIn(POR_CONFIRMAR, nota)


class TestFormatoUnico(unittest.TestCase):
    def test_campos_que_faltan_quedan_por_confirmar(self):
        f = a_formato_unico(
            {"puesto": "Cocinero", "sponsor": "CETUSA"},
            fuente="portal", archivo_origen="scraper.json", correlativo=3)
        self.assertEqual(f["id_oferta"], "OF-2026-0003")
        self.assertEqual(f["estado"], "nueva")
        self.assertEqual(f["carrera"], "Gastronomía")
        self.assertEqual(f["salario / pago"], POR_CONFIRMAR)
        self.assertEqual(f["fecha_inicio"], POR_CONFIRMAR)

    def test_nada_se_inventa(self):
        f = a_formato_unico(
            {"puesto": "Bartender"}, fuente="correo",
            archivo_origen="correo.xlsx", correlativo=1)
        self.assertEqual(f["sponsor"], POR_CONFIRMAR)
        self.assertEqual(f["ubicacion"], POR_CONFIRMAR)


class TestDuplicados(unittest.TestCase):
    def test_misma_oferta_por_portal_y_correo(self):
        portal = a_formato_unico(
            {"puesto": "Recepcionista de hotel", "sponsor": "CHI",
             "ubicacion": "Orlando, Florida", "fecha_inicio": "2027-06"},
            fuente="portal", archivo_origen="scraper.json", correlativo=1)
        correo = a_formato_unico(
            {"puesto": "Recepcionista de hotel", "sponsor": "CHI",
             "ubicacion": "Orlando, Florida", "fecha_inicio": "junio 2027"},
            fuente="correo", archivo_origen="correo.xlsx", correlativo=2)
        self.assertEqual(clave_duplicado(portal), clave_duplicado(correo))

    def test_otro_sponsor_no_es_duplicado(self):
        a = {"sponsor": "CHI", "posicion_canonica": "recepcionista",
             "ubicacion": "Orlando, Florida", "fecha_inicio": "2027-06"}
        b = dict(a, sponsor="CETUSA")
        self.assertNotEqual(clave_duplicado(a), clave_duplicado(b))


class TestMatch(unittest.TestCase):
    def test_ejemplo_ilustrativo_del_borrador_77_5(self):
        """Ejemplo del borrador 21 nov: recepcionista de hotel, 77,5%."""
        oferta = a_formato_unico(
            {"puesto": "Recepcionista de hotel", "sponsor": "CHI",
             "ubicacion": "Orlando, Florida", "programa": "Internship USA",
             "ingles": "intermedio", "texto": "Hotel receptionist"},
            fuente="portal", archivo_origen="scraper.json", correlativo=1)
        oferta["experiencia_min_anios"] = 2
        oferta["requiere_estudios"] = True
        perfil = {"carrera": "Turismo", "experiencia_anios": 1,
                  "estudios_afines": True, "ingles": "",
                  "preferencias": ["hotelería"]}
        r = match(oferta, perfil)
        self.assertEqual(r["porcentaje"], 77.5)
        self.assertEqual(r["puntajes"]["carrera"], 1.0)
        self.assertEqual(r["puntajes"]["experiencia"], 0.5)
        self.assertEqual(r["puntajes"]["educacion"], 1.0)
        self.assertEqual(r["puntajes"]["ingles"], 0.0)
        self.assertEqual(r["puntajes"]["preferencias"], 1.0)
        self.assertIn("inglés", r["que_falta"])

    def test_match_perfecto_da_100(self):
        oferta = {"carrera": "Gastronomía", "posicion": "cocinero/a",
                  "ubicacion": "Miami, Florida",
                  "ingles requerido": "básico", "requiere_estudios": False}
        perfil = {"carrera": "Gastronomía", "experiencia_anios": 5,
                  "estudios_afines": True, "ingles": "intermedio",
                  "preferencias": ["gastronomía"]}
        self.assertEqual(match(oferta, perfil)["porcentaje"], 100.0)

    def test_honores_no_resta(self):
        """Los honores no entran como factor negativo: el match no baja por tenerlos."""
        oferta = {"carrera": "Hotelería", "posicion": "recepcionista",
                  "ubicacion": "Miami, Florida",
                  "ingles requerido": "básico", "requiere_estudios": False}
        base = {"carrera": "Hotelería", "experiencia_anios": 2,
                "estudios_afines": False, "ingles": "básico",
                "preferencias": ["hotelería"]}
        con_honores = dict(base, honores=["Mejor estudiante"])
        self.assertEqual(match(oferta, base)["porcentaje"],
                         match(oferta, con_honores)["porcentaje"])


class TestCorreo(unittest.TestCase):
    def test_oferta_se_detecta(self):
        self.assertEqual(
            es_oferta_trabajo("New vacancy: hotel receptionist, sponsor CHI, Orlando"),
            "oferta")

    def test_gracias_no_es_oferta(self):
        self.assertEqual(
            es_oferta_trabajo("Gracias por su mensaje, le responderemos pronto"),
            "no es oferta")

    def test_dudoso_queda_en_revisar(self):
        self.assertEqual(es_oferta_trabajo("Hola, te escribo por lo de ayer"), "revisar")


class TestScraper(unittest.TestCase):
    def test_rotativo_queda_por_confirmar(self):
        carrera, _, _, _, nota = clasificar_puesto(
            "Hospitality Rotational",
            "Program with rotations in Front Office, F&B, Culinary")
        self.assertIsNone(carrera)
        self.assertIn("rotativo", nota)

    def test_front_office_es_recepcionista(self):
        _, _, pos, _, _ = clasificar_puesto("Front Office Program - 11099")
        self.assertEqual(pos, "recepcionista")

    def test_culinary_es_cocinero(self):
        carrera, esp, pos, _, _ = clasificar_puesto("Culinary Program")
        self.assertEqual((carrera, esp, pos),
                         ("Gastronomía", "Cocina", "cocinero/a"))

    def test_cocina_y_sala_es_cocinero(self):
        _, _, pos, _, _ = clasificar_puesto("Cocina y sala")
        self.assertEqual(pos, "cocinero/a")

    def test_nivel_ingles_en_ingles(self):
        oferta = {"ingles requerido": "Advanced"}
        self.assertEqual(match(
            dict(oferta, carrera="Hotelería", posicion="recepcionista",
                 ubicacion="Miami", experiencia_min_anios=None,
                 requiere_estudios=False),
            {"carrera": "Hotelería", "experiencia_anios": 0,
             "estudios_afines": False, "ingles": "intermedio",
             "preferencias": []})["puntajes"]["ingles"], 0.5)

    def test_clave_usa_la_posicion_canonica(self):
        f = {"sponsor": "CHI", "posicion": "recepcionista",
             "puesto": "Recepción", "ubicacion": "Orlando, FL, USA",
             "fecha_inicio": "2027-01-01"}
        self.assertTrue(clave_duplicado(f).startswith("chi|recepcionista|"))

    def test_mapear_intern_espana(self):
        from clasificador_ofertas import mapear_oferta_scraper
        cruda = mapear_oferta_scraper(
            {"title": "Cocina y sala", "company": "Cobo Estratos",
             "location": "Burgos", "state": None, "country": "Spain",
             "program_type": "Intern", "start_date": "Finales de 2026",
             "earliest_start_date": "2026-05-13", "english_level": "Excellent",
             "category": "Hospitality", "description": "", "full_description": "",
             "training_plan": None, "requirements": None,
             "candidate_profile": None, "listing_expires": None,
             "first_seen": "2026-07-08T04:08:14.234021+00:00",
             "compensation_text": "300 €/mes", "hours_per_week": None,
             "end_date": None, "duration_text": None})
        self.assertEqual(cruda["programa"], "Internship España")
        self.assertIn("Cubre cocina y sala", cruda["notas"])


if __name__ == "__main__":
    unittest.main()

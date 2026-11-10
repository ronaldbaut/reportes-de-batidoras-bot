"""Pruebas puras del cálculo de tiempo por batida y de los resúmenes del cierre."""
import os

os.environ.setdefault("DISCORD_TOKEN", "test")
os.environ.setdefault("XAI_API_KEY", "test")

import main


def test_parsear_horas():
    assert main.parsear_hora_minutos("7") == 7 * 60
    assert main.parsear_hora_minutos("7:00") == 7 * 60
    assert main.parsear_hora_minutos("7am") == 7 * 60
    assert main.parsear_hora_minutos("7:00 am") == 7 * 60
    assert main.parsear_hora_minutos("7:00 a.m.") == 7 * 60
    assert main.parsear_hora_minutos("12:40 pm") == 12 * 60 + 40
    assert main.parsear_hora_minutos("12:40pm") == 12 * 60 + 40
    assert main.parsear_hora_minutos("1:15 pm") == 13 * 60 + 15
    assert main.parsear_hora_minutos("1:15pm") == 13 * 60 + 15
    assert main.parsear_hora_minutos("1:15 p.m.") == 13 * 60 + 15
    assert main.parsear_hora_minutos("a la una") == 60
    assert main.parsear_hora_minutos("a las siete") == 7 * 60
    assert main.parsear_hora_minutos("mediodía") == 12 * 60
    assert main.parsear_hora_minutos("el clima esta bonito") is None


def test_sin_meridiano_antes_de_llegada_es_pm():
    llegada = main.parsear_hora_minutos("7:00 am")
    assert main.parsear_hora_minutos("1:15", llegada_min=llegada) == 13 * 60 + 15
    assert main.parsear_hora_minutos("6", llegada_min=llegada) == 18 * 60
    # 12:40 no es anterior a las 7:00, se queda al mediodía.
    assert main.parsear_hora_minutos("12:40", llegada_min=llegada) == 12 * 60 + 40
    # Con am/pm explícito no se mueve.
    assert main.parsear_hora_minutos("6:00 am", llegada_min=llegada) == 6 * 60


def test_calculo_ejemplo_meta():
    calc = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 12)
    assert calc["ok"] is True
    assert calc["total_min"] == 5 * 60 + 40
    assert calc["cumplio"] is True
    texto = main.formatear_calculo_batidas(calc)
    esperado = (
        "📊 **Cálculo de tiempo por batida**\n"
        "• Llegada: 7:00 am\n"
        "• Culminación: 12:40 pm\n"
        "• Tiempo total: 5 h 40 min\n"
        "• Batidas: 12\n"
        "• Promedio: **28,3 min por batida**\n"
        "• Meta (CMI): **30 min por batida o menos**\n"
        "✅ **Cumplieron la meta** (1,7 min por debajo)."
    )
    assert texto == esperado
    assert main.META_MIN_POR_BATIDA == 30


def test_misma_cuenta_sin_am_pm_en_culminacion():
    calc = main.calcular_tiempo_por_batida("7", "12:40", 12)
    assert main.formatear_calculo_batidas(calc) == main.formatear_calculo_batidas(
        main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 12)
    )


def test_no_cumplen():
    calc = main.calcular_tiempo_por_batida("7:00 am", "1:00 pm", 10)
    assert calc["ok"] is True
    assert calc["cumplio"] is False
    texto = main.formatear_calculo_batidas(calc)
    assert "Tiempo total: 6 h" in texto
    assert "36,0 min por batida" in texto
    assert "❌ **No cumplieron la meta** (6,0 min por encima)." in texto


def test_no_se_puede_calcular():
    antes = main.calcular_tiempo_por_batida("7:00 pm", "8:00 am", 5)
    assert antes["ok"] is False
    assert "no es posterior" in antes["mensaje"]
    invalida = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 0)
    assert invalida["ok"] is False
    assert "no es válido" in invalida["mensaje"]
    ambas = main.calcular_tiempo_por_batida("7:00 am", "7:00 am", "muchas")
    assert ambas["ok"] is False
    assert "no es posterior" in ambas["mensaje"]
    assert "no es válido" in ambas["mensaje"]
    assert "No pude calcular" in main.formatear_calculo_batidas(ambas)


def test_batidas_en_palabras():
    assert main.extraer_entero_positivo("hicimos doce") == 12
    assert main.extraer_entero_positivo("Margaret pasó 12") == 12
    assert main.extraer_entero_positivo("cero") is None
    calc = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", "doce")
    assert calc["batidas"] == 12


def test_agua_sal():
    si = main.parsear_agua_sal("sí, la 2 una vez y la 4 dos veces")
    assert si["estado"] == "ok"
    assert si["cambios"] == [
        {"batidora": 2, "veces": 1},
        {"batidora": 4, "veces": 2},
    ]
    assert main.parsear_agua_sal("no") == {"estado": "ok", "cambios": []}
    assert main.parsear_agua_sal("ninguna")["cambios"] == []
    assert main.parsear_agua_sal("sí")["estado"] == "falta_numeros"
    assert main.parsear_agua_sal("sep, la dos")["cambios"] == [
        {"batidora": 2, "veces": 1}
    ]
    assert main.parsear_agua_sal("2 veces la 4")["cambios"] == [
        {"batidora": 4, "veces": 2}
    ]
    assert (
        main.formatear_resumen_agua_sal([])
        == "💧 Cambios de agua sal: ninguno"
    )
    assert (
        main.formatear_resumen_agua_sal(si["cambios"])
        == "💧 Cambios de agua sal: batidora 2 (1 vez), batidora 4 (2 veces)"
    )


def test_limpieza():
    limpio = main.evaluar_limpieza("sí")
    assert limpio["estado"] == "ok" and limpio["limpio"] is True
    assert main.formatear_resumen_limpieza(True, None) == "🧽 Limpieza: ✅ todo limpio"

    pedido = main.evaluar_limpieza("no")
    assert pedido["estado"] == "pedir_detalle"

    segundo = main.evaluar_limpieza("no", ya_pedi_detalle=True)
    assert segundo["estado"] == "ok" and segundo["limpio"] is False
    assert "no se especificó" in main.formatear_resumen_limpieza(False, segundo["pendiente"])

    detalle = main.evaluar_limpieza("no, los mesones y el piso")
    assert detalle["limpio"] is False
    assert "mesones" in detalle["pendiente"]
    assert main.formatear_resumen_limpieza(False, detalle["pendiente"]).startswith(
        "🧽 Limpieza: ❌ quedó pendiente:"
    )

    corregido = main.evaluar_limpieza("no\nsí, todo limpio", ya_pedi_detalle=True)
    assert corregido["estado"] == "ok" and corregido["limpio"] is True
    # Lo que ya está en el buffer no se vuelve a pedir: "sí" + números.
    junto = main.parsear_agua_sal("sí\nla 2 una vez")
    assert junto["estado"] == "ok"
    assert junto["cambios"][0]["batidora"] == 2


def test_orden_de_las_preguntas_nuevas():
    assert main.FASES_CIERRE_APAGADO == (
        "agua_sal",
        "limpieza",
        "hora_llegada",
        "batidas",
        "hora_culminacion",
        "batidoras_dia",
        "batidoras_parcial",
    )
    assert "todo el día" in main.PREGUNTAS_CIERRE["batidoras_dia"].lower()
    assert "parte del día" in main.PREGUNTAS_CIERRE["batidoras_parcial"].lower()
    assert "2,5" in main.PREGUNTAS_CIERRE["batidoras_parcial"]
    assert "pausa" not in main.FASES_CIERRE_APAGADO
    assert "pausa" not in main.PREGUNTAS_CIERRE


def test_numero_de_batidoras():
    assert main.parsear_batidoras_dia("4") == 4
    assert main.parsear_batidoras_dia("con 3") == 3
    assert main.parsear_batidoras_dia("tres") == 3
    assert main.parsear_batidoras_dia("trabajamos con cuatro") == 4
    assert main.parsear_batidoras_dia("0") == 0
    assert main.parsear_batidoras_dia("no") == 0
    assert main.parsear_batidoras_dia("ninguna") == 0
    assert main.parsear_batidoras_dia("3 y 4") is None
    assert main.parsear_batidoras_dia("3,5") is None
    assert main.parsear_batidoras_dia("3.5") is None
    assert main.parsear_batidoras_dia("6") is None

    assert main.parsear_horas_parciales("0") == []
    assert main.parsear_horas_parciales("no") == []
    assert main.parsear_horas_parciales("ninguna") == []
    assert main.parsear_horas_parciales("4") == [4]
    assert main.parsear_horas_parciales("4 y 2,5") == [4, 2.5]
    assert main.parsear_horas_parciales("4 y 2.5") == [4, 2.5]
    assert main.parsear_horas_parciales("4:30") == [4.5]
    assert main.parsear_horas_parciales("4:30 y 2,5") == [4.5, 2.5]
    assert main.parsear_horas_parciales("cuatro") == [4]
    assert main.parsear_horas_parciales("sí") is None
    assert main.parsear_horas_parciales("4:60") is None
    assert main.parsear_horas_parciales("30") is None

    state = {"fase": "batidoras_dia", "answers": {}}
    ambigua = main._combinar_decision_cierre(state, "3 y 4", {})
    assert ambigua["respuesta_valida"] is False
    clara = main._combinar_decision_cierre(state, "con tres", {})
    assert clara["respuesta_valida"] is True
    assert clara["_batidoras_dia"] == 3
    cero_dia = main._combinar_decision_cierre(state, "ninguna", {})
    assert cero_dia["_batidoras_dia"] == 0
    seguido = main._combinar_decision_cierre(state, "3 y 4\n3", {})
    assert seguido["respuesta_valida"] is True
    assert seguido["_batidoras_dia"] == 3

    state_parc = {"fase": "batidoras_parcial", "answers": {"batidoras_dia": 3}}
    parte = main._combinar_decision_cierre(state_parc, "4:30", {})
    assert parte["respuesta_valida"] is True
    assert parte["_horas_parciales"] == [4.5]
    ninguna = main._combinar_decision_cierre(state_parc, "no", {})
    assert ninguna["_horas_parciales"] == []
    de_mas = main._combinar_decision_cierre(
        {"fase": "batidoras_parcial", "answers": {"batidoras_dia": 4}},
        "4 y 2,5",
        {},
    )
    assert de_mas["respuesta_valida"] is False
    assert str(main.NUM_BATIDORAS) in de_mas["mensaje"]
    vacio = main._combinar_decision_cierre(
        {"fase": "batidoras_parcial", "answers": {"batidoras_dia": 0}},
        "no",
        {},
    )
    assert vacio["respuesta_valida"] is False


def test_la_meta_depende_de_las_batidoras_efectivas():
    # Sin datos de batidoras: tiempo de reloj / batidas y meta de 30.
    base = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 12)
    assert base["total_min"] == 340
    assert base["promedio"] == 340 / 12
    assert base["meta"] == 30
    assert "num_batidoras" not in base
    assert "Pausa" not in main.formatear_calculo_batidas(base)
    assert "Meta (CMI)" in main.formatear_calculo_batidas(base)

    assert main.meta_para_batidoras(4) == 30
    assert main.meta_para_batidoras(3) == 40
    assert main.meta_para_batidoras(2) == 60

    cuatro = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 12, num_batidoras=4)
    assert cuatro["total_min"] == 340
    assert cuatro["num_batidoras"] == 4
    assert cuatro["promedio"] == 340 / 12
    assert cuatro["meta"] == 30
    assert cuatro["cumplio"] is True
    texto_cuatro = main.formatear_calculo_batidas(cuatro)
    assert "Tiempo total: 5 h 40 min" in texto_cuatro
    assert "Pausa" not in texto_cuatro
    assert "Batidoras: 4 todo el día (equivale a 4,0)" in texto_cuatro
    assert "28,3 min por batida" in texto_cuatro
    assert "Meta: **30,0 min**" in texto_cuatro
    assert cuatro["n_ef"] == 4

    tres = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 12, num_batidoras=3)
    assert tres["promedio"] == 340 / 12
    assert tres["meta"] == 40
    assert tres["cumplio"] is True
    texto_tres = main.formatear_calculo_batidas(tres)
    assert "Batidoras: 3 todo el día (equivale a 3,0)" in texto_tres
    assert "28,3 min por batida" in texto_tres
    assert "Meta: **40,0 min**" in texto_tres
    assert tres["n_ef"] == 3

    # 36 min queda por encima de 30 y dentro de la meta de 40.
    justo = main.calcular_tiempo_por_batida("7:00 am", "1:00 pm", 10, num_batidoras=3)
    assert justo["promedio"] == 36
    assert justo["meta"] == 40
    assert justo["cumplio"] is True
    assert "4,0 min por debajo" in main.formatear_calculo_batidas(justo)
    con_cuatro = main.calcular_tiempo_por_batida("7:00 am", "1:00 pm", 10, num_batidoras=4)
    assert con_cuatro["cumplio"] is False
    assert con_cuatro["meta"] == 30

    dos = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 12, num_batidoras=2)
    assert dos["promedio"] == 340 / 12
    assert dos["meta"] == 60
    assert dos["n_ef"] == 2
    assert "Meta: **60,0 min**" in main.formatear_calculo_batidas(dos)

    ninguna = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=0, horas_parciales=[]
    )
    assert ninguna["ok"] is False
    assert "ninguna batidora" in ninguna["mensaje"]
    de_mas = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=5, horas_parciales=[4]
    )
    assert de_mas["ok"] is False
    assert "más de 5" in de_mas["mensaje"]


def test_ejemplo_batidoras_parciales():
    """7:00–12:40, 12 batidas. El día efectivo es el reloj completo: 5 h 40 min."""
    dia_h = 340 / 60

    def calc(dia, horas):
        return main.calcular_tiempo_por_batida(
            "7:00 am",
            "12:40 pm",
            12,
            num_batidoras=dia,
            horas_parciales=horas,
        )

    cuatro = calc(4, [])
    assert cuatro["promedio"] == 340 / 12
    assert cuatro["n_ef"] == 4
    assert cuatro["meta"] == 30
    assert "equivale a 4,0" in main.formatear_calculo_batidas(cuatro)

    tres = calc(3, [])
    assert tres["n_ef"] == 3
    assert tres["promedio"] == cuatro["promedio"]
    assert tres["meta"] == 40

    parcial = calc(3, [4])
    assert abs(parcial["n_ef"] - (3 + 4 / dia_h)) < 1e-9
    assert main._fmt_un_decimal(parcial["n_ef"]) == "3,7"
    assert parcial["meta"] == 32.4
    assert parcial["promedio"] == 340 / 12
    texto = main.formatear_calculo_batidas(parcial)
    assert "Batidoras: 3 todo el día + 1 por 4 h (equivale a 3,7)" in texto
    assert "Meta: **32,4 min**" in texto
    assert "28,3 min por batida" in texto

    solo = calc(0, [4])
    assert abs(solo["n_ef"] - (4 / dia_h)) < 1e-9
    assert main._fmt_un_decimal(solo["n_ef"]) == "0,7"
    assert solo["meta"] == 170
    assert solo["promedio"] == 340 / 12
    texto_solo = main.formatear_calculo_batidas(solo)
    assert "Batidoras: 0 todo el día + 1 por 4 h (equivale a 0,7)" in texto_solo
    assert "Meta: **170,0 min**" in texto_solo

    # 4:30 son 4,5 h. Una de 8 h se recorta al día neto y cuenta como 1.
    media = calc(0, ["4:30"])
    assert abs(media["n_ef"] - (4.5 / dia_h)) < 1e-9
    assert "1 por 4,5 h" in main.formatear_calculo_batidas(media)
    capada = calc(0, [8])
    una = calc(1, [])
    assert abs(capada["n_ef"] - 1) < 1e-9
    assert capada["meta"] == una["meta"] == 120


def test_combinar_no_repite_si_ya_hay_hora():
    state = {"fase": "hora_llegada", "answers": {}}
    decision = main._combinar_decision_cierre(
        state,
        "llegamos tipo 7",
        {"respuesta_valida": False, "mensaje": "repite la hora"},
    )
    assert decision["respuesta_valida"] is True
    assert decision["_minutos"] == 7 * 60

    state_fin = {
        "fase": "hora_culminacion",
        "answers": {"hora_llegada": "7:00 am"},
    }
    decision_fin = main._combinar_decision_cierre(
        state_fin,
        "1:15",
        {"respuesta_valida": False, "mensaje": "falta am pm"},
    )
    assert decision_fin["respuesta_valida"] is True
    assert decision_fin["_minutos"] == 13 * 60 + 15


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"{len(tests)} pruebas ok")

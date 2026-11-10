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
        "num_batidoras",
        "pausa",
    )
    assert "cuántas batidoras" in main.PREGUNTAS_CIERRE["num_batidoras"].lower()
    assert "0" in main.PREGUNTAS_CIERRE["pausa"]
    assert "30,5" in main.PREGUNTAS_CIERRE["pausa"]


def test_minutos_de_pausa_con_coma_o_punto():
    assert main.parsear_minutos_pausa("0") == 0
    assert main.parsear_minutos_pausa("no") == 0
    assert main.parsear_minutos_pausa("sin pausa") == 0
    assert main.parsear_minutos_pausa("no hubo pausa") == 0
    assert main.parsear_minutos_pausa("40") == 40
    assert main.parsear_minutos_pausa("40 minutos") == 40
    assert main.parsear_minutos_pausa("30,5") == 30.5
    assert main.parsear_minutos_pausa("30.5 minutos") == 30.5
    assert main.parsear_minutos_pausa("1,5 horas") == 90
    assert main.parsear_minutos_pausa("1 hora") == 60
    assert main.parsear_minutos_pausa("media hora") == 30
    assert main.parsear_minutos_pausa("hora y media") == 90
    assert main.parsear_minutos_pausa("sí, 20") == 20
    assert main.parsear_minutos_pausa("sí") is None
    assert main.parsear_minutos_pausa("15 y 20") is None
    assert main.parsear_minutos_pausa("1 hora 30 min") is None
    assert main.parsear_minutos_pausa("9 horas") is None


def test_numero_de_batidoras():
    assert main.parsear_num_batidoras("4") == 4
    assert main.parsear_num_batidoras("con 3") == 3
    assert main.parsear_num_batidoras("tres") == 3
    assert main.parsear_num_batidoras("trabajamos con cuatro") == 4
    assert main.parsear_num_batidoras("3 y 4") is None
    assert main.parsear_num_batidoras("3,5") is None
    assert main.parsear_num_batidoras("3.5") is None
    assert main.parsear_num_batidoras("0") is None
    assert main.parsear_num_batidoras("6") is None
    assert main.parsear_num_batidoras("no") is None

    state = {"fase": "num_batidoras", "answers": {}}
    ambigua = main._combinar_decision_cierre(state, "3 y 4", {})
    assert ambigua["respuesta_valida"] is False
    clara = main._combinar_decision_cierre(state, "con tres", {})
    assert clara["respuesta_valida"] is True
    assert clara["_batidoras"] == 3

    state_p = {"fase": "pausa", "answers": {}}
    cero = main._combinar_decision_cierre(state_p, "sin pausa", {})
    assert cero["respuesta_valida"] is True
    assert cero["_pausa_min"] == 0
    media = main._combinar_decision_cierre(state_p, "30,5 minutos", {})
    assert media["_pausa_min"] == 30.5
    # Si el acumulado queda ambiguo, vale el último mensaje claro.
    seguido = main._combinar_decision_cierre(state, "3 y 4\n3", {})
    assert seguido["respuesta_valida"] is True
    assert seguido["_batidoras"] == 3
    seguido_p = main._combinar_decision_cierre(state_p, "15 y 20\n15,5", {})
    assert seguido_p["respuesta_valida"] is True
    assert seguido_p["_pausa_min"] == 15.5


def test_pausa_resta_tiempo_y_la_meta_depende_de_las_batidoras():
    # Sin datos nuevos: tiempo / batidas y meta de 30, como antes.
    base = main.calcular_tiempo_por_batida("7:00 am", "12:40 pm", 12)
    assert base["total_min"] == 340
    assert base["promedio"] == 340 / 12
    assert base["meta"] == 30
    assert "pausa_min" not in base
    assert "num_batidoras" not in base
    assert "Meta (CMI)" in main.formatear_calculo_batidas(base)

    assert main.meta_para_batidoras(4) == 30
    assert main.meta_para_batidoras(3) == 40
    assert main.meta_para_batidoras(2) == 60

    cuatro = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=4, pausa_min=0
    )
    assert cuatro["bruto_min"] == 340
    assert cuatro["pausa_min"] == 0
    assert cuatro["total_min"] == 340
    assert cuatro["num_batidoras"] == 4
    assert cuatro["promedio"] == 340 / 12
    assert cuatro["meta"] == 30
    assert cuatro["cumplio"] is True
    texto_cuatro = main.formatear_calculo_batidas(cuatro)
    assert "Tiempo bruto: 5 h 40 min" in texto_cuatro
    assert "Pausa descontada: 0 min" in texto_cuatro
    assert "Tiempo neto: 5 h 40 min" in texto_cuatro
    assert "Batidoras: 4" in texto_cuatro
    assert "28,3 min por batida" in texto_cuatro
    assert "Meta con 4 batidoras: **30 min**" in texto_cuatro
    assert "ajuste" not in texto_cuatro

    con_pausa = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=4, pausa_min=40
    )
    assert con_pausa["total_min"] == 300
    assert con_pausa["promedio"] == 300 / 12
    assert con_pausa["meta"] == 30
    assert con_pausa["cumplio"] is True
    texto_pausa = main.formatear_calculo_batidas(con_pausa)
    assert "Pausa descontada: 40 min" in texto_pausa
    assert "Tiempo neto: 5 h" in texto_pausa
    assert "25,0 min por batida" in texto_pausa
    assert "Meta con 4 batidoras: **30 min**" in texto_pausa

    tres = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=3, pausa_min=0
    )
    assert tres["promedio"] == 340 / 12
    assert tres["meta"] == 40
    assert tres["cumplio"] is True
    texto_tres = main.formatear_calculo_batidas(tres)
    assert "Batidoras: 3" in texto_tres
    assert "28,3 min por batida" in texto_tres
    assert "Meta con 3 batidoras: **40 min**" in texto_tres
    assert "ajuste" not in texto_tres

    tres_pausa = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras="3", pausa_min="40"
    )
    assert tres_pausa["num_batidoras"] == 3
    assert tres_pausa["promedio"] == 300 / 12
    assert tres_pausa["meta"] == 40
    assert tres_pausa["cumplio"] is True
    texto_tres_pausa = main.formatear_calculo_batidas(tres_pausa)
    assert "25,0 min por batida" in texto_tres_pausa
    assert "Meta con 3 batidoras: **40 min**" in texto_tres_pausa

    # 36 min queda por encima de 30 y dentro de la meta de 40.
    justo = main.calcular_tiempo_por_batida(
        "7:00 am", "1:00 pm", 10, num_batidoras=3, pausa_min=0
    )
    assert justo["promedio"] == 36
    assert justo["meta"] == 40
    assert justo["cumplio"] is True
    assert "4,0 min por debajo" in main.formatear_calculo_batidas(justo)
    con_cuatro = main.calcular_tiempo_por_batida(
        "7:00 am", "1:00 pm", 10, num_batidoras=4, pausa_min=0
    )
    assert con_cuatro["cumplio"] is False
    assert con_cuatro["meta"] == 30

    dos = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=2, pausa_min=0
    )
    assert dos["promedio"] == 340 / 12
    assert dos["meta"] == 60
    assert "Meta con 2 batidoras: **60 min**" in main.formatear_calculo_batidas(dos)

    decimal = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=4, pausa_min="30,5"
    )
    assert decimal["pausa_min"] == 30.5
    assert decimal["total_min"] == 309.5
    assert abs(decimal["promedio"] - (309.5 / 12)) < 1e-9
    assert decimal["meta"] == 30
    assert "Pausa descontada: 30,5 min" in main.formatear_calculo_batidas(decimal)

    cubre = main.calcular_tiempo_por_batida(
        "7:00 am", "12:40 pm", 12, num_batidoras=4, pausa_min=340
    )
    assert cubre["ok"] is False
    assert "cubre todo el tiempo" in cubre["mensaje"]
    assert "5 h 40 min" in main.formatear_calculo_batidas(cubre)


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

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

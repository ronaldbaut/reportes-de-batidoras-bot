"""Recorrido de las batidoras 4 y 5 en inicio y cierre.

La batidora 4 se ponía rara: el modelo devolvía fuera de servicio
(o la palabra "false") y el bot se saltaba el video.
"""
import asyncio
import os

os.environ.setdefault("DISCORD_TOKEN", "test")
os.environ.setdefault("XAI_API_KEY", "test")

import main

CHECKLIST_OK = (
    "dientes completos, piñón ajustado y engrasado, cuchilla bien, "
    "agua sal a nivel, la correa no está floja, encendido 7:00 apagado 12:00"
)


class _Canal:
    def __init__(self):
        self.id = 404
        self.mensajes = []

    async def send(self, texto, **kwargs):
        self.mensajes.append(texto)
        self.ultimo_view = kwargs.get("view")


class _Usuario:
    id = 7
    mention = "<@7>"
    display_name = "Karina"


class _Adjunto:
    def __init__(self, nombre):
        self.filename = nombre
        self.size = 1000 + len(nombre)
        self.content_type = "video/mp4"


class _Msg:
    def __init__(self, canal, contenido, video=None):
        self.channel = canal
        self.content = contenido
        self.author = _Usuario()
        self.attachments = [] if video is None else [_Adjunto(video)]

    async def add_reaction(self, emoji):
        return None


def _grok(fuera, valida=True):
    async def _consultar(state, respuesta, tiene_media):
        return {
            "respuesta_valida": valida,
            "es_fuera_de_servicio": fuera,
            "mensaje": "rechazo del modelo" if not valida else None,
        }

    return _consultar


async def _ir_hasta(tipo, batidora, grok_fuera=False):
    """Deja el reporte en el checklist de `batidora`, con las anteriores ya hechas."""
    main.consultar_grok = _grok(grok_fuera)
    main.conversation_state.clear()
    canal = _Canal()
    await main._iniciar(canal, _Usuario(), tipo)
    if tipo == "encendido_batidoras":
        await main.manejar_respuesta(_Msg(canal, "7:00 am"))
    while True:
        state = main.conversation_state[str(canal.id)]
        if state["fase"] == "checklist" and state["batidora"] == batidora:
            return canal
        if state["fase"] == "funcionamiento" and state["batidora"] == batidora:
            return canal
        if state["fase"] == "trabajo_hoy":
            await main.manejar_respuesta(_Msg(canal, "sí"))
        elif state["fase"] == "video":
            await main.manejar_respuesta(
                _Msg(canal, "", video=f"pinon-{state['batidora']}.mp4")
            )
        else:
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))


def test_false_en_texto_no_es_verdadero():
    assert main._como_bool(False) is False
    assert main._como_bool("false") is False
    assert main._como_bool("no") is False
    assert main._como_bool(True) is True
    assert main._como_bool("true") is True
    assert main._texto_fuera_de_servicio(CHECKLIST_OK) is False
    assert main._texto_fuera_de_servicio("la correa no está floja") is False
    assert main._texto_fuera_de_servicio("no se usó grasa de más") is False
    assert main._texto_fuera_de_servicio("no funcionó hoy") is True
    assert main._texto_fuera_de_servicio("está en reparación") is True
    assert main._texto_fuera_de_servicio("la dejamos apagada") is True
    assert main._texto_fuera_de_servicio("apagado 12:00") is False
    for frase in (
        "no está trabajando",
        "no trabajó",
        "no se usó",
        "está en reparación",
        "dañada",
        "parada",
        "fuera de servicio",
        "no funciona",
        "sin uso hoy",
        "no",
    ):
        assert main._texto_fuera_de_servicio(frase) is True, frase
    assert main._texto_fuera_de_servicio("no está dañada") is False
    assert main._texto_fuera_de_servicio("no está parada") is False
    assert main._texto_fuera_de_servicio("el piñón no trabaja bien") is False


def test_la_cuarta_no_se_salta_si_el_modelo_la_marca_fuera():
    """Inicio y cierre: un checklist normal de la 4 pide video y sigue a la 5."""

    async def caso(tipo):
        for marca in (True, "false"):
            canal = await _ir_hasta(tipo, 4)
            main.consultar_grok = _grok(marca)
            antes = len(canal.mensajes)
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
            nuevos = canal.mensajes[antes:]
            assert not any("trabajó hoy" in m for m in nuevos), nuevos
            assert any("video del piñón de la batidora 4" in m for m in nuevos), nuevos
            assert not any("fuera de servicio" in m for m in nuevos), nuevos
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == 4 and state["fase"] == "video"
            assert state["answers"][f"{tipo}_bat4_trabajo"] == "si"
            await main.manejar_respuesta(_Msg(canal, "sí"))
            assert any("video del piñón de la batidora 4" in m for m in canal.mensajes)
            state = main.conversation_state[str(canal.id)]
            assert state["fase"] == "video"
            await main.manejar_respuesta(_Msg(canal, "", video="pinon-4.mp4"))
            assert any(m.startswith("**Batidora 5**") for m in canal.mensajes), canal.mensajes[-1]
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == 5 and state["fase"] == "checklist"

    asyncio.run(caso("encendido_batidoras"))
    asyncio.run(caso("apagado_batidoras"))


def test_si_no_trabaja_no_pide_video_y_guarda_el_motivo():
    """En el video, «no trabaja» no sigue pidiendo el video."""

    async def correr():
        frases = (
            "no está trabajando",
            "está en reparación",
            "dañada",
            "no se usó",
            "sin uso hoy",
            "parada",
            "no",
        )
        for i, frase in enumerate(frases):
            bat = 4 if i % 2 == 0 else 2
            canal = await _ir_hasta("apagado_batidoras", bat)
            main.consultar_grok = _grok(True, valida=True)
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
            state = main.conversation_state[str(canal.id)]
            assert state["fase"] == "video"
            antes = len(canal.mensajes)
            await main.manejar_respuesta(_Msg(canal, frase))
            nuevos = canal.mensajes[antes:]
            assert not any("video del piñón" in m for m in nuevos), (frase, nuevos)
            assert any("no en uso" in m and frase in m for m in nuevos), (frase, nuevos)
            guardado = state["answers"][f"apagado_batidoras_bat{bat}_video"]
            assert "fuera de servicio" in guardado and frase in guardado
            assert state["batidora"] == bat + 1
            assert state["fase"] == "checklist"

    asyncio.run(correr())


def test_la_cuarta_fuera_de_servicio_si_pasa_a_la_quinta():
    async def caso(tipo):
        canal = await _ir_hasta(tipo, 4)
        main.consultar_grok = _grok(True)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        await main.manejar_respuesta(_Msg(canal, "no funcionó hoy"))
        assert any("Batidora 4 marcada como **no en uso" in m for m in canal.mensajes)
        assert any(m.startswith("**Batidora 5**") for m in canal.mensajes)
        state = main.conversation_state[str(canal.id)]
        assert state["batidora"] == 5
        assert "fuera de servicio" in state["answers"][f"{tipo}_bat4_video"]

    asyncio.run(caso("encendido_batidoras"))
    asyncio.run(caso("apagado_batidoras"))


def test_la_quinta_cierra_sin_pedir_una_sexta():
    async def encendido():
        canal = await _ir_hasta("encendido_batidoras", 5)
        main.consultar_grok = _grok(True)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        await main.manejar_respuesta(_Msg(canal, "sí"))
        await main.manejar_respuesta(_Msg(canal, "", video="pinon-5.mp4"))
        assert any("Encendido de Batidoras completado" in m for m in canal.mensajes)
        assert not any("Batidora 6" in m for m in canal.mensajes)
        assert str(canal.id) not in main.conversation_state

    async def apagado():
        canal = await _ir_hasta("apagado_batidoras", 5)
        main.consultar_grok = _grok(False)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        await main.manejar_respuesta(_Msg(canal, "sí"))
        await main.manejar_respuesta(_Msg(canal, "", video="pinon-5.mp4"))
        assert any("Agua sal" in m for m in canal.mensajes)
        assert not any("Batidora 6" in m for m in canal.mensajes)
        state = main.conversation_state[str(canal.id)]
        assert state["fase"] == "agua_sal" and state["batidora"] == 5

    asyncio.run(encendido())
    asyncio.run(apagado())


class _Resp:
    def __init__(self):
        self.done = False

    def is_done(self):
        return self.done

    async def edit_message(self, **kwargs):
        self.done = True

    async def send_message(self, content, **kwargs):
        self.done = True
        self.content = content

    async def defer(self):
        self.done = True


class _Inter:
    def __init__(self, canal, uid=7):
        self.channel = canal
        self.user = _Usuario()
        self.user.id = uid
        self.response = _Resp()


def test_boton_viejo_de_trabajo_ya_no_esta_activo():
    async def correr():
        canal = await _ir_hasta("apagado_batidoras", 2)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        state = main.conversation_state[str(canal.id)]
        assert state["fase"] == "video" and state["batidora"] == 2
        view = main.TrabajoHoyView(str(canal.id), 2)
        inter = _Inter(canal)
        await view._resolver(inter, False)
        assert inter.response.content == "Esa pregunta ya no está activa."
        assert state["fase"] == "video" and state["batidora"] == 2
        assert state["answers"]["apagado_batidoras_bat2_trabajo"] == "si"

    asyncio.run(correr())


def test_texto_en_la_pregunta_y_en_el_video_de_la_2():
    """El caso de Karina: «la 2 está en reparación» no puede seguir pidiendo video."""

    async def en_la_pregunta():
        canal = await _ir_hasta("apagado_batidoras", 2)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        await main.manejar_respuesta(_Msg(canal, "está en reparación"))
        assert not any("trabajó hoy" in m for m in canal.mensajes)
        videos = [m for m in canal.mensajes if "video del piñón de la batidora 2" in m]
        assert len(videos) == 1
        state = main.conversation_state[str(canal.id)]
        assert "reparación" in state["answers"]["apagado_batidoras_bat2_video"]
        assert state["batidora"] == 3

    async def en_el_video():
        canal = await _ir_hasta("encendido_batidoras", 2)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        state = main.conversation_state[str(canal.id)]
        assert state["fase"] == "video"
        await main.manejar_respuesta(_Msg(canal, "la 2 está en reparación"))
        assert state["batidora"] == 3
        assert state["fase"] == "checklist"
        assert "reparación" in state["answers"]["encendido_batidoras_bat2_video"]
        videos = [m for m in canal.mensajes if "video del piñón de la batidora 2" in m]
        assert len(videos) == 1

    asyncio.run(en_la_pregunta())
    asyncio.run(en_el_video())


def test_varias_fuera_y_reporte_completo_de_cinco():
    async def varias():
        canal = await _ir_hasta("apagado_batidoras", 1)
        for bat, como in (
            (1, "sí"),
            (2, "en reparacion"),
            (3, "sí"),
            (4, "no"),
            (5, "dañada"),
        ):
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == bat and state["fase"] == "checklist", (bat, state["fase"])
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
            assert state["fase"] == "video"
            if como == "dañada":
                await main.manejar_respuesta(_Msg(canal, "dañada"))
                continue
            if como == "sí":
                await main.manejar_respuesta(_Msg(canal, "sí"))
                await main.manejar_respuesta(_Msg(canal, "", video=f"pinon-{bat}.mp4"))
            elif como == "en reparacion":
                await main.manejar_respuesta(_Msg(canal, "en reparacion"))
            else:
                await main.manejar_respuesta(_Msg(canal, "no"))
        assert any("Agua sal" in m for m in canal.mensajes)
        assert not any("Batidora 6" in m for m in canal.mensajes)
        answers = main.conversation_state[str(canal.id)]["answers"]
        assert "reparacion" in answers["apagado_batidoras_bat2_video"].lower() or "reparación" in answers["apagado_batidoras_bat2_video"]
        assert "fuera de servicio" in answers["apagado_batidoras_bat4_video"]
        assert "dañada" in answers["apagado_batidoras_bat5_video"]
        assert "archivos" in str(answers["apagado_batidoras_bat1_video"])
        assert "archivos" in str(answers["apagado_batidoras_bat3_video"])

    async def cinco_encendido():
        canal = await _ir_hasta("encendido_batidoras", 1)
        for bat in range(1, 6):
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == bat and state["fase"] == "checklist"
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
            await main.manejar_respuesta(_Msg(canal, "Sí"))
            await main.manejar_respuesta(_Msg(canal, "", video=f"pin-{bat}.mp4"))
        assert any("Encendido de Batidoras completado" in m for m in canal.mensajes)
        assert not any("Batidora 6" in m for m in canal.mensajes)

    asyncio.run(varias())
    asyncio.run(cinco_encendido())


def test_no_en_agua_sal_avanza_y_no_repite_la_pregunta():
    """Regresión: «no» al agua sal no es «la máquina no trabaja»."""

    async def correr():
        llamadas = []

        async def grok(state, respuesta, tiene_media):
            llamadas.append(state["fase"])
            if (respuesta or "").strip().lower() == "no":
                return {
                    "respuesta_valida": False,
                    "es_fuera_de_servicio": True,
                    "mensaje": main.PREGUNTAS_CIERRE["agua_sal"],
                }
            return {
                "respuesta_valida": True,
                "es_fuera_de_servicio": False,
                "mensaje": None,
            }

        main.consultar_grok = grok
        canal = await _ir_hasta("apagado_batidoras", 1)
        for bat, fuera in ((1, False), (2, True), (3, False), (4, True), (5, False)):
            state = main.conversation_state[str(canal.id)]
            assert state["fase"] == "checklist" and state["batidora"] == bat
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
            if fuera:
                await main.manejar_respuesta(_Msg(canal, "la 2 está en reparación" if bat == 2 else "en reparacion"))
            else:
                await main.manejar_respuesta(_Msg(canal, "sí"))
                await main.manejar_respuesta(_Msg(canal, "", video=f"v{bat}.mp4"))
        state = main.conversation_state[str(canal.id)]
        assert state["fase"] == "agua_sal"
        antes = len(canal.mensajes)
        await main.manejar_respuesta(_Msg(canal, "no"))
        nuevos = canal.mensajes[antes:]
        assert not any("Agua sal" in m for m in nuevos), nuevos
        assert any("Limpieza" in m for m in nuevos), nuevos
        assert state["fase"] == "limpieza"
        assert state["answers"]["agua_sal_cambios"] == []
        assert "agua_sal" not in llamadas
        await main.manejar_respuesta(_Msg(canal, "sí"))
        assert state["fase"] == "hora_llegada"
        await main.manejar_respuesta(_Msg(canal, "7:00 am"))
        await main.manejar_respuesta(_Msg(canal, "12"))
        await main.manejar_respuesta(_Msg(canal, "12:40 pm"))
        await main.manejar_respuesta(_Msg(canal, "3"))
        await main.manejar_respuesta(_Msg(canal, "ninguna"))
        assert any("Reporte de Apagado" in m and "completado" in m for m in canal.mensajes)
        assert str(canal.id) not in main.conversation_state

    asyncio.run(correr())


AVISO_CIERRE = (
    "Listo con las 5 batidoras. Ahora van las preguntas del cierre, para todas juntas."
)

PREGUNTA_145 = (
    "De las que sí trabajaron hoy (la 1, la 4 y la 5): si alguna no hizo el día entero, "
    "escribe solo las horas que sí trabajó. Si una trabajó 4 horas, escribe 4. "
    "Si fueron dos, una de 4 horas y otra de 2 horas y media, escribe 4 y 2,5. "
    "Si todas hicieron el día entero, escribe NO."
)

REINTENTO_PARCIAL = (
    "No entendí. Si una trabajó 4 horas, escribe 4. "
    "Si fueron dos, una de 4 horas y otra de 2 horas y media, escribe 4 y 2,5. "
    "Si todas las que trabajaron hicieron el día entero, escribe NO."
)


def _preparar_culminacion(quienes_si):
    main.conversation_state.clear()
    canal = _Canal()
    answers = {
        "hora_llegada": "7:00 am",
        "batidas": 12,
        "limpio": True,
        "agua_sal_cambios": [],
    }
    for n in range(1, 6):
        answers[f"apagado_batidoras_bat{n}_trabajo"] = "si" if n in quienes_si else "no"
    main.conversation_state[str(canal.id)] = {
        "tipo": "apagado_batidoras",
        "user_id": 7,
        "fase": "hora_culminacion",
        "batidora": 5,
        "buffer": "",
        "answers": answers,
        "videos_usados": [],
        "hora_global": None,
    }
    return canal


async def _cerrar_y_ver(canal, texto):
    visto = {}
    original = main._cerrar_apagado

    async def _wrap(message, state):
        visto["dia"] = state["answers"].get("batidoras_dia")
        visto["num"] = state["answers"].get("num_batidoras")
        visto["horas"] = list(state["answers"].get("batidoras_parciales") or [])
        await original(message, state)

    main._cerrar_apagado = _wrap
    try:
        await main.manejar_respuesta(_Msg(canal, texto))
    finally:
        main._cerrar_apagado = original
    return visto


def test_checklist_en_reparacion_no_pregunta_botones():
    async def correr():
        for tipo, marca in (
            ("apagado_batidoras", False),
            ("encendido_batidoras", True),
        ):
            canal = await _ir_hasta(tipo, 3)
            main.consultar_grok = _grok(marca)
            antes = len(canal.mensajes)
            await main.manejar_respuesta(_Msg(canal, "la 3 está en reparación"))
            nuevos = canal.mensajes[antes:]
            assert not any("trabajó hoy" in m for m in nuevos), (tipo, nuevos)
            assert not any("video del piñón" in m for m in nuevos), (tipo, nuevos)
            state = main.conversation_state[str(canal.id)]
            assert state["answers"][f"{tipo}_bat3_trabajo"] == "no"
            assert state["batidora"] == 4 and state["fase"] == "checklist"
            assert "reparación" in state["answers"][f"{tipo}_bat3_video"]

    asyncio.run(correr())


def test_cierre_cuenta_quien_trabajo_y_pregunta_la_1_la_4_y_la_5():
    async def correr():
        main.consultar_grok = _grok(False)
        main.conversation_state.clear()
        canal = _Canal()
        await main._iniciar(canal, _Usuario(), "apagado_batidoras")
        for bat in range(1, 6):
            state = main.conversation_state[str(canal.id)]
            assert state["fase"] == "checklist" and state["batidora"] == bat
            if bat in (1, 4, 5):
                await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
                assert state["fase"] == "video"
                assert state["answers"][f"apagado_batidoras_bat{bat}_trabajo"] == "si"
                await main.manejar_respuesta(_Msg(canal, "", video=f"p{bat}.mp4"))
            else:
                await main.manejar_respuesta(_Msg(canal, "en reparación"))
                assert state["answers"][f"apagado_batidoras_bat{bat}_trabajo"] == "no"
        assert not any("trabajó hoy" in m for m in canal.mensajes)
        assert any(
            m == AVISO_CIERRE + "\n\n" + main.PREGUNTAS_CIERRE["agua_sal"]
            for m in canal.mensajes
        )
        await main.manejar_respuesta(_Msg(canal, "no"))
        await main.manejar_respuesta(_Msg(canal, "sí"))
        await main.manejar_respuesta(_Msg(canal, "7:00 am"))
        await main.manejar_respuesta(_Msg(canal, "12"))
        await main.manejar_respuesta(_Msg(canal, "12:40 pm"))
        state = main.conversation_state[str(canal.id)]
        assert state["fase"] == "batidoras_parcial"
        assert canal.mensajes[-1] == PREGUNTA_145
        assert not any("trabajaron todo el día" in m for m in canal.mensajes)
        visto = await _cerrar_y_ver(canal, "4 y 2,5")
        assert visto == {"dia": 1, "num": 1, "horas": [4, 2.5]}
        assert any("completado" in m for m in canal.mensajes)

    asyncio.run(correr())


def test_sin_parciales_el_dia_es_cuantas_trabajaron():
    async def correr():
        for texto in ("NO", "no", "0", "ninguna"):
            canal = _preparar_culminacion({1, 4, 5})
            await main.manejar_respuesta(_Msg(canal, "12:40 pm"))
            assert main.conversation_state[str(canal.id)]["fase"] == "batidoras_parcial"
            visto = await _cerrar_y_ver(canal, texto)
            assert visto == {"dia": 3, "num": 3, "horas": []}, texto

    asyncio.run(correr())


def test_repregunta_si_hay_mas_horas_que_las_que_trabajaron():
    async def correr():
        canal = _preparar_culminacion({1, 4, 5})
        await main.manejar_respuesta(_Msg(canal, "12:40 pm"))
        state = main.conversation_state[str(canal.id)]
        await main.manejar_respuesta(_Msg(canal, "4 y 2,5 y 1 y 3"))
        assert state["fase"] == "batidoras_parcial"
        assert str(canal.id) in main.conversation_state
        assert not any("completado" in m for m in canal.mensajes)
        assert canal.mensajes[-1] == main._MSG_MAS_HORAS_QUE_TRABAJARON
        assert "batidoras_dia" not in state["answers"]

    asyncio.run(correr())


def test_si_ninguna_trabajo_se_salta_la_parcial():
    async def correr():
        main.consultar_grok = _grok(False)
        main.conversation_state.clear()
        canal = _Canal()
        await main._iniciar(canal, _Usuario(), "apagado_batidoras")
        for _ in range(5):
            await main.manejar_respuesta(_Msg(canal, "en reparación"))
        assert not any("trabajó hoy" in m or "video del piñón" in m for m in canal.mensajes)
        await main.manejar_respuesta(_Msg(canal, "no"))
        await main.manejar_respuesta(_Msg(canal, "sí"))
        await main.manejar_respuesta(_Msg(canal, "7:00 am"))
        await main.manejar_respuesta(_Msg(canal, "12"))
        antes = len(canal.mensajes)
        visto = await _cerrar_y_ver(canal, "12:40 pm")
        nuevos = canal.mensajes[antes:]
        assert visto == {"dia": 0, "num": 0, "horas": []}
        assert not any("De las que sí trabajaron" in m for m in nuevos)
        assert not any("trabajaron todo el día" in m for m in canal.mensajes)
        assert any("ninguna batidora" in m for m in nuevos)
        assert any("completado" in m for m in canal.mensajes)

    asyncio.run(correr())


def test_pregunta_parcial_una_o_dos_y_el_reintento():
    async def correr():
        canal = _preparar_culminacion({1})
        await main.manejar_respuesta(_Msg(canal, "12:40 pm"))
        assert canal.mensajes[-1] == (
            "De las que sí trabajaron hoy (la 1): si alguna no hizo el día entero, "
            "escribe solo las horas que sí trabajó. Si una trabajó 4 horas, escribe 4. "
            "Si fueron dos, una de 4 horas y otra de 2 horas y media, escribe 4 y 2,5. "
            "Si esa hizo el día entero, escribe NO."
        )
        canal = _preparar_culminacion({1, 4})
        await main.manejar_respuesta(_Msg(canal, "12:40 pm"))
        assert canal.mensajes[-1] == (
            "De las que sí trabajaron hoy (la 1 y la 4): si alguna no hizo el día entero, "
            "escribe solo las horas que sí trabajó. Si una trabajó 4 horas, escribe 4. "
            "Si fueron dos, una de 4 horas y otra de 2 horas y media, escribe 4 y 2,5. "
            "Si todas hicieron el día entero, escribe NO."
        )

    asyncio.run(correr())
    decision = main._combinar_decision_cierre(
        {"fase": "batidoras_parcial", "answers": {"batidoras_dia": 3}},
        "sí",
        {},
    )
    assert decision["respuesta_valida"] is False
    assert decision["mensaje"] == REINTENTO_PARCIAL


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"{len(tests)} pruebas ok")

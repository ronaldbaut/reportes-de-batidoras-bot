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
            assert any("¿La **batidora 4** trabajó hoy?" in m for m in nuevos), nuevos
            assert not any("video del piñón" in m for m in nuevos), nuevos
            assert not any("fuera de servicio" in m for m in nuevos), nuevos
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == 4 and state["fase"] == "trabajo_hoy"
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
    """Dos máquinas paradas: no hay video, queda el motivo y sigue la siguiente."""

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
            canal = await _ir_hasta("apagado_batidoras", 4 if i % 2 == 0 else 2)
            # Aunque el modelo diga que el checklist está incompleto.
            main.consultar_grok = _grok(False, valida=False)
            antes = len(canal.mensajes)
            await main.manejar_respuesta(_Msg(canal, frase))
            nuevos = canal.mensajes[antes:]
            assert not any("video del piñón" in m for m in nuevos), (frase, nuevos)
            assert any("no en uso" in m and frase in m for m in nuevos), (frase, nuevos)
            state = main.conversation_state[str(canal.id)]
            bat = 4 if i % 2 == 0 else 2
            guardado = state["answers"][f"apagado_batidoras_bat{bat}_video"]
            assert "fuera de servicio" in guardado and frase in guardado
            assert state["batidora"] == bat + 1
            assert state["fase"] == "checklist"

    asyncio.run(correr())


def test_la_cuarta_fuera_de_servicio_si_pasa_a_la_quinta():
    async def caso(tipo):
        canal = await _ir_hasta(tipo, 4)
        main.consultar_grok = _grok(True)
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


def test_boton_no_en_reparacion_no_pide_video():
    async def correr():
        canal = await _ir_hasta("apagado_batidoras", 2)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        state = main.conversation_state[str(canal.id)]
        assert state["fase"] == "trabajo_hoy" and state["batidora"] == 2
        view = main.TrabajoHoyView(str(canal.id), 2)
        await view._resolver(_Inter(canal), False)
        assert not any("video del piñón de la batidora 2" in m for m in canal.mensajes)
        assert any("batidora 2" in m.lower() and "no en uso" in m for m in canal.mensajes)
        guardado = state["answers"]["apagado_batidoras_bat2_video"]
        assert "reparación o parada" in guardado
        assert state["batidora"] == 3 and state["fase"] == "checklist"

    asyncio.run(correr())


def test_texto_en_la_pregunta_y_en_el_video_de_la_2():
    """El caso de Karina: «la 2 está en reparación» no puede seguir pidiendo video."""

    async def en_la_pregunta():
        canal = await _ir_hasta("apagado_batidoras", 2)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        await main.manejar_respuesta(_Msg(canal, "está en reparación"))
        assert not any("video del piñón de la batidora 2" in m for m in canal.mensajes)
        state = main.conversation_state[str(canal.id)]
        assert "reparación" in state["answers"]["apagado_batidoras_bat2_video"]
        assert state["batidora"] == 3

    async def en_el_video():
        canal = await _ir_hasta("encendido_batidoras", 2)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        await main.manejar_respuesta(_Msg(canal, "sí"))
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
            (4, "boton-no"),
            (5, "dañada"),
        ):
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == bat and state["fase"] == "checklist", (bat, state["fase"])
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK if como != "dañada" else "dañada"))
            if como == "dañada":
                continue
            assert state["fase"] == "trabajo_hoy"
            if como == "sí":
                await main.manejar_respuesta(_Msg(canal, "sí"))
                await main.manejar_respuesta(_Msg(canal, "", video=f"pinon-{bat}.mp4"))
            elif como == "en reparacion":
                await main.manejar_respuesta(_Msg(canal, "en reparacion"))
            else:
                view = main.TrabajoHoyView(str(canal.id), bat)
                await view._resolver(_Inter(canal), False)
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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"{len(tests)} pruebas ok")

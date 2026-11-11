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

    async def send(self, texto):
        self.mensajes.append(texto)


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
        if state["fase"] == "video":
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


def test_la_cuarta_no_se_salta_si_el_modelo_la_marca_fuera():
    """Inicio y cierre: un checklist normal de la 4 pide video y sigue a la 5."""

    async def caso(tipo):
        for marca in (True, "false"):
            canal = await _ir_hasta(tipo, 4)
            main.consultar_grok = _grok(marca)
            antes = len(canal.mensajes)
            await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
            nuevos = canal.mensajes[antes:]
            assert any("video del piñón de la batidora 4" in m for m in nuevos), nuevos
            assert not any("fuera de servicio" in m for m in nuevos), nuevos
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == 4 and state["fase"] == "video"
            await main.manejar_respuesta(_Msg(canal, "", video="pinon-4.mp4"))
            assert any(m.startswith("**Batidora 5**") for m in canal.mensajes), canal.mensajes[-1]
            state = main.conversation_state[str(canal.id)]
            assert state["batidora"] == 5 and state["fase"] == "checklist"

    asyncio.run(caso("encendido_batidoras"))
    asyncio.run(caso("apagado_batidoras"))


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
        await main.manejar_respuesta(_Msg(canal, "", video="pinon-5.mp4"))
        assert any("Encendido de Batidoras completado" in m for m in canal.mensajes)
        assert not any("Batidora 6" in m for m in canal.mensajes)
        assert str(canal.id) not in main.conversation_state

    async def apagado():
        canal = await _ir_hasta("apagado_batidoras", 5)
        main.consultar_grok = _grok(False)
        await main.manejar_respuesta(_Msg(canal, CHECKLIST_OK))
        await main.manejar_respuesta(_Msg(canal, "", video="pinon-5.mp4"))
        assert any("Agua sal" in m for m in canal.mensajes)
        assert not any("Batidora 6" in m for m in canal.mensajes)
        state = main.conversation_state[str(canal.id)]
        assert state["fase"] == "agua_sal" and state["batidora"] == 5

    asyncio.run(encendido())
    asyncio.run(apagado())


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"{len(tests)} pruebas ok")

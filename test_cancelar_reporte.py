"""Cancelar tiene que borrar el reporte aunque no lo haya abierto esa persona."""
import asyncio
import os

os.environ.setdefault("DISCORD_TOKEN", "test")
os.environ.setdefault("XAI_API_KEY", "test")

import main


class _Canal:
    def __init__(self, cid=77, parent_id=None):
        self.id = cid
        self.parent_id = parent_id
        self.mensajes = []

    async def send(self, texto):
        self.mensajes.append(texto)


class _Usuario:
    def __init__(self, uid):
        self.id = uid
        self.bot = False
        self.mention = f"<@{uid}>"
        self.display_name = "Karina"


class _Msg:
    def __init__(self, canal, uid, contenido):
        self.channel = canal
        self.author = _Usuario(uid)
        self.content = contenido
        self.attachments = []


def test_frases_de_cancelar():
    assert main._es_orden_cancelar("cancelar")
    assert main._es_orden_cancelar("Cancelar")
    assert main._es_orden_cancelar("cancelar.")
    assert main._es_orden_cancelar("**cancelar**")
    assert main._es_orden_cancelar("cancelar reporte")
    assert main._es_orden_cancelar("cancelar el reporte")
    assert main._es_orden_cancelar("cancela")
    assert main._es_orden_cancelar("por favor cancelar")
    assert not main._es_orden_cancelar("no cancelar la producción")
    assert not main._es_orden_cancelar("dientes completos, piñón bien")


def test_cancelar_de_otra_persona_borra_el_reporte():
    async def correr():
        main.conversation_state.clear()
        canal = _Canal()
        main.conversation_state[str(canal.id)] = {
            "tipo": "apagado_batidoras",
            "user_id": 999,
            "fase": "checklist",
            "batidora": 4,
        }
        await main.on_message(_Msg(canal, 7, "cancelar"))
        assert str(canal.id) not in main.conversation_state
        assert any("cancelado" in m for m in canal.mensajes)
        await main._iniciar(canal, _Usuario(7), "encendido_batidoras")
        assert main.conversation_state[str(canal.id)]["user_id"] == 7
        assert any("iniciado" in m.lower() for m in canal.mensajes)

    asyncio.run(correr())


def test_cancelar_en_el_hilo_borra_el_canal():
    async def correr():
        main.conversation_state.clear()
        hilo = _Canal(cid=88, parent_id=77)
        main.conversation_state["77"] = {"user_id": 999, "fase": "checklist", "batidora": 4}
        await main.on_message(_Msg(hilo, 7, "cancelar el reporte"))
        assert "77" not in main.conversation_state
        assert any("cancelado" in m for m in hilo.mensajes)

    asyncio.run(correr())


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"{len(tests)} pruebas ok")

import discord
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

conversation_state = {}

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip().lower()
    channel_id = str(message.channel.id)

    if content in ["cancelar", "cancelar reporte"]:
        if channel_id in conversation_state:
            del conversation_state[channel_id]
            await message.channel.send("✅ Reporte cancelado.")
        return

    if content == "iniciar reporte de cierre":
        await iniciar_reporte_cierre(message.channel)
    elif content == "reporte de inicio de batidoras":
        await reporte_inicio_batidoras(message.channel)
    elif content == "reporte de funcionamiento de batidoras":
        await reporte_funcionamiento_batidoras(message.channel)
    elif content == "reporte de apagado de batidoras":
        await reporte_apagado_batidoras(message.channel)

    elif channel_id in conversation_state:
        await manejar_respuesta(message)

# ================== INICIO DE REPORTES ==================
async def iniciar_reporte_cierre(channel):
    conversation_state[str(channel.id)] = {"tipo": "cierre", "paso": 1}
    await channel.send("**Reporte de Cierre iniciado.**\n\n1. ¿Qué trabajadores alistaron los pedidos?")

async def reporte_inicio_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "inicio_batidoras", "batidora": 1, "paso": 1}
    await channel.send("**Reporte de Inicio de Batidoras iniciado.**\n\n**Batidora 1**\n1. ¿Revisaste la tensión de las correas?")

async def reporte_funcionamiento_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "funcionamiento_batidoras", "batidora": 1, "paso": 1}
    await channel.send("**Reporte de Funcionamiento de Batidoras iniciado.**\n\n**Batidora 1**\n1. ¿La temperatura del cabezote está por debajo de 50°? ¿Cuál es la temperatura exacta?")

async def reporte_apagado_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "apagado_batidoras", "batidora": 1, "paso": 1}
    await channel.send("**Reporte de Apagado de Batidoras iniciado.**\n\n**Batidora 1**\n1. ¿Revisaste los dientes del piñón? (envía video)")

# ================== MANEJO DE RESPUESTAS ==================
async def manejar_respuesta(message):
    channel_id = str(message.channel.id)
    state = conversation_state[channel_id]
    tipo = state["tipo"]
    bat = state["batidora"]
    paso = state["paso"]

    text = message.content.lower()

    # Si dice que la batidora no está en funcionamiento, saltamos a la siguiente
    if any(word in text for word in ["no está en funcionamiento", "no funciona", "apagada", "no enciende", "no operativa"]):
        if bat < 5:
            state["batidora"] = bat + 1
            state["paso"] = 1
            await message.channel.send(f"✅ Batidora {bat} saltada. Pasando a **Batidora {bat + 1}**")
            if tipo == "inicio_batidoras":
                await message.channel.send("1. ¿Revisaste la tensión de las correas?")
            elif tipo == "funcionamiento_batidoras":
                await message.channel.send("1. ¿La temperatura del cabezote está por debajo de 50°? ¿Cuál es la temperatura exacta?")
            elif tipo == "apagado_batidoras":
                await message.channel.send("1. ¿Revisaste los dientes del piñón? (envía video)")
            return

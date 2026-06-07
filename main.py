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
    conversation_state[str(channel.id)] = {"tipo": "inicio_batidoras", "paso": 1}
    await channel.send("**Reporte de Inicio de Batidoras iniciado.**\n\n1. ¿Revisaste la tensión de las correas?")

async def reporte_funcionamiento_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "funcionamiento_batidoras", "paso": 1}
    await channel.send("**Reporte de Funcionamiento de Batidoras iniciado.**\n\n1. ¿La temperatura del cabezote de la batidora 1 está por debajo de 50°?")

async def reporte_apagado_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "apagado_batidoras", "paso": 1}
    await channel.send("**Reporte de Apagado de Batidoras iniciado.**\n\n1. ¿Revisaste los dientes del piñón?")

# ================== MANEJO DE RESPUESTAS ==================
async def manejar_respuesta(message):
    channel_id = str(message.channel.id)
    state = conversation_state[channel_id]
    tipo = state["tipo"]
    paso = state["paso"]

    await message.channel.send(f"✅ Recibido: {message.content}")

    if tipo == "funcionamiento_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send("2. ¿La temperatura del cabezote de la batidora 2 está por debajo de 50°?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send("3. ¿La temperatura del cabezote de la batidora 3 está por debajo de 50°?")
        elif paso == 3:
            state["paso"] = 4
            await message.channel.send("4. ¿La temperatura del cabezote de la batidora 4 está por debajo de 50°?")
        elif paso == 4:
            state["paso"] = 5
            await message.channel.send("5. ¿La temperatura del cabezote de la batidora 5 está por debajo de 50°?")
        elif paso == 5:
            state["paso"] = 6
            await message.channel.send("6. ¿Se respetaron los tiempos de batida sin excepciones?")
        elif paso == 6:
            state["paso"] = 7
            await message.channel.send("7. ¿Cuáles son los tiempos promedio de cada batidora?")
        else:
            await message.channel.send("✅ Reporte de Funcionamiento de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]

    # Otros reportes (mantienen su flujo anterior)
    elif tipo == "inicio_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send("2. ¿Revisaste las chavetas del eje de batido?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send("3. ¿Aplicaste grasa al piñón?")
        else:
            await message.channel.send("✅ Reporte de Inicio de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]

    elif tipo == "apagado_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send("2. ¿Revisaste el ajuste del piñón?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send("3. ¿Revisaste la protección del rodamiento arriba?")
        elif paso == 3:
            state["paso"] = 4
            await message.channel.send("4. ¿Revisaste el movimiento en ambos sentidos del eje del tambor?")
        else:
            await message.channel.send("✅ Reporte de Apagado de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]

    else:
        await message.channel.send("✅ Respuesta guardada.")
        del conversation_state[channel_id]

client.run(DISCORD_TOKEN)

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
    await channel.send("**Reporte de Inicio de Batidoras iniciado.**\n\n1. ¿Revisaste la tensión de las correas de la batidora 1?")

async def reporte_funcionamiento_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "funcionamiento_batidoras", "paso": 1}
    await channel.send("**Reporte de Funcionamiento de Batidoras iniciado.**\n\n1. ¿La temperatura del cabezote de la batidora 1 está por debajo de 50°?")

async def reporte_apagado_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "apagado_batidoras", "paso": 1}
    await channel.send("**Reporte de Apagado de Batidoras iniciado.**\n\n1. ¿Revisaste los dientes del piñón de la batidora 1? (envía foto)")

# ================== MANEJO DE RESPUESTAS ==================
async def manejar_respuesta(message):
    channel_id = str(message.channel.id)
    state = conversation_state[channel_id]
    tipo = state["tipo"]
    paso = state["paso"]

    await message.channel.send(f"✅ Recibido: {message.content}")

    if tipo == "cierre":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send("2. ¿A qué clientes pertenecen los pedidos que se alistaron?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send("3. ¿Cómo quedaron los pedidos? (cuáles se completaron, cuáles quedaron pendientes, observaciones)")
        elif paso == 3:
            state["paso"] = 4
            await message.channel.send("4. ¿En qué congeladores quedaron cuáles pedidos?")
        elif paso == 4:
            state["paso"] = 5
            await message.channel.send("5. ¿A qué hora se comenzaron a alistar los pedidos y a qué hora terminaron?")
        else:
            await message.channel.send("✅ Reporte de Cierre completado. ¡Gracias!")
            del conversation_state[channel_id]

    elif tipo == "funcionamiento_batidoras":
        if paso <= 5:
            bat = paso
            state["paso"] = paso + 1
            await message.channel.send(f"{paso + 1}. ¿Está raspando correctamente la batidora {bat}?")
        else:
            await message.channel.send("✅ Reporte de Funcionamiento de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]

    elif tipo == "inicio_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send("2. ¿Revisaste las chavetas del eje de batido de la batidora 1?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send("3. ¿Está adecuadamente engrasado el piñón de la batidora 1?")
        # ... (puedes seguir agregando las demás preguntas aquí)
        else:
            await message.channel.send("✅ Reporte de Inicio de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]

    elif tipo == "apagado_batidoras":
        if paso <= 5:
            bat = paso
            state["paso"] = paso + 1
            await message.channel.send(f"{paso + 1}. ¿Revisaste los dientes del piñón de la batidora {bat}? (envía foto)")
        else:
            await message.channel.send("✅ Reporte de Apagado de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]

    else:
        await message.channel.send("✅ Respuesta guardada.")
        del conversation_state[channel_id]

client.run(DISCORD_TOKEN)

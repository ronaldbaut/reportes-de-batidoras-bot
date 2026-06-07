import discord
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

# Estado de las conversaciones por canal
conversation_state = {}

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()
    channel_id = str(message.channel.id)

    # Comandos para iniciar reportes
    if content == "iniciar reporte de cierre":
        await iniciar_reporte_cierre(message.channel)
    elif content == "Reporte de inicio de batidoras":
        await reporte_inicio_batidoras(message.channel)
    elif content == "Reporte de funcionamiento de batidoras":
        await reporte_funcionamiento_batidoras(message.channel)
    elif content == "Reporte de apagado de batidoras":
        await reporte_apagado_batidoras(message.channel)

    # Si hay una conversación activa
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
    await channel.send("**Reporte de Funcionamiento de Batidoras iniciado.**\n\n1. ¿La temperatura del cabezote está por debajo de 50° en todas las batidoras?")

async def reporte_apagado_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "apagado_batidoras", "paso": 1}
    await channel.send("**Reporte de Apagado de Batidoras iniciado.**\n\n1. ¿Revisaste los dientes del piñón?")

# ================== MANEJO DE RESPUESTAS ==================
async def manejar_respuesta(message):
    channel_id = str(message.channel.id)
    state = conversation_state[channel_id]
    tipo = state["tipo"]
    paso = state["paso"]

    # Aquí puedes agregar más preguntas según el tipo y paso
    await message.channel.send(f"✅ Recibido: {message.content}")

    if tipo == "inicio_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send("2. ¿Revisaste las chavetas del eje de batido?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send("3. ¿Aplicaste grasa al piñón?")
        else:
            await message.channel.send("✅ Reporte de Inicio de Batidoras completado. Gracias!")
            del conversation_state[channel_id]

    # (Puedes agregar los flujos completos de los otros reportes aquí)
    # Por ahora los otros reportes solo avanzan 1 paso. Dime y agrego todos los pasos.

    else:
        await message.channel.send("✅ Respuesta guardada. Reporte en progreso...")
        # Temporal: termina la conversación
        del conversation_state[channel_id]

client.run(DISCORD_TOKEN)

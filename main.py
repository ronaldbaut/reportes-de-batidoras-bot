import discord
import google.generativeai as genai
import os
from datetime import datetime

# ================== CONFIGURACIÓN ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

# Diccionario para guardar el estado de cada conversación por canal
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

    # ================== COMANDOS ==================
    if content == "iniciar reporte de cierre":
        await iniciar_reporte_cierre(message.channel)
    elif content == "Reporte de inicio de batidoras":
        await reporte_inicio_batidoras(message.channel)
    elif content == "Reporte de funcionamiento de batidoras":
        await reporte_funcionamiento_batidoras(message.channel)
    elif content == "Reporte de apagado de batidoras":
        await reporte_apagado_batidoras(message.channel)

    # Si ya hay una conversación activa en este canal
    elif channel_id in conversation_state:
        await manejar_respuesta(message)

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

async def manejar_respuesta(message):
    channel_id = str(message.channel.id)
    state = conversation_state[channel_id]
    # Aquí irían las preguntas siguientes según el tipo y paso
    # (por ahora solo mostramos que recibió la respuesta)
    await message.channel.send(f"✅ Recibido: {message.content}\n\nSiguiente pregunta en desarrollo...")
    # En futuras actualizaciones agregaremos todas las preguntas secuenciales

# ================== EJECUCIÓN ==================
client.run(DISCORD_TOKEN)
import discord
from discord.ext import commands
import os
import traceback
from openai import OpenAI
import json

print(">>> Iniciando reportes-de-batidoras-bot...")

# ================== CONFIGURACIÓN ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("❌ ERROR: Falta la variable de entorno DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Cliente de xAI (Grok)
client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

conversation_state = {}

# ================== COMANDOS SLASH ==================
@bot.tree.command(name="reporte-encendido-batidoras", description="Inicia el Reporte de Encendido de Batidoras")
async def reporte_encendido_batidoras_slash(interaction: discord.Interaction):
    channel = interaction.channel
    conversation_state[str(channel.id)] = {"tipo": "encendido_batidoras", "hora_recibida": False}
    await interaction.response.send_message(
        "**Reporte de Encendido de Batidoras iniciado.**\n\n"
        "¿A qué hora se encendieron las batidoras?\n\n"
        "_Escribe **cancelar** o **cancelar reporte** en cualquier momento para detenerlo._"
    )

@bot.tree.command(name="reporte-funcionamiento-batidoras", description="Inicia el Reporte de Funcionamiento de Batidoras")
async def reporte_funcionamiento_batidoras_slash(interaction: discord.Interaction):
    channel = interaction.channel
    conversation_state[str(channel.id)] = {"tipo": "funcionamiento_batidoras", "batidora": 1}
    await interaction.response.send_message(
        "**Reporte de Funcionamiento de Batidoras iniciado.**\n\n"
        "**Batidora 1**\n\n"
        "Verifica durante el funcionamiento: (temperatura del cabezote por debajo de 50° y temperatura exacta actual, si está raspando correctamente la mezcla). ¿Cuál es la temperatura del cabezote y está raspando bien?\n\n"
        "_Escribe **cancelar** o **cancelar reporte** en cualquier momento para detenerlo._"
    )

@bot.tree.command(name="reporte-apagado-batidoras", description="Inicia el Reporte de Apagado de Batidoras")
async def reporte_apagado_batidoras_slash(interaction: discord.Interaction):
    channel = interaction.channel
    conversation_state[str(channel.id)] = {"tipo": "apagado_batidoras", "batidora": 1, "paso": 1}
    await interaction.response.send_message(
        "**Reporte de Apagado de Batidoras iniciado.**\n\n"
        "**Batidora 1**\n\n"
        "Al apagar confirma: (dientes del piñón, ajuste del piñón, subir cuchilla y la protección del rodamiento, movimiento del eje del tambor en ambos sentidos, hora de encendido y apagado, cantidad de colores batidos, tiempo promedio de las batidas trisabor/gourmet/clásica/sundae). Reporta el estado y los datos.\n\n"
        "_Escribe **cancelar** o **cancelar reporte** en cualquier momento para detenerlo._"
    )

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} slash commands sincronizados correctamente")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")
        traceback.print_exc()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip().lower()
    channel_id = str(message.channel.id)

    if "cancelar" in content:
        if channel_id in conversation_state:
            del conversation_state[channel_id]
            await message.channel.send("✅ Reporte cancelado.")
        return

    if content in ["reporte de encendido de batidoras", "iniciar reporte de encendido de batidoras"]:

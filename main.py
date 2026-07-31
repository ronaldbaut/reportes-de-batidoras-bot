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
        await reporte_encendido_batidoras(message.channel)
    elif content in ["reporte de funcionamiento de batidoras", "iniciar reporte de funcionamiento de batidoras"]:
        await reporte_funcionamiento_batidoras(message.channel)
    elif content in ["reporte de apagado de batidoras", "iniciar reporte de apagado de batidoras"]:
        await reporte_apagado_batidoras(message.channel)
    elif channel_id in conversation_state:
        await manejar_respuesta(message)

# ================== INICIO DE REPORTES ==================
async def reporte_encendido_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "encendido_batidoras", "hora_recibida": False}
    await channel.send(
        "**Reporte de Encendido de Batidoras iniciado.**\n\n"
        "¿A qué hora se encendieron las batidoras?\n\n"
        "_Escribe **cancelar** o **cancelar reporte** en cualquier momento para detenerlo._"
    )

async def reporte_funcionamiento_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "funcionamiento_batidoras", "batidora": 1}
    await channel.send(
        "**Reporte de Funcionamiento de Batidoras iniciado.**\n\n"
        "**Batidora 1**\n\n"
        "Verifica durante el funcionamiento: (temperatura del cabezote por debajo de 50° y temperatura exacta actual, si está raspando correctamente la mezcla). ¿Cuál es la temperatura del cabezote y está raspando bien?\n\n"
        "_Escribe **cancelar** o **cancelar reporte** en cualquier momento para detenerlo._"
    )

async def reporte_apagado_batidoras(channel):
    conversation_state[str(channel.id)] = {"tipo": "apagado_batidoras", "batidora": 1, "paso": 1}
    await channel.send(
        "**Reporte de Apagado de Batidoras iniciado.**\n\n"
        "**Batidora 1**\n\n"
        "Al apagar confirma: (dientes del piñón, ajuste del piñón, subir cuchilla y la protección del rodamiento, movimiento del eje del tambor en ambos sentidos, hora de encendido y apagado, cantidad de colores batidos, tiempo promedio de las batidas trisabor/gourmet/clásica/sundae). Reporta el estado y los datos.\n\n"
        "_Escribe **cancelar** o **cancelar reporte** en cualquier momento para detenerlo._"
    )

# ================== FUNCIÓN QUE CONSULTA A GROK ==================
async def consultar_grok(estado_actual: dict, mensaje_usuario: str) -> dict:
    system_prompt = """
Eres un supervisor estricto de reportes de batidoras en una fábrica de helados.

Debes responder ÚNICAMENTE con un JSON válido con esta estructura:

{
  "respuesta_valida": true o false,
  "es_negativa": true o false,
  "accion": "avanzar" | "pedir_aclaracion" | "saltar_batidora" | "completar",
  "mensaje": null o "texto"
}

Reglas:
- Si la respuesta del trabajador es incompleta, corta o no responde exactamente lo que se preguntó → respuesta_valida = false
- Cuando respuesta_valida sea false, el campo "mensaje" debe ser un regaño directo y claro (ejemplo: "No me estás diciendo la temperatura exacta ni si está raspando bien. Responde completo.")
- Sé firme y directo, no amable ni educado de más.
- Si la respuesta es válida, pon "mensaje": null
- Sé estricto.
"""

    user_content = f"""
Estado actual del reporte:
{json.dumps(estado_actual, ensure_ascii=False, indent=2)}

Mensaje del trabajador:
"{mensaje_usuario}"
"""

    try:
        response = client.chat.completions.create(
            model="grok-4-1-fast",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error al consultar Grok: {e}")
        return {
            "respuesta_valida": True,
            "es_negativa": False,
            "accion": "avanzar",
            "mensaje": None
        }

# ================== MANEJO DE RESPUESTAS ==================
async def manejar_respuesta(message):
    channel_id = str(message.channel.id)
    state = conversation_state[channel_id]
    tipo = state["tipo"]

    try:
        await message.add_reaction("✅")
    except:
        pass

    decision = await consultar_grok(state, message.content)

    # Si la respuesta no es válida → regaño y paramos
    if not decision.get("respuesta_valida", True):
        mensaje = decision.get("mensaje") or "Tu respuesta está incompleta. Responde bien lo que se te preguntó."
        await message.channel.send(mensaje)
        return

    # ===== Respuesta válida =====
    if tipo == "encendido_batidoras":
        if not state.get("hora_recibida", False):
            state["hora_recibida"] = True
            state["batidora"] = 1
            state["paso"] = 1
            await message.channel.send(
                "**Batidora 1**\n\n"
                "Revisa lo siguiente antes de encender: (tensión de correas, chavetas del eje de batido, engrase del piñón, protección del rodamiento 6206, nivel óptimo de agua sal, ajuste del piñón sin juego, dientes completos del piñón, movimiento del tambor derecha-izquierda y arriba-abajo). ¿Todo está en buen estado?"
            )
            return

        bat = state.get("batidora", 1)
        paso = state.get("paso", 1)
        negativo = decision.get("es_negativa", False)

        if paso == 1:
            if negativo or decision.get("accion") == "saltar_batidora":
                if bat < 5:
                    next_bat = bat + 1
                    state["batidora"] = next_bat
                    state["paso"] = 1
                    await message.channel.send(
                        f"**Batidora {next_bat}**\n\n"
                        "Revisa lo siguiente antes de encender: (tensión de correas, chavetas del eje de batido, engrase del piñón, protección del rodamiento 6206, nivel óptimo de agua sal, ajuste del piñón sin juego, dientes completos del piñón, movimiento del tambor derecha-izquierda y arriba-abajo). ¿Todo está en buen estado?"
                    )
                else:
                    await message.channel.send("✅ Reporte de Encendido de Batidoras completado. ¡Gracias!")
                    del conversation_state[channel_id]
            else:
                state["paso"] = 2
                await message.channel.send(f"Por favor envía un video del piñón de la batidora {bat} (muestra los dientes y el estado general).")
        elif paso == 2:
            if bat < 5:
                next_bat = bat + 1
                state["batidora"] = next_bat
                state["paso"] = 1
                await message.channel.send(
                    f"**Batidora {next_bat}**\n\n"
                    "Revisa lo siguiente antes de encender: (tensión de correas, chavetas del eje de batido, engrase del piñón, protección del rodamiento 6206, nivel óptimo de agua sal, ajuste del piñón sin juego, dientes completos del piñón, movimiento del tambor derecha-izquierda y arriba-abajo). ¿Todo está en buen estado?"
                )
            else:
                await message.channel.send("✅ Reporte de Encendido de Batidoras completado. ¡Gracias!")
                del conversation_state[channel_id]

    elif tipo == "funcionamiento_batidoras":
        bat = state.get("batidora", 1)

        if bat >= 5 or decision.get("accion") == "completar":
            await message.channel.send("✅ Reporte de Funcionamiento de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]
        else:
            next_bat = bat + 1
            state["batidora"] = next_bat
            await message.channel.send(
                f"**Batidora {next_bat}**\n\n"
                "Verifica durante el funcionamiento: (temperatura del cabezote por debajo de 50° y temperatura exacta actual, si está raspando correctamente la mezcla). ¿Cuál es la temperatura del cabezote y está raspando bien?"
            )

    elif tipo == "apagado_batidoras":
        bat = state.get("batidora", 1)
        paso = state.get("paso", 1)
        negativo = decision.get("es_negativa", False)

        if paso == 1:
            if negativo or decision.get("accion") == "saltar_batidora":
                if bat < 5:
                    next_bat = bat + 1
                    state["batidora"] = next_bat
                    state["paso"] = 1
                    await message.channel.send(
                        f"**Batidora {next_bat}**\n\n"
                        "Al apagar confirma: (dientes del piñón, ajuste del piñón, subir cuchilla y la protección del rodamiento, movimiento del eje del tambor en ambos sentidos, hora de encendido y apagado, cantidad de colores batidos, tiempo promedio de las batidas trisabor/gourmet/clásica/sundae). Reporta el estado y los datos."
                    )
                else:
                    await message.channel.send("✅ Reporte de Apagado de Batidoras completado. ¡Gracias!")
                    del conversation_state[channel_id]
            else:
                state["paso"] = 2
                await message.channel.send(f"Por favor envía un video del piñón de la batidora {bat} (muestra los dientes y el estado general).")
        elif paso == 2:
            if bat < 5:
                next_bat = bat + 1
                state["batidora"] = next_bat
                state["paso"] = 1
                await message.channel.send(
                    f"**Batidora {next_bat}**\n\n"
                    "Al apagar confirma: (dientes del piñón, ajuste del piñón, subir cuchilla y la protección del rodamiento, movimiento del eje del tambor en ambos sentidos, hora de encendido y apagado, cantidad de colores batidos, tiempo promedio de las batidas trisabor/gourmet/clásica/sundae). Reporta el estado y los datos."
                )
            else:
                await message.channel.send("✅ Reporte de Apagado de Batidoras completado. ¡Gracias!")
                del conversation_state[channel_id]

# ================== INICIO DEL BOT ==================
bot.run(DISCORD_TOKEN)

import discord
from discord.ext import commands
import os
import traceback

print(">>> Iniciando reportes-de-batidoras-bot...")

# ================== CONFIGURACIÓN ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    raise RuntimeError("❌ ERROR: Falta la variable de entorno DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

conversation_state = {}

# ================== COMANDOS SLASH (para usar con /) ==================
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

    # === CANCELACIÓN MEJORADA (más flexible) ===
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


# ================== INICIO DE REPORTES (usados por comandos de texto) ==================
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


def es_respuesta_negativa(texto: str) -> bool:
    """Detecta si la respuesta indica que la batidora NO está funcionando / en mal estado."""
    t = texto.lower().strip()
    if not t:
        return False
    # Casos directos cortos
    if t in ["no", "nope", "mal", "nada", "ninguno", "falla", "fallo"]:
        return True
    patrones = [
        "no funciona",
        "no está funcionando",
        "no esta funcionando",
        "no trabaja",
        "no está bien",
        "no esta bien",
        "no enciende",
        "no prende",
        "no se enciende",
        "dañada",
        "dañado",
        "mal estado",
        "no sirve",
        "problema",
        "fallando",
        "no rasp",
        "no está raspando",
        "no esta raspando",
        "no está en buen estado",
        "no esta en buen estado",
        "no todo bien",
        "no,",
    ]
    return any(p in t for p in patrones)


# ================== MANEJO DE RESPUESTAS ==================
async def manejar_respuesta(message):
    channel_id = str(message.channel.id)
    state = conversation_state[channel_id]
    tipo = state["tipo"]

    # Solo el emoji de check, nada más. Luego se envía la siguiente pregunta.
    await message.channel.send("✅")

    if tipo == "encendido_batidoras":
        # Primera respuesta: hora de encendido (global)
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
        negativo = es_respuesta_negativa(message.content)

        if paso == 1:
            if negativo:
                # Saltar esta batidora (no pedir video), ir directo a la siguiente
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
                # Normal: pedir video
                state["paso"] = 2
                await message.channel.send(f"Por favor envía un video del piñón de la batidora {bat} (muestra los dientes y el estado general).")
        elif paso == 2:
            # Después del video → siguiente batidora
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

        if bat < 5:
            next_bat = bat + 1
            state["batidora"] = next_bat
            await message.channel.send(
                f"**Batidora {next_bat}**\n\n"
                "Verifica durante el funcionamiento: (temperatura del cabezote por debajo de 50° y temperatura exacta actual, si está raspando correctamente la mezcla). ¿Cuál es la temperatura del cabezote y está raspando bien?"
            )
        else:
            await message.channel.send("✅ Reporte de Funcionamiento de Batidoras completado. ¡Gracias!")
            del conversation_state[channel_id]

    elif tipo == "apagado_batidoras":
        bat = state.get("batidora", 1)
        paso = state.get("paso", 1)
        negativo = es_respuesta_negativa(message.content)

        if paso == 1:
            if negativo:
                # Saltar video y esta batidora, ir directo a la siguiente
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

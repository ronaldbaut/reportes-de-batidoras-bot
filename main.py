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
    paso = state["paso"]
    bat = state.get("batidora", 1)

    await message.channel.send(f"✅ Recibido: {message.content}")

    if tipo == "cierre":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send("2. ¿A qué clientes pertenecen los pedidos que se alistaron?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send("3. ¿Cómo quedaron los pedidos? (cuáles se completaron, cuáles quedaron pendientes, observaciones relevantes y cualquier ajuste para Producción mañana). En caso de que hayan pedidos incompletos, explica por qué quedaron incompletos.")
        elif paso == 3:
            state["paso"] = 4
            await message.channel.send("4. ¿En qué congeladores quedaron cuáles pedidos?")
        elif paso == 4:
            state["paso"] = 5
            await message.channel.send("5. ¿A qué hora se comenzaron a alistar los pedidos y a qué hora terminaron?")
        elif paso == 5:
            state["paso"] = 6
            await message.channel.send("6. ¿A qué hora empezaste y terminaste el envasado de bandejas? ¿Qué trabajadores se encargaron?")
        elif paso == 6:
            state["paso"] = 7
            await message.channel.send("7. ¿A qué hora empezaste y terminaste el envasado de vasitos? ¿Qué trabajadores envasaron?")
        elif paso == 7:
            state["paso"] = 8
            await message.channel.send("8. ¿A qué hora empezaste y terminaste la limpieza? ¿Qué trabajadores se encargaron?")
        elif paso == 8:
            state["paso"] = 9
            await message.channel.send("9. ¿Limpiaste los tambores de las batidoras y retiraste la sal de los cabezotes?")
        elif paso == 9:
            state["paso"] = 10
            await message.channel.send("10. ¿Cuánto gasoil tiene ahora la planta azul y cuál es el nivel de aceite?")
        elif paso == 10:
            state["paso"] = 11
            await message.channel.send("11. ¿Cuánto gasoil tiene ahora la planta roja y cuál es el nivel de aceite?")
        elif paso == 11:
            state["paso"] = 12
            await message.channel.send("12. ¿Todos los motores de los congeladores están encendidos, bien cerrados y calientes?")
        elif paso == 12:
            state["paso"] = 13
            await message.channel.send("13. ¿Cerraste con candado las puertas de los heladeros, el estacionamiento, la planta y la salida (con doble candado)?")
        elif paso == 13:
            state["paso"] = 14
            await message.channel.send("14. ¿Quedó apagado el aire acondicionado de producción y el de ventas?")
        elif paso == 14:
            state["paso"] = 15
            await message.channel.send("15. ¿Quedó registrada la producción del día completa en la hoja de cálculo correspondiente? ¿Quién lo hizo?")
        elif paso == 15:
            state["paso"] = 16
            await message.channel.send("16. ¿Oprimiste el botón rojo del tablero de batidoras?")
        elif paso == 16:
            state["paso"] = 17
            await message.channel.send("17. ¿Dejaron todas las luces de la fábrica apagadas?")
        elif paso == 17:
            state["paso"] = 18
            await message.channel.send("18. ¿Qué cantidad de gasoil hay en el depósito?")
        else:
            await message.channel.send("✅ Reporte de Cierre completado. ¡Gracias!")
            del conversation_state[channel_id]

    # Reportes de batidoras (agrupados por batidora)
    elif tipo == "inicio_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send(f"2. ¿Revisaste las chavetas del eje de batido de la batidora {bat}?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send(f"3. ¿Está adecuadamente engrasado el piñón de la batidora {bat}?")
        elif paso == 3:
            state["paso"] = 4
            await message.channel.send(f"4. ¿Bajaste la protección del rodamiento 6206 de la batidora {bat}?")
        elif paso == 4:
            state["paso"] = 5
            await message.channel.send(f"5. ¿Oíste algún sonido extraño al empezar la batidora {bat}?")
        elif paso == 5:
            state["paso"] = 6
            await message.channel.send(f"6. ¿El nivel de agua sal es óptimo en la batidora {bat}?")
        elif paso == 6:
            state["paso"] = 7
            await message.channel.send(f"7. ¿Se encuentra ajustado el piñón de la batidora {bat}? ¿Tiene algún movimiento o juego?")
        elif paso == 7:
            state["paso"] = 8
            await message.channel.send(f"8. ¿Están completos los dientes del piñón de la batidora {bat}? (envía video)")
        elif paso == 8:
            state["paso"] = 9
            await message.channel.send(f"9. ¿Existe movimiento del tambor de derecha a izquierda en la batidora {bat}?")
        elif paso == 9:
            state["paso"] = 10
            await message.channel.send(f"10. ¿Existe movimiento del tambor de arriba a abajo en la batidora {bat}?")
        else:
            if bat < 5:
                state["batidora"] = bat + 1
                state["paso"] = 1
                await message.channel.send(f"\n**Batidora {bat + 1}**")
                await message.channel.send("1. ¿Revisaste la tensión de las correas?")
            else:
                await message.channel.send("✅ Reporte de Inicio de Batidoras completado. ¡Gracias!")
                del conversation_state[channel_id]

    elif tipo == "funcionamiento_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send(f"2. ¿Está raspando correctamente la batidora {bat}?")
        else:
            if bat < 5:
                state["batidora"] = bat + 1
                state["paso"] = 1
                await message.channel.send(f"\n**Batidora {bat + 1}**")
                await message.channel.send("1. ¿La temperatura del cabezote está por debajo de 50°? ¿Cuál es la temperatura exacta?")
            else:
                await message.channel.send("✅ Reporte de Funcionamiento de Batidoras completado. ¡Gracias!")
                del conversation_state[channel_id]

    elif tipo == "apagado_batidoras":
        if paso == 1:
            state["paso"] = 2
            await message.channel.send(f"2. ¿Revisaste el ajuste del piñón de la batidora {bat}?")
        elif paso == 2:
            state["paso"] = 3
            await message.channel.send(f"3. ¿Subiste la cuchilla y la protección del rodamiento de la batidora {bat}?")
        elif paso == 3:
            state["paso"] = 4
            await message.channel.send(f"4. ¿Revisaste el movimiento en ambos sentidos del eje del tambor de la batidora {bat}?")
        elif paso == 4:
            state["paso"] = 5
            await message.channel.send(f"5. ¿A qué hora se encendió la batidora {bat}? ¿A qué hora se apagó? ¿Cuántas colores se batieron?")
        elif paso == 5:
            state["paso"] = 6
            await message.channel.send(f"6. ¿En la batidora {bat}, cuánto demoró en promedio las batidas trisabor, gourmet, clásica y sundae?")
        else:
            if bat < 5:
                state["batidora"] = bat + 1
                state["paso"] = 1
                await message.channel.send(f"\n**Batidora {bat + 1}**")
                await message.channel.send("1. ¿Revisaste los dientes del piñón? (envía video)")
            else:
                await message.channel.send("✅ Reporte de Apagado de Batidoras completado. ¡Gracias!")
                del conversation_state[channel_id]

client.run(DISCORD_TOKEN)

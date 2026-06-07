import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
print("DEBUG TOKEN:", "PRESENT" if DISCORD_TOKEN else "NONE - VERIFICAR VARIABLES EN RAILWAY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

# ================== CONFIGURACIÓN DE LOS REPORTES ==================
REPORT_TYPES = {
    "cierre": {
        "trigger": "iniciar reporte de cierre",
        "title": "Reporte de Cierre",
        "questions": [
            "1. ¿Qué trabajadores alistaron los pedidos?",
            "2. ¿A qué clientes pertenecen los pedidos que se alistaron? Nómbralos todos.",
            "3. ¿Cómo quedaron los pedidos del día? (cuáles se completaron, cuáles quedaron pendientes, observaciones relevantes y cualquier ajuste para Producción mañana)",
            "4. ¿En qué congeladores quedaron cuáles pedidos?",
            "5. ¿A qué hora se comenzaron a alistar los pedidos y a qué hora terminaron?",
            "6. Tiempos de proceso - Envasado de Bandejas: Hora de inicio y hora de finalización. ¿Qué trabajadores se encargaron?",
            "7. Tiempos de proceso - Envasado de vasitos: Hora de inicio y hora de finalización. ¿Qué trabajadores se encargaron?",
            "8. Tiempos de proceso - Limpieza: Hora de inicio y hora de finalización. ¿Qué trabajadores se encargaron?",
            "9. ¿Limpiaste los tambores de las batidoras? ¿Retiraste la sal de los cabezotes?",
            "10. Inventario de pimpinas de gasoil: Número exacto de pimpinas disponibles al cierre del día",
            "11. Planta Azul - Cantidad de gasoil actual",
            "12. Planta Azul - Nivel de aceite medido",
            "13. Planta Amarilla - Cantidad de gasoil actual",
            "14. Planta Amarilla - Nivel de aceite medido",
            "15. Estado final de la planta: ¿Quedó completamente desactivada (ningún equipo operando sin supervisión)?",
            "16. Protocolo de cierre - Congeladores: ¿Todos los congeladores están encendidos? Si alguno está apagado, ¿cuáles? ¿Todos los congeladores encendidos están bien cerrados? ¿Los motores de los congeladores encendidos están calientes?",
            "17. Protocolo de cierre - Puertas: ¿Cerraste correctamente con candado las puertas de heladeros, del estacionamiento, de la planta y de la salida (incluyendo el doble candado)?",
            "18. Protocolo de cierre - Aire acondicionado: ¿Quedó apagado el aire acondicionado de producción y el de ventas?",
            "19. Protocolo de cierre - Botón rojo: ¿Oprimiste el botón rojo del tablero de batidoras?",
            "20. ¿Pasaste la producción del día completa en la hoja de cálculo correspondiente?"
        ]
    },
    "batidoras_inicio": {
        "trigger": "iniciar reporte de batidoras",
        "title": "Reporte de Inicio de Batidoras",
        "questions": [
            "1. ¿La tensión de las correas está correcta?",
            "2. ¿Las chavetas del eje de batido están en buen estado y bien colocadas?",
            "3. ¿El piñón tiene suficiente grasa?",
            "4. ¿La protección del rodamiento 6206 (abajo) está en buen estado?",
            "5. Al encender las batidoras, ¿se escuchan sonidos extraños o anormales?",
            "6. ¿Hay agua sal en algún lugar donde no debe estar?",
            "7. ¿El piñón está bien ajustado?",
            "8. ¿Los dientes del piñón están en buen estado (sin desgaste ni daño)?",
            "9. ¿El tambor tiene movimiento normal de derecha a izquierda?",
            "10. ¿El tambor tiene movimiento normal de arriba a abajo?"
        ]
    },
    "batidoras_funcionamiento": {
        "trigger": "iniciar reporte de funcionamiento de batidoras",
        "title": "Reporte de Funcionamiento de Batidoras",
        "questions": [
            "1. ¿La temperatura del cabezote se mantuvo por debajo de 50°?",
            "2. ¿Se realizó correctamente el raspado de la cuchilla?",
            "3. ¿Cuáles son los tiempos promedio de cada batidora?"
        ]
    },
    "batidoras_apagado": {
        "trigger": "iniciar reporte de apagado de batidoras",
        "title": "Reporte de Apagado de Batidoras",
        "questions": [
            "1. ¿Los dientes del piñón están en buen estado?",
            "2. ¿El piñón está bien ajustado?",
            "3. ¿La protección del rodamiento (arriba) está en buen estado?",
            "4. ¿El eje del tambor tiene movimiento normal en ambos sentidos?"
        ]
    }
}

active_reports = {}

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    user_id = message.author.id
    content = message.content.strip().lower()

    # Detectar cuál reporte iniciar
    for key, report in REPORT_TYPES.items():
        if content == report["trigger"]:
            if user_id in active_reports:
                await message.channel.send(f"⚠️ {message.author.mention}, ya tienes un reporte en curso.")
                return
            active_reports[user_id] = {
                "step": 0,
                "answers": [],
                "questions": report["questions"],
                "title": report["title"],
                "channel": message.channel
            }
            await message.channel.send(
                f"✅ **{report['title']} iniciado** {message.author.mention}\n"
                f"Te haré {len(report['questions'])} preguntas.\n\n"
                f"**Pregunta 1/{len(report['questions'])}:**\n{report['questions'][0]}"
            )
            return

    if content == "cancelar reporte":
        if user_id in active_reports:
            del active_reports[user_id]
            await message.channel.send(f"❌ Reporte cancelado {message.author.mention}.")
        return

    # Responder preguntas
    if user_id in active_reports:
        session = active_reports[user_id]
        session["answers"].append(message.content)
        session["step"] += 1

        if session["step"] < len(session["questions"]):
            await message.channel.send(f"**Pregunta {session['step']+1}/{len(session['questions'])}:**\n{session['questions'][session['step']]}")
        else:
            await message.channel.send("✅ ¡Reporte completado! Gemini está verificando que todo esté cubierto...")

            qa_text = ""
            for i, q in enumerate(session["questions"]):
                r = session["answers"][i] if i < len(session["answers"]) else "No respondido"
                qa_text += f"Pregunta: {q}\nRespuesta: {r}\n\n"

            prompt = f"""Eres un auditor experto. Revisa el siguiente reporte de {session['title']}.
Respuestas:\n{qa_text}

Responde en español con formato:
**📋 Reporte Oficial**
**🔍 Verificación de Completitud**
- ✅ Todo cubierto
- ❌ Faltantes: [lista clara]"""

            try:
                response = model.generate_content(prompt)
                resultado_ia = response.text
                embed = discord.Embed(
                    title=f"📊 {session['title']} Final - Verificado por Gemini",
                    description=resultado_ia,
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Trabajador: {message.author.display_name}")
                await message.channel.send(embed=embed)
            except Exception as e:
                await message.channel.send(f"❌ Error con Gemini: {e}")
            del active_reports[user_id]

@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user} (usando Gemini)")
    print("✅ Bot listo para usar")
    print("   Comandos disponibles:")
    print("   - iniciar reporte de cierre")
    print("   - iniciar reporte de batidoras")
    print("   - iniciar reporte de funcionamiento de batidoras")
    print("   - iniciar reporte de apagado de batidoras")

client.run(DISCORD_TOKEN)
from __future__ import annotations

import discord
from discord.ext import commands
import os
import traceback
from openai import OpenAI
import json
import re
 
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
    base_url="https://api.x.ai/v1",
)
 
# Estado por canal:
# {
#   "tipo": "encendido_batidoras" | "funcionamiento_batidoras" | "apagado_batidoras",
#   "user_id": int,
#   "batidora": 1..5,
#   "fase": "hora" | "checklist" | "video" | "funcionamiento"
#           | "agua_sal" | "limpieza" | "hora_llegada" | "batidas" | "hora_culminacion",
#   "buffer": str,
#   "answers": {...},
#   "videos_usados": [filename o url, ...],  # evita reutilizar el mismo video en 2 batidoras
#   "hora_global": str | None,
# }
conversation_state = {}
 
NUM_BATIDORAS = 5
# Meta CMI: minutos de reloj (llegada → fin, limpieza incluida) por batida.
META_MIN_POR_BATIDA = 30
 
# ================== TEXTOS ==================
TXT_CHECKLIST_ENCENDIDO = (
    "Revisa lo siguiente **antes de encender**: "
    "(tensión de correas, chavetas del eje de batido, engrase del piñón, "
    "protección del rodamiento 6206, nivel óptimo de agua sal, ajuste del piñón sin juego, "
    "dientes del piñón —si faltan, cuántos—, movimiento del tambor derecha-izquierda y arriba-abajo).\n\n"
    "Reporta el estado. Si la batidora **no funciona / no se enciende / está en reparación**, dilo claro."
)
 
TXT_VIDEO = (
    "Por favor envía un **video del piñón de la batidora {bat}** "
    "(muestra los dientes y el estado general). "
    "No reutilices el video de otra batidora."
)
 
TXT_CHECKLIST_APAGADO = (
    "Al apagar, cuéntame cómo quedó **esta** batidora:\n"
    "• **Dientes del piñón:** ¿están completos o faltan? Si faltan, dime cuántos "
    "(no pongas solo “igual”).\n"
    "• **Ajuste del piñón y grasa:** ¿quedó bien ajustado y engrasado?\n"
    "• **Cuchilla y protección del rodamiento:** ¿cómo quedaron, arriba y abajo?\n"
    "• **Nivel de agua sal:** ¿en qué nivel quedó?\n"
    "• **Hora de encendido y de apagado:** si se apagó y se volvió a prender, anota cada tramo.\n"
    "• **Tiempos aproximados de batida:** normal, gourmet, clásica, batipop o sundae, "
    "lo que hayan usado hoy.\n"
    "Si **no funcionó hoy**, dilo y pasamos a la siguiente."
)
 
TXT_FUNCIONAMIENTO = (
    "Verifica durante el funcionamiento:\n"
    "• Temperatura del cabezote (ideal bajo 50°) y temperatura actual\n"
    "• Si está raspando bien la mezcla\n"
    "Si la batidora no está en uso / no funciona, dilo claro."
)


# Preguntas finales del apagado: una sola vez por reporte, no por batidora.
FASES_CIERRE_APAGADO = (
    "agua_sal",
    "limpieza",
    "hora_llegada",
    "batidas",
    "hora_culminacion",
)

PREGUNTAS_CIERRE = {
    "agua_sal": (
        "💧 **Agua sal.** ¿Le cambiaron el agua sal a alguna batidora hoy? "
        "Responde **sí** o **no**. Si es sí, dime el número de cada batidora y "
        "cuántas veces se la cambiaron (ejemplo: *sí, la 2 una vez y la 4 dos veces*)."
    ),
    "limpieza": (
        "🧽 **Limpieza.** ¿Quedó limpia toda el área de producción, con todos los "
        "enseres que usaron (tobos, paletas, jarras, licuadora, mesones y piso)? "
        "Responde **sí** o **no**. Si algo quedó sin limpiar, dime qué fue."
    ),
    "hora_llegada": (
        "🕖 **Hora de llegada.** ¿A qué hora llegaron hoy a la fábrica para empezar "
        "la producción? (ejemplo: *7:00 am*)"
    ),
    "batidas": (
        "🔢 **Batidas.** ¿Cuántas batidas hicieron hoy en total? "
        "Es el número de pesadas que les pasó Margaret."
    ),
    "hora_culminacion": (
        "🏁 **Hora de culminación.** ¿A qué hora terminaron **todo** el trabajo de "
        "producción de hoy, incluida la limpieza? (ejemplo: *12:40 pm*)"
    ),
}

_SYSTEM_PROMPT_CIERRE = """
Eres validador de reportes de batidoras en una fábrica de helados.
Responde ÚNICAMENTE JSON:
{
  "respuesta_valida": true o false,
  "es_fuera_de_servicio": false,
  "mensaje": null o "texto corto pidiendo SOLO lo que falta",
  "agua_sal_cambios": [{"batidora": 2, "veces": 1}] o [] o null,
  "limpio": true o false o null,
  "pendiente_limpieza": null o "qué quedó sin limpiar",
  "hora": "HH:MM" en 24 horas o null,
  "batidas": entero positivo o null
}

Principios:
1. Evalúa BUFFER + respuesta nueva juntos. Nunca pidas un dato que ya esté en el buffer.
2. Typos y español informal de planta OK.
3. Rechaza solo vacío, ".", o texto irrelevante a la pregunta.
4. No calcules promedios, duraciones ni metas. Solo extrae. El tiempo lo calcula el código.
5. hora: 7am → "07:00", 1:15 pm → "13:15", 12:40 pm → "12:40". Si no hay am/pm, pon la hora en 24h lo mejor que puedas.
6. agua_sal_cambios solo en la fase de agua sal. Si dijeron que no, lista vacía. Si no dijeron las veces, veces=1.
7. En limpieza, limpio=true si quedó limpio. Si no, limpio=false y pendiente_limpieza con lo que nombraron.
8. batidas es un entero positivo. null si no hay número.
9. Llena solo los campos de la fase actual; el resto null.
10. mensaje en español corto, pidiendo únicamente lo que falta.
"""


# ================== TIEMPO, AGUA SAL, LIMPIEZA ==================
def _norm_es(texto: str) -> str:
    t = (texto or "").lower().strip()
    return (
        t.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )


_PALABRAS_NUM = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiun": 21,
    "veintiuno": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
}

_ORDINALES_BAT = {
    "primera": 1,
    "primero": 1,
    "segunda": 2,
    "segundo": 2,
    "tercera": 3,
    "tercero": 3,
    "cuarta": 4,
    "cuarto": 4,
    "quinta": 5,
    "quinto": 5,
}

_PREFIJOS_BAT = {
    "la",
    "las",
    "el",
    "los",
    "batidora",
    "batidoras",
    "maquina",
    "maquinas",
    "numero",
    "num",
    "nro",
    "a",
}

_RE_MER = r"[ap]\s*\.?\s*m\s*\.?(?!\w)"


def _interpretar_mer(raw: str | None) -> str | None:
    if not raw:
        return None
    t = re.sub(r"[\s.]", "", raw.lower())
    if t.startswith("a"):
        return "am"
    if t.startswith("p"):
        return "pm"
    return None


def _aplicar_meridiano(h: int, m: int, mer: str | None) -> int | None:
    if m < 0 or m > 59:
        return None
    if mer is None:
        if 0 <= h <= 23:
            return h * 60 + m
        return None
    if mer == "pm" and 13 <= h <= 23:
        return h * 60 + m
    if not (0 <= h <= 12):
        return None
    if mer == "am":
        if h == 12:
            h = 0
    elif mer == "pm":
        if h < 12:
            h += 12
    else:
        return None
    if not (0 <= h <= 23):
        return None
    return h * 60 + m


def _mer_por_frase(texto_norm: str, h: int) -> str | None:
    if re.search(r"\b(manana|madrugada)\b", texto_norm):
        return "am"
    if re.search(r"\btarde\b", texto_norm):
        return "pm"
    if re.search(r"\bnoche\b", texto_norm):
        return "am" if h == 12 else "pm"
    return None


def _extraer_reloj(texto_norm: str) -> dict | None:
    """Primera hora reconocible. mer es am/pm o None si el texto no lo trae."""
    for m in re.finditer(
        rf"\b(\d{{1,2}})\s*[:.]\s*(\d{{1,2}})\s*({_RE_MER})?",
        texto_norm,
        re.I,
    ):
        h = int(m.group(1))
        minu = int(m.group(2))
        if 0 <= h <= 23 and 0 <= minu <= 59:
            return {"h": h, "m": minu, "mer": _interpretar_mer(m.group(3))}

    for m in re.finditer(
        rf"\b(\d{{1,2}})\s*h\s*(\d{{1,2}})\s*({_RE_MER})?",
        texto_norm,
        re.I,
    ):
        h = int(m.group(1))
        minu = int(m.group(2))
        if 0 <= h <= 23 and 0 <= minu <= 59:
            return {"h": h, "m": minu, "mer": _interpretar_mer(m.group(3))}

    m = re.search(
        rf"\b(\d{{1,2}})\s+y\s+(media|cuarto|\d{{1,2}})\s*({_RE_MER})?",
        texto_norm,
        re.I,
    )
    if m:
        h = int(m.group(1))
        cola = m.group(2)
        if cola == "media":
            minu = 30
        elif cola == "cuarto":
            minu = 15
        else:
            minu = int(cola)
        if 0 <= h <= 23 and 0 <= minu <= 59:
            return {"h": h, "m": minu, "mer": _interpretar_mer(m.group(3))}

    m = re.search(rf"\b(\d{{1,2}})\s*({_RE_MER})", texto_norm, re.I)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return {"h": h, "m": 0, "mer": _interpretar_mer(m.group(2))}

    m = re.search(
        r"\b(?:a\s+las|alas|tipo|las)\s+(\d{1,2})\b",
        texto_norm,
        re.I,
    )
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return {"h": h, "m": 0, "mer": None}

    palabras = "|".join(
        sorted((w for w, v in _PALABRAS_NUM.items() if 1 <= v <= 12), key=len, reverse=True)
    )
    for m in re.finditer(
        rf"\b(?:a\s+las|a\s+la|alas|las|la|tipo)?\s*\b({palabras})"
        rf"(?:\s+y\s+(media|cuarto|\d{{1,2}}))?\b",
        texto_norm,
        re.I,
    ):
        contexto = bool(
            m.group(0).strip() != m.group(1)
            or m.group(2)
            or re.search(r"\b(manana|tarde|noche|madrugada|punto)\b", texto_norm)
            or re.fullmatch(
                rf"(?:a\s+las\s+|a\s+la\s+|las\s+|la\s+|tipo\s+)?{m.group(1)}"
                rf"(?:\s+y\s+(?:media|cuarto|\d{{1,2}}))?(?:\s+horas?)?",
                texto_norm.strip(),
            )
        )
        if not contexto:
            continue
        h = _PALABRAS_NUM[m.group(1)]
        cola = m.group(2)
        minu = 0
        if cola == "media":
            minu = 30
        elif cola == "cuarto":
            minu = 15
        elif cola and str(cola).isdigit():
            minu = int(cola)
        if 0 <= minu <= 59:
            return {"h": h, "m": minu, "mer": None}

    if re.search(r"\b(?:medio\s*dia|mediodia)\b", texto_norm):
        return {"h": 12, "m": 0, "mer": "pm"}
    if re.search(r"\bmedianoche\b", texto_norm):
        return {"h": 12, "m": 0, "mer": "am"}

    nums = [int(n) for n in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", texto_norm)]
    horas = [n for n in nums if 0 <= n <= 23]
    if horas:
        return {"h": horas[0], "m": 0, "mer": None}
    return None


def parsear_hora_minutos(texto: str, llegada_min: int | None = None) -> int | None:
    """
    Minutos desde medianoche.
    7, 7:00, 7am → 07:00. 12:40 pm → 12:40. 1:15 pm → 13:15.
    Si no hay am/pm y la hora queda antes de llegada_min, se asume pm.
    """
    norm = _norm_es(texto)
    if not norm:
        return None
    parsed = _extraer_reloj(norm)
    if not parsed:
        return None
    h, m, mer = parsed["h"], parsed["m"], parsed["mer"]
    mer_frase = _mer_por_frase(norm, h) if mer is None else None
    if mer is None:
        mer = mer_frase
    base = _aplicar_meridiano(h, m, mer)
    if base is None:
        return None
    if (
        parsed["mer"] is None
        and mer_frase is None
        and llegada_min is not None
        and 1 <= h <= 11
        and base < llegada_min
    ):
        return base + 12 * 60
    return base


def minutos_a_hhmm(minutos: int) -> str:
    h, m = divmod(int(minutos) % (24 * 60), 60)
    return f"{h:02d}:{m:02d}"


def formatear_hora_12(minutos: int) -> str:
    h24, m = divmod(int(minutos) % (24 * 60), 60)
    suf = "am" if h24 < 12 else "pm"
    h12 = h24 % 12 or 12
    return f"{h12}:{m:02d} {suf}"


def _fmt_duracion(minutos: float) -> str:
    total = max(0, int(round(minutos)))
    h, m = divmod(total, 60)
    if h and m:
        return f"{h} h {m} min"
    if h:
        return f"{h} h"
    return f"{m} min"


def _fmt_un_decimal(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _fmt_margen(valor: float) -> str:
    texto = _fmt_un_decimal(valor)
    if texto in {"0,0", "-0,0"} and valor > 0:
        return "menos de 0,1"
    return texto


def extraer_entero_positivo(texto: str) -> int | None:
    if texto is None:
        return None
    t = _norm_es(str(texto))
    nums = [int(n) for n in re.findall(r"\d+", t)]
    positivos = [n for n in nums if n > 0]
    if len(positivos) == 1:
        return positivos[0]
    if len(positivos) > 1:
        m = re.search(r"(\d+)\s*batida", t)
        if m and int(m.group(1)) > 0:
            return int(m.group(1))
        return positivos[0]
    for word, val in sorted(_PALABRAS_NUM.items(), key=lambda kv: -len(kv[0])):
        if val > 0 and re.search(rf"\b{word}\b", t):
            return val
    return None


def _como_batidas(valor):
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, int):
        return valor if valor > 0 else None
    if isinstance(valor, float):
        if valor > 0 and abs(valor - round(valor)) < 1e-9:
            return int(round(valor))
        return None
    return extraer_entero_positivo(str(valor))


def calcular_tiempo_por_batida(llegada: str, culminacion: str, batidas) -> dict:
    """Promedio de minutos de reloj por batida. La cuenta es solo Python."""
    t0 = parsear_hora_minutos(str(llegada or ""))
    t1 = parsear_hora_minutos(str(culminacion or ""), llegada_min=t0)
    n = _como_batidas(batidas)
    if t0 is None and t1 is None:
        return {
            "ok": False,
            "mensaje": (
                "No pude calcular el tiempo por batida: "
                "no entendí la hora de llegada ni la de culminación."
            ),
        }
    if t0 is None:
        return {
            "ok": False,
            "mensaje": "No pude calcular el tiempo por batida: no entendí la hora de llegada.",
        }
    if t1 is None:
        return {
            "ok": False,
            "mensaje": "No pude calcular el tiempo por batida: no entendí la hora de culminación.",
        }
    razones = []
    if t1 <= t0:
        razones.append("la hora de culminación no es posterior a la de llegada")
    if n is None:
        razones.append("el número de batidas no es válido")
    if razones:
        return {
            "ok": False,
            "mensaje": "No pude calcular el tiempo por batida: " + " y ".join(razones) + ".",
            "llegada_min": t0,
            "culminacion_min": t1,
            "batidas": n,
        }
    total = t1 - t0
    promedio = total / n
    return {
        "ok": True,
        "llegada_min": t0,
        "culminacion_min": t1,
        "total_min": total,
        "batidas": n,
        "promedio": promedio,
        "cumplio": promedio <= META_MIN_POR_BATIDA + 1e-9,
    }


def formatear_calculo_batidas(calc: dict) -> str:
    if not calc or not calc.get("ok"):
        motivo = (calc or {}).get("mensaje") or "No pude calcular el tiempo por batida."
        return f"📊 **Cálculo de tiempo por batida**\n{motivo}"
    diff = META_MIN_POR_BATIDA - calc["promedio"]
    lineas = [
        "📊 **Cálculo de tiempo por batida**",
        f"• Llegada: {formatear_hora_12(calc['llegada_min'])}",
        f"• Culminación: {formatear_hora_12(calc['culminacion_min'])}",
        f"• Tiempo total: {_fmt_duracion(calc['total_min'])}",
        f"• Batidas: {calc['batidas']}",
        f"• Promedio: **{_fmt_un_decimal(calc['promedio'])} min por batida**",
        f"• Meta (CMI): **{META_MIN_POR_BATIDA} min por batida o menos**",
    ]
    if calc.get("cumplio"):
        lineas.append(
            f"✅ **Cumplieron la meta** ({_fmt_margen(diff)} min por debajo)."
        )
    else:
        lineas.append(
            f"❌ **No cumplieron la meta** ({_fmt_margen(-diff)} min por encima)."
        )
    return "\n".join(lineas)


def _upsert_bat(cambios: list, index_por_bat: dict, bat: int, veces: int) -> int:
    if bat in index_por_bat:
        idx = index_por_bat[bat]
        cambios[idx]["veces"] = veces
        return idx
    index_por_bat[bat] = len(cambios)
    cambios.append({"batidora": bat, "veces": veces})
    return index_por_bat[bat]


def _extraer_cambios_agua_sal(norm: str) -> list:
    tokens = re.findall(r"\d+|[a-z]+", norm)
    cambios = []
    index_por_bat = {}
    last_idx = None
    pending = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if tok in _PREFIJOS_BAT:
            i += 1
            continue
        if nxt in {"vez", "veces"}:
            n = None
            if tok.isdigit():
                n = int(tok)
            elif tok in _PALABRAS_NUM:
                n = _PALABRAS_NUM[tok]
            if n is not None and n > 0:
                if last_idx is not None:
                    cambios[last_idx]["veces"] = n
                else:
                    pending = n
                i += 2
                continue
        if tok in _ORDINALES_BAT:
            bat = _ORDINALES_BAT[tok]
            veces = pending or 1
            pending = None
            last_idx = _upsert_bat(cambios, index_por_bat, bat, veces)
            i += 1
            continue
        if tok.isdigit():
            n = int(tok)
            if 1 <= n <= 5:
                veces = pending or 1
                pending = None
                last_idx = _upsert_bat(cambios, index_por_bat, n, veces)
            i += 1
            continue
        if tok in _PALABRAS_NUM and 1 <= _PALABRAS_NUM[tok] <= 5:
            prev = tokens[i - 1] if i else ""
            if prev in _PREFIJOS_BAT:
                bat = _PALABRAS_NUM[tok]
                veces = pending or 1
                pending = None
                last_idx = _upsert_bat(cambios, index_por_bat, bat, veces)
                i += 1
                continue
        i += 1
    cambios.sort(key=lambda c: c["batidora"])
    return cambios


def parsear_agua_sal(texto: str) -> dict:
    """
    estado ok + cambios (vacío si no cambiaron),
    falta_numeros si dijeron que sí y no hay batidora 1-5,
    invalido si no es sí/no.
    """
    norm = _norm_es(texto or "")
    cambios = _extraer_cambios_agua_sal(norm)
    if cambios:
        return {"estado": "ok", "cambios": cambios}
    es_no = bool(re.search(r"\b(no|nop|nel|nope|ninguna|ninguno|nada)\b", norm))
    es_si = bool(re.search(r"\b(si|sip|sep|simon|afirmativo)\b", norm)) or bool(
        re.search(r"\bcambi", norm)
    )
    if es_no and not es_si:
        return {"estado": "ok", "cambios": []}
    if es_no and es_si:
        if re.match(r"^(no|nop|nel|ninguna|ninguno|nada)\b", norm):
            return {"estado": "ok", "cambios": []}
        return {"estado": "falta_numeros"}
    if es_si:
        return {"estado": "falta_numeros"}
    return {"estado": "invalido"}


def formatear_resumen_agua_sal(cambios: list | None) -> str:
    if not cambios:
        return "💧 Cambios de agua sal: ninguno"
    partes = []
    for c in sorted(cambios, key=lambda x: int(x["batidora"])):
        v = int(c.get("veces") or 1)
        palabra = "vez" if v == 1 else "veces"
        partes.append(f"batidora {c['batidora']} ({v} {palabra})")
    return "💧 Cambios de agua sal: " + ", ".join(partes)


_DETALLE_STOP = {
    "no",
    "nop",
    "nel",
    "nope",
    "si",
    "sip",
    "sep",
    "simon",
    "quedo",
    "queda",
    "quedaron",
    "todo",
    "toda",
    "todos",
    "todas",
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "area",
    "de",
    "del",
    "al",
    "produccion",
    "limpio",
    "limpia",
    "limpios",
    "limpias",
    "se",
    "nos",
    "hoy",
    "muy",
    "bien",
    "ya",
    "esta",
    "eso",
    "que",
    "en",
    "con",
    "por",
    "para",
    "lo",
    "y",
    "o",
    "u",
    "enser",
    "enseres",
    "ok",
    "vale",
    "listo",
    "k",
    "nada",
    "ningun",
    "ninguna",
    "ninguno",
}


def _detalle_limpieza(texto_original: str) -> str:
    lineas = []
    for linea in (texto_original or "").splitlines():
        s = re.sub(
            r"^\s*(sí|si|sip|sep|no|nop|nel)\b[\s,.:;\-]*",
            "",
            linea.strip(),
            flags=re.I,
        ).strip()
        if s:
            lineas.append(s)
    return ", ".join(lineas).strip(" ,.;")


def _tiene_detalle_limpieza(detalle: str) -> bool:
    palabras = re.findall(r"[a-z0-9]+", _norm_es(detalle))
    return any(p not in _DETALLE_STOP and len(p) > 1 for p in palabras)


def evaluar_limpieza(texto: str, ya_pedi_detalle: bool = False) -> dict:
    """
    estado ok (limpio / pendiente), pedir_detalle (un solo re-pregunta)
    o invalido.
    Si ya se pidió el detalle, manda la última línea: un "sí" posterior
    no se queda pegado al "no" del intento anterior.
    """
    lineas = [ln.strip() for ln in (texto or "").splitlines() if ln.strip()]
    if ya_pedi_detalle and len(lineas) > 1:
        texto = lineas[-1]
    norm = _norm_es(texto or "")
    detalle = _detalle_limpieza(texto or "")
    hay_detalle = _tiene_detalle_limpieza(detalle)
    es_si = bool(re.search(r"\b(si|sip|sep|simon|afirmativo)\b", norm))
    if re.search(r"\blimpi[oa]s?\b", norm) and not re.search(
        r"\b(no|sin|falto|falta|suci)\w*", norm
    ):
        es_si = True
    if re.search(r"\b(todo bien|ya quedo|quedo lista|quedo listo)\b", norm):
        es_si = True
    es_no = bool(
        re.search(
            r"\b(no|nop|nel|nope)\b|\bsin limpiar\b|\bsuci[oa]s?\b|\bfalt\w*\b|\bpendiente\b",
            norm,
        )
    )
    if (
        re.search(r"\bnada\b", norm)
        and re.search(r"\b(suci|pendiente)\w*", norm)
        and not hay_detalle
    ):
        return {"estado": "ok", "limpio": True, "pendiente": None}
    if es_si and not es_no:
        return {"estado": "ok", "limpio": True, "pendiente": None}
    if es_no and hay_detalle:
        return {"estado": "ok", "limpio": False, "pendiente": detalle}
    if es_no and not hay_detalle:
        if ya_pedi_detalle:
            return {"estado": "ok", "limpio": False, "pendiente": "no se especificó"}
        return {
            "estado": "pedir_detalle",
            "mensaje": (
                "¿Qué quedó sin limpiar? "
                "(tobos, paletas, jarras, licuadora, mesones o piso)."
            ),
        }
    if ya_pedi_detalle and (texto or "").strip():
        return {
            "estado": "ok",
            "limpio": False,
            "pendiente": detalle if hay_detalle else "no se especificó",
        }
    return {"estado": "invalido"}


def formatear_resumen_limpieza(limpio: bool, pendiente: str | None) -> str:
    if limpio:
        return "🧽 Limpieza: ✅ todo limpio"
    det = (pendiente or "no se especificó").strip()
    return f"🧽 Limpieza: ❌ quedó pendiente: {det}"


def _normalizar_cambios_grok(raw) -> list | None:
    if not isinstance(raw, list):
        return None
    vistos = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            bat = int(item.get("batidora"))
            veces = int(item.get("veces") or 1)
        except (TypeError, ValueError):
            continue
        if 1 <= bat <= 5 and veces > 0:
            vistos[bat] = veces
    if not vistos and raw:
        return None
    return [{"batidora": b, "veces": v} for b, v in sorted(vistos.items())]


def _combinar_decision_cierre(state: dict, texto: str, decision: dict) -> dict:
    """
    Grok valida el lenguaje. Python exige la estructura
    (sí/no, hora, entero) y no vuelve a pedir lo que ya está.
    """
    fase = state.get("fase")
    decision = dict(decision or {})
    decision.setdefault("respuesta_valida", False)
    decision.setdefault("es_fuera_de_servicio", False)
    decision.setdefault("mensaje", None)

    if fase == "agua_sal":
        parsed = parsear_agua_sal(texto)
        if parsed["estado"] == "ok":
            decision["respuesta_valida"] = True
            decision["mensaje"] = None
            decision["_agua"] = parsed
            return decision
        if parsed["estado"] == "falta_numeros":
            decision["respuesta_valida"] = False
            decision["mensaje"] = (
                "Dime el número de cada batidora (del 1 al 5) y cuántas veces "
                "le cambiaron el agua sal. Ejemplo: *la 2 una vez y la 4 dos veces*."
            )
            return decision
        cambios = _normalizar_cambios_grok(decision.get("agua_sal_cambios"))
        if decision.get("respuesta_valida") and cambios:
            decision["mensaje"] = None
            decision["_agua"] = {"estado": "ok", "cambios": cambios}
            return decision
        decision["respuesta_valida"] = False
        if not (decision.get("mensaje") or "").strip():
            decision["mensaje"] = (
                "Responde **sí** o **no**. Si es sí, dime el número de la batidora "
                "(1 a 5) y cuántas veces."
            )
        return decision

    if fase == "limpieza":
        ev = evaluar_limpieza(texto, bool(state.get("limpieza_pido_detalle")))
        if ev["estado"] == "ok":
            decision["respuesta_valida"] = True
            decision["mensaje"] = None
            decision["_limpieza"] = ev
            return decision
        if ev["estado"] == "pedir_detalle":
            decision["respuesta_valida"] = False
            decision["mensaje"] = ev["mensaje"]
            decision["pedir_detalle_limpieza"] = True
            return decision
        limpio = decision.get("limpio")
        if isinstance(limpio, str):
            t = limpio.strip().lower()
            if t in {"true", "si", "sí", "1"}:
                limpio = True
            elif t in {"false", "no", "0"}:
                limpio = False
            else:
                limpio = None
        if decision.get("respuesta_valida") and isinstance(limpio, bool):
            pendiente = (decision.get("pendiente_limpieza") or "").strip()
            if not limpio and not pendiente and not state.get("limpieza_pido_detalle"):
                decision["respuesta_valida"] = False
                decision["mensaje"] = (
                    "¿Qué quedó sin limpiar? "
                    "(tobos, paletas, jarras, licuadora, mesones o piso)."
                )
                decision["pedir_detalle_limpieza"] = True
                return decision
            decision["mensaje"] = None
            decision["_limpieza"] = {
                "estado": "ok",
                "limpio": limpio,
                "pendiente": None if limpio else (pendiente or "no se especificó"),
            }
            return decision
        decision["respuesta_valida"] = False
        if not (decision.get("mensaje") or "").strip():
            decision["mensaje"] = (
                "Responde **sí** o **no**. Si algo quedó sin limpiar, dime qué fue."
            )
        return decision

    if fase in {"hora_llegada", "hora_culminacion"}:
        llegada_min = None
        if fase == "hora_culminacion":
            llegada_min = parsear_hora_minutos(
                (state.get("answers") or {}).get("hora_llegada") or ""
            )
        mins = parsear_hora_minutos(texto, llegada_min=llegada_min)
        if mins is None:
            decision["respuesta_valida"] = False
            if not (decision.get("mensaje") or "").strip():
                ejemplo = "*7:00 am*" if fase == "hora_llegada" else "*12:40 pm*"
                decision["mensaje"] = f"Dime la hora. Ejemplo: {ejemplo}."
            return decision
        decision["respuesta_valida"] = True
        decision["mensaje"] = None
        decision["_minutos"] = mins
        return decision

    if fase == "batidas":
        n = extraer_entero_positivo(texto)
        if n is None:
            gb = decision.get("batidas")
            try:
                if isinstance(gb, bool) or gb is None:
                    gb = None
                else:
                    gb = int(gb)
            except (TypeError, ValueError):
                gb = None
            if gb and gb > 0 and re.search(rf"\b{gb}\b", _norm_es(texto)):
                n = gb
        if n is None or n <= 0:
            decision["respuesta_valida"] = False
            if not (decision.get("mensaje") or "").strip():
                decision["mensaje"] = (
                    "Dime cuántas batidas hicieron hoy, con un número "
                    "(las pesadas que pasó Margaret)."
                )
            return decision
        decision["respuesta_valida"] = True
        decision["mensaje"] = None
        decision["_batidas"] = n
        return decision

    return decision


# ================== HELPERS ==================
def _vacio_o_basura(texto: str, tiene_media: bool) -> bool:
    t = (texto or "").strip()
    if tiene_media:
        return False
    if not t:
        return True
    return t.lower() in {".", "..", "...", "ok", "vale", "listo", "k", "ya", "-", "—"}
 
 
def _parece_cancelar(content_lower: str) -> bool:
    patrones = [
        r"^cancelar(\s+reporte)?$",
        r"^cancel(\s+report)?$",
        r"^cancela(r)?$",
        r"^canelar(\s+reporte)?$",
        r"^reporte\s+cancelado$",
        r"^detener(\s+reporte)?$",
    ]
    return any(re.match(p, content_lower) for p in patrones)
 
 
def _tiene_media(message: discord.Message) -> bool:
    for att in message.attachments:
        ct = (att.content_type or "").lower()
        name = (att.filename or "").lower()
        if ct.startswith("video/") or ct.startswith("image/"):
            return True
        if name.endswith((".mp4", ".mov", ".webm", ".mkv", ".avi", ".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return True
    return False
 
 
def _media_ids(message: discord.Message) -> list:
    """Identificadores estables del adjunto para detectar reuso."""
    ids = []
    for att in message.attachments:
        # filename + size es un proxy razonable; url cambia por expiry
        ids.append(f"{att.filename}|{att.size}")
    return ids
 
 
def _msg_inicio(tipo: str, user: discord.abc.User) -> str:
    base_cancel = (
        f"_Solo {user.display_name} puede responder este reporte._\n"
        f"_Escribe **cancelar** o **cancelar reporte** para detenerlo._"
    )
    if tipo == "encendido_batidoras":
        return (
            f"**Reporte de Encendido de Batidoras iniciado** por {user.mention}\n\n"
            f"¿A qué hora se encendieron las batidoras?\n"
            f"(Si alguna no se enciende, lo dirás batidora por batidora.)\n\n"
            f"{base_cancel}"
        )
    if tipo == "funcionamiento_batidoras":
        return (
            f"**Reporte de Funcionamiento de Batidoras iniciado** por {user.mention}\n\n"
            f"**Batidora 1**\n\n{TXT_FUNCIONAMIENTO}\n\n{base_cancel}"
        )
    return (
        f"**Reporte de Apagado de Batidoras iniciado** por {user.mention}\n\n"
        f"**Batidora 1**\n\n{TXT_CHECKLIST_APAGADO}\n\n{base_cancel}"
    )
 
 
def _estado_inicial(tipo: str, user_id: int) -> dict:
    if tipo == "encendido_batidoras":
        return {
            "tipo": tipo,
            "user_id": user_id,
            "fase": "hora",
            "batidora": 1,
            "buffer": "",
            "answers": {},
            "videos_usados": [],
            "hora_global": None,
        }
    if tipo == "funcionamiento_batidoras":
        return {
            "tipo": tipo,
            "user_id": user_id,
            "fase": "funcionamiento",
            "batidora": 1,
            "buffer": "",
            "answers": {},
            "videos_usados": [],
            "hora_global": None,
        }
    # apagado
    return {
        "tipo": tipo,
        "user_id": user_id,
        "fase": "checklist",
        "batidora": 1,
        "buffer": "",
        "answers": {},
        "videos_usados": [],
        "hora_global": None,
    }
 
 
async def _iniciar(channel, user: discord.abc.User, tipo: str):
    channel_id = str(channel.id)
    if channel_id in conversation_state:
        dueño = conversation_state[channel_id]["user_id"]
        await channel.send(
            f"Ya hay un reporte de batidoras en curso (iniciado por <@{dueño}>). "
            f"Termínenlo o escriban **cancelar reporte**."
        )
        return
    conversation_state[channel_id] = _estado_inicial(tipo, user.id)
    await channel.send(_msg_inicio(tipo, user))
 
 
def _texto_checklist_para(state: dict) -> str:
    bat = state["batidora"]
    if state["tipo"] == "encendido_batidoras":
        return f"**Batidora {bat}**\n\n{TXT_CHECKLIST_ENCENDIDO}"
    if state["tipo"] == "apagado_batidoras":
        return f"**Batidora {bat}**\n\n{TXT_CHECKLIST_APAGADO}"
    return f"**Batidora {bat}**\n\n{TXT_FUNCIONAMIENTO}"
 
 
async def _ir_siguiente_batidora_o_fin(message: discord.Message, state: dict):
    bat = state["batidora"]
    tipo = state["tipo"]
 
    if bat < NUM_BATIDORAS:
        state["batidora"] = bat + 1
        state["buffer"] = ""
        if tipo == "funcionamiento_batidoras":
            state["fase"] = "funcionamiento"
            await message.channel.send(
                f"**Batidora {state['batidora']}**\n\n{TXT_FUNCIONAMIENTO}"
            )
        else:
            state["fase"] = "checklist"
            await message.channel.send(_texto_checklist_para(state))
        return
 
    if tipo == "apagado_batidoras" and state.get("fase") not in FASES_CIERRE_APAGADO:
        state["buffer"] = ""
        state["fase"] = "agua_sal"
        await message.channel.send(PREGUNTAS_CIERRE["agua_sal"])
        return

    await _finalizar_reporte(message, state)


async def _finalizar_reporte(message: discord.Message, state: dict):
    channel_id = str(message.channel.id)
    tipo = state["tipo"]
    nombres = {
        "encendido_batidoras": "Encendido de Batidoras",
        "apagado_batidoras": "Apagado de Batidoras",
        "funcionamiento_batidoras": "Funcionamiento de Batidoras",
    }
    await message.channel.send(
        f"✅ **Reporte de {nombres.get(tipo, 'Batidoras')} completado.** ¡Gracias!\n"
        f"_Respondido por <@{state['user_id']}>._"
    )
    print(f"[BATIDORAS OK] tipo={tipo} answers={json.dumps(state['answers'], ensure_ascii=False)}")
    del conversation_state[channel_id]


async def _cerrar_apagado(message: discord.Message, state: dict):
    calc = calcular_tiempo_por_batida(
        state["answers"].get("hora_llegada") or "",
        state["answers"].get("hora_culminacion") or "",
        state["answers"].get("batidas"),
    )
    guardado = {"ok": bool(calc.get("ok"))}
    if calc.get("ok"):
        guardado.update(
            {
                "llegada_24h": minutos_a_hhmm(calc["llegada_min"]),
                "culminacion_24h": minutos_a_hhmm(calc["culminacion_min"]),
                "total_min": calc["total_min"],
                "batidas": calc["batidas"],
                "promedio_min": round(calc["promedio"], 1),
                "cumplio": bool(calc["cumplio"]),
            }
        )
    else:
        guardado["motivo"] = calc.get("mensaje")
    state["answers"]["calculo_tiempo"] = guardado
    await message.channel.send(formatear_calculo_batidas(calc))
    await message.channel.send(
        formatear_resumen_agua_sal(state["answers"].get("agua_sal_cambios") or [])
        + "\n"
        + formatear_resumen_limpieza(
            bool(state["answers"].get("limpio")),
            state["answers"].get("limpieza_pendiente"),
        )
    )
    await _finalizar_reporte(message, state)


async def _avanzar_cierre_apagado(
    message: discord.Message,
    state: dict,
    buffer_completo: str,
    decision: dict,
):
    fase = state["fase"]
    if fase == "agua_sal":
        agua = decision.get("_agua") or parsear_agua_sal(buffer_completo)
        state["answers"]["agua_sal"] = buffer_completo
        state["answers"]["agua_sal_cambios"] = agua.get("cambios") or []
    elif fase == "limpieza":
        ev = decision.get("_limpieza") or evaluar_limpieza(buffer_completo, True)
        state["answers"]["limpieza"] = buffer_completo
        state["answers"]["limpio"] = bool(ev.get("limpio"))
        state["answers"]["limpieza_pendiente"] = ev.get("pendiente")
    elif fase == "hora_llegada":
        mins = decision.get("_minutos")
        if mins is None:
            mins = parsear_hora_minutos(buffer_completo)
        state["answers"]["hora_llegada"] = buffer_completo
        state["answers"]["hora_llegada_24h"] = (
            minutos_a_hhmm(mins) if mins is not None else None
        )
    elif fase == "batidas":
        n = decision.get("_batidas")
        if n is None:
            n = extraer_entero_positivo(buffer_completo)
        state["answers"]["batidas_texto"] = buffer_completo
        state["answers"]["batidas"] = n
    elif fase == "hora_culminacion":
        llegada_min = parsear_hora_minutos(state["answers"].get("hora_llegada") or "")
        mins = decision.get("_minutos")
        if mins is None:
            mins = parsear_hora_minutos(buffer_completo, llegada_min=llegada_min)
        state["answers"]["hora_culminacion"] = buffer_completo
        state["answers"]["hora_culminacion_24h"] = (
            minutos_a_hhmm(mins) if mins is not None else None
        )
        state["buffer"] = ""
        await _cerrar_apagado(message, state)
        return

    state["buffer"] = ""
    orden = list(FASES_CIERRE_APAGADO)
    state["fase"] = orden[orden.index(fase) + 1]
    await message.channel.send(PREGUNTAS_CIERRE[state["fase"]])
 
 
# ================== SLASH COMMANDS ==================
@bot.tree.command(
    name="reporte-encendido-batidoras",
    description="Inicia el Reporte de Encendido de Batidoras",
)
async def slash_encendido(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await _iniciar(interaction.channel, interaction.user, "encendido_batidoras")
    try:
        await interaction.followup.send("Reporte de encendido iniciado en el canal.", ephemeral=True)
    except Exception:
        pass
 
 
@bot.tree.command(
    name="reporte-funcionamiento-batidoras",
    description="Inicia el Reporte de Funcionamiento de Batidoras",
)
async def slash_funcionamiento(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await _iniciar(interaction.channel, interaction.user, "funcionamiento_batidoras")
    try:
        await interaction.followup.send("Reporte de funcionamiento iniciado en el canal.", ephemeral=True)
    except Exception:
        pass
 
 
@bot.tree.command(
    name="reporte-apagado-batidoras",
    description="Inicia el Reporte de Apagado de Batidoras",
)
async def slash_apagado(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await _iniciar(interaction.channel, interaction.user, "apagado_batidoras")
    try:
        await interaction.followup.send("Reporte de apagado iniciado en el canal.", ephemeral=True)
    except Exception:
        pass
 
 
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} slash commands sincronizados")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")
        traceback.print_exc()
 
 
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
 
    content_lower = (message.content or "").strip().lower()
    channel_id = str(message.channel.id)
    state = conversation_state.get(channel_id)
 
    # Cancelar
    if state and _parece_cancelar(content_lower):
        es_dueño = message.author.id == state["user_id"]
        if es_dueño or content_lower in {"cancelar reporte", "reporte cancelado", "canelar reporte"}:
            del conversation_state[channel_id]
            await message.channel.send("✅ Reporte de batidoras cancelado.")
        return
 
    # Inicio por texto
    inicios = {
        "reporte de encendido de batidoras": "encendido_batidoras",
        "iniciar reporte de encendido de batidoras": "encendido_batidoras",
        "reporte de funcionamiento de batidoras": "funcionamiento_batidoras",
        "iniciar reporte de funcionamiento de batidoras": "funcionamiento_batidoras",
        "reporte de apagado de batidoras": "apagado_batidoras",
        "iniciar reporte de apagado de batidoras": "apagado_batidoras",
    }
    if content_lower in inicios:
        await _iniciar(message.channel, message.author, inicios[content_lower])
        return
 
    if not state:
        return
 
    # Solo el dueño avanza el reporte
    if message.author.id != state["user_id"]:
        return
 
    await manejar_respuesta(message)
 
 
# ================== GROK ==================
async def consultar_grok(
    state: dict,
    respuesta_nueva: str,
    tiene_media: bool,
) -> dict:
    """
    Devuelve:
      respuesta_valida: bool
      es_fuera_de_servicio: bool   # no funciona / reparación / no se usó
      mensaje: str | null
      En las fases finales del apagado, también agua_sal_cambios, limpio,
      pendiente_limpieza, hora (HH:MM) y batidas. El promedio no lo calcula el modelo.
    """
    tipo = state["tipo"]
    fase = state["fase"]
    bat = state["batidora"]
    buffer = state.get("buffer") or ""
 
    if fase == "hora":
        contexto_pregunta = (
            "Pregunta: ¿A qué hora se encendieron las batidoras?\n"
            "Válido: una hora o varias (ej. '7:20', 'La 3 a las 7:00 las demás a las 7:20').\n"
            "Inválido: punto, vacío, sin ninguna hora."
        )
    elif fase == "video":
        contexto_pregunta = (
            f"Fase: VIDEO del piñón de la batidora {bat}.\n"
            "Si hay video/imagen adjunta → válido.\n"
            "Si solo texto sin media → inválido. Mensaje: pide el video del piñón.\n"
            "No evalúes checklist aquí."
        )
    elif fase == "funcionamiento":
        contexto_pregunta = f"""
Fase: FUNCIONAMIENTO batidora {bat}.
Pide: temperatura del cabezote + si raspa bien la mezcla.
- Válido: temp (número o rango) + raspando sí/no o equivalente.
- Válido fuera de servicio: "no funciona", "no está en uso", "apagada", "en reparación".
- NO exijas copiar la pregunta. NO digas "confirma el encendido".
- Español de planta informal OK.
"""
    elif fase == "agua_sal":
        contexto_pregunta = """
Fase: AGUA SAL, una sola vez en todo el reporte (NO por batidora).
Pregunta: ¿Le cambiaron el agua sal a alguna batidora hoy?
Válido:
- "no", "ninguna", "no se cambió" → respuesta_valida true y agua_sal_cambios [].
- "sí" más al menos una batidora del 1 al 5.
  Ejemplo: "sí, la 2 una vez y la 4 dos veces"
  → agua_sal_cambios [{"batidora": 2, "veces": 1}, {"batidora": 4, "veces": 2}].
  Si no dicen las veces, veces=1.
Inválido:
- vacío, ".", irrelevante.
- "sí" sin ningún número de batidora. En mensaje pide SOLO los números (1 a 5) y las veces.
  No vuelvas a pedir el sí/no.
NO pidas datos que ya estén en el buffer. Español informal y typos OK.
hora=null, batidas=null, limpio=null.
"""
    elif fase == "limpieza":
        ya_detalle = bool(state.get("limpieza_pido_detalle"))
        contexto_pregunta = f"""
Fase: LIMPIEZA del área de producción, una sola vez (NO por batidora).
Válido: "sí" / "todo limpio" → limpio true, pendiente_limpieza null.
Válido: "no" y qué quedó sin limpiar → limpio false y pendiente_limpieza con ese texto.
Si dijeron "no" sin decir qué, y ya_se_pidio_el_detalle es false: respuesta_valida false
y el mensaje pide SOLO qué quedó (tobos, paletas, jarras, licuadora, mesones o piso).
Si ya_se_pidio_el_detalle es true: acepta esta respuesta aunque no detallen. limpio false.
ya_se_pidio_el_detalle: {ya_detalle}
Inválido: vacío, ".", irrelevante.
No pidas de nuevo lo que ya está en el buffer. Español informal OK.
"""
    elif fase == "hora_llegada":
        contexto_pregunta = """
Fase: HORA DE LLEGADA a la fábrica, una sola vez.
Válido si hay una hora (7, 7:00, 7am, 7:00 am, 7 de la mañana).
hora en 24h "HH:MM" (7am → "07:00", 1:15 pm → "13:15").
Inválido: sin ninguna hora, vacío, ".", irrelevante.
No calcules duraciones. Español informal OK.
"""
    elif fase == "batidas":
        contexto_pregunta = """
Fase: BATIDAS totales del día (pesadas que pasó Margaret). Una sola vez.
Válido si hay un entero positivo: "12", "doce", "hicimos 12".
batidas = ese entero.
Inválido: sin número, cero, negativo, vacío, ".", irrelevante.
No calcules promedios. Español informal OK.
"""
    elif fase == "hora_culminacion":
        llegada_txt = (state.get("answers") or {}).get("hora_llegada") or ""
        llegada_24 = (state.get("answers") or {}).get("hora_llegada_24h") or ""
        contexto_pregunta = f"""
Fase: HORA DE CULMINACIÓN de todo el trabajo, incluida la limpieza. Una sola vez.
Válido si hay una hora.
hora en 24h "HH:MM".
Llegada ya reportada: "{llegada_txt}" ({llegada_24}).
Si la hora NO trae am/pm y quedaría antes de la llegada, asume pm
(1:15 con llegada 07:00 → "13:15"; 12:40 con llegada 07:00 → "12:40").
NO calcules el promedio ni la duración: solo extrae la hora.
Inválido: sin hora, vacío, ".", irrelevante.
Español informal OK. No pidas la hora si ya está en el buffer.
"""
    elif tipo == "encendido_batidoras":
        contexto_pregunta = f"""
Fase: CHECKLIST DE ENCENDIDO batidora {bat}.
Pide estado de: correas, chaveta, grasa/piñón, protección rodamiento, agua sal, ajuste piñón, dientes (completos o cuántos faltan), movimiento tambor.
REGLAS:
- NO es una pregunta de "¿está encendida?". Es revisión de estado ANTES/AL encender.
- NUNCA digas "te falta confirmar el encendido".
- Respuesta natural con varios puntos del checklist ES válida aunque no cubra el 100% palabra por palabra.
- Si reporta problemas (falta diente, grasa, correa floja) SIGUE siendo válida: es información útil, no un rechazo.
- Válido fuera de servicio: "no está en funcionamiento", "en reparación", "no se enciende", "batidora X no trabaja".
- "Todo bien" corto es débil: si es muy corto sin detalle, pide al menos 2-3 puntos del checklist O que diga si no funciona.
- Si el buffer + respuesta nueva ya tienen info suficiente de estado → válido.
- Inválido: solo ".", vacío, irrelevante.
- Sé razonable, no legalista.
"""
    else:  # apagado checklist
        contexto_pregunta = f"""
Fase: CHECKLIST DE APAGADO batidora {bat}.
Pide: dientes del piñón (completos o cuántos faltan, NO solo "igual"), ajuste del piñón y grasa, cuchilla y protección del rodamiento, nivel de agua sal (solo el nivel; si la cambiaron se pregunta al final del reporte, no aquí), hora de encendido y de apagado con tramos si se apagó y se prendió, tiempos aproximados de batida.
REGLAS:
- Acepta respuestas de planta incompletas al 100% si traen lo esencial: estado del piñón/protección + horas + algún tiempo de batida.
- "Dientes igual" es aceptable si además trae horas y protección; si puedes, en mensaje (solo si inválida) pide especificar si faltan dientes.
- Válido fuera de servicio: "no funcionó", "no está en funcionamiento", "no se usó hoy".
- NO exijas cantidad exacta de "colores batidos" si no la dieron pero sí tiempos y horas.
- NO pidas si cambiaron el agua sal en esta fase.
- NO entres en bucle pidiendo lo que ya está en el buffer.
- Inválido: solo "." o basura.
"""
 
    system_prompt = """
Eres validador de reportes de batidoras en una fábrica de helados.
Responde ÚNICAMENTE JSON:
{
  "respuesta_valida": true o false,
  "es_fuera_de_servicio": true o false,
  "mensaje": null o "texto corto pidiendo SOLO lo que falta"
}
 
Principios:
1. Evalúa si la INFORMACIÓN esencial está (buffer + respuesta nueva), no si la frase es perfecta.
2. Typos y español informal OK ("se pagado", "hechar grasa", "iso").
3. es_fuera_de_servicio=true si dice que no funciona / reparación / no se usó / no se encendió.
4. Si es_fuera_de_servicio y se entiende → respuesta_valida=true.
5. Nunca uses el mensaje genérico "Tu mensaje está incompleto" sin decir qué falta.
6. Nunca pidas "confirmar el encendido" en la fase de checklist de estado.
7. temperature-level: sé práctico para operarios de planta, no un auditor legal.
 
Errores reales que DEBES evitar:
- Rechazar un checklist detallado (correas, grasa, dientes, agua sal) como "incompleto".
- Aceptar un punto "." como respuesta.
- Confundir checklist de estado con confirmación de encendido.
- Pedir video cuando dijeron que la máquina no funciona (eso lo maneja el código con es_fuera_de_servicio).
- Exigir copiar toda la lista del prompt.
"""
    if fase in FASES_CIERRE_APAGADO:
        system_prompt = _SYSTEM_PROMPT_CIERRE
 
    user_content = f"""
Tipo de reporte: {tipo}
Fase actual: {fase}
Batidora actual: {bat}
Tiene_media_en_este_mensaje: {tiene_media}
 
{contexto_pregunta}
 
BUFFER de la misma fase (intentos previos):
\"\"\"{buffer or "(vacío)"}\"\"\"
 
Respuesta NUEVA:
\"\"\"{respuesta_nueva}\"\"\"
 
Evalúa BUFFER + respuesta nueva juntos.
"""
 
    try:
        response = client.chat.completions.create(
            model="grok-4-1-fast",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        limpio = data.get("limpio")
        if isinstance(limpio, str):
            tlim = limpio.strip().lower()
            if tlim in {"true", "si", "sí", "1"}:
                limpio = True
            elif tlim in {"false", "no", "0"}:
                limpio = False
            else:
                limpio = None
        elif not isinstance(limpio, bool):
            limpio = None
        batidas_n = data.get("batidas")
        if isinstance(batidas_n, bool) or batidas_n is None:
            batidas_n = None
        else:
            try:
                batidas_n = int(batidas_n)
            except (TypeError, ValueError):
                batidas_n = None
        return {
            "respuesta_valida": bool(data.get("respuesta_valida", False)),
            "es_fuera_de_servicio": bool(data.get("es_fuera_de_servicio", False)),
            "mensaje": data.get("mensaje"),
            "agua_sal_cambios": data.get("agua_sal_cambios"),
            "limpio": limpio,
            "pendiente_limpieza": data.get("pendiente_limpieza"),
            "hora": data.get("hora"),
            "batidas": batidas_n,
        }
    except Exception as e:
        print(f"Error al consultar Grok: {e}")
        traceback.print_exc()
        if _vacio_o_basura(respuesta_nueva, tiene_media):
            return {
                "respuesta_valida": False,
                "es_fuera_de_servicio": False,
                "mensaje": "Escribe la respuesta con datos (no uses solo un punto).",
            }
        # Fail-open con texto real
        return {
            "respuesta_valida": True,
            "es_fuera_de_servicio": bool(
                re.search(
                    r"no\s+(est[aá]|funciona|se\s+us|enciend)|reparaci[oó]n|fuera\s+de\s+servicio",
                    respuesta_nueva,
                    re.I,
                )
            ),
            "mensaje": None,
        }
 
 
# ================== MANEJO ==================
async def manejar_respuesta(message: discord.Message):
    channel_id = str(message.channel.id)
    state = conversation_state.get(channel_id)
    if not state:
        return
 
    texto = (message.content or "").strip()
    tiene_media = _tiene_media(message)
    fase = state["fase"]
    bat = state["batidora"]
    tipo = state["tipo"]
 
    # ---- FASE VIDEO: exigir media de verdad ----
    if fase == "video":
        if not tiene_media:
            if _vacio_o_basura(texto, False):
                await message.channel.send(
                    f"Necesito el **video del piñón de la batidora {bat}**, no un punto. "
                    f"Graba y envíalo aquí."
                )
            else:
                # Texto sin video: no avanzar
                await message.channel.send(
                    f"Anota eso, pero aún falta el **video del piñón de la batidora {bat}**. Envíalo por favor."
                )
                if texto:
                    state["buffer"] = ((state.get("buffer") or "") + "\n" + texto).strip()
            return
 
        # Detectar reuso del mismo archivo
        ids = _media_ids(message)
        reusado = [i for i in ids if i in state.get("videos_usados", [])]
        if reusado:
            await message.channel.send(
                f"⚠️ Ese video/archivo ya se usó en otra batidora. "
                f"Envía un **video nuevo del piñón de la batidora {bat}**."
            )
            return
 
        # Video OK
        try:
            await message.add_reaction("✅")
        except Exception:
            pass
 
        key = f"{tipo}_bat{bat}_video"
        state["answers"][key] = {
            "archivos": ids,
            "nota": texto or state.get("buffer") or "",
        }
        state["videos_usados"].extend(ids)
        state["buffer"] = ""
        await _ir_siguiente_batidora_o_fin(message, state)
        return
 
    # ---- Prefiltro basura (no video) ----
    if _vacio_o_basura(texto, tiene_media):
        # En limpieza, el segundo intento cuenta aunque sea corto ("ok", "no").
        segunda_limpieza = (
            fase == "limpieza"
            and state.get("limpieza_pido_detalle")
            and (texto or "").strip().lower() not in {"", ".", "..", "...", "-", "—"}
        )
        if not segunda_limpieza:
            if fase in FASES_CIERRE_APAGADO:
                await message.channel.send(
                    "Escribe la respuesta con datos (no uses solo un punto)."
                )
            else:
                await message.channel.send(
                    "Escribe la respuesta con datos (no uses solo un punto). "
                    "Si la batidora no funciona, dilo con palabras: *no está en funcionamiento*."
                )
            return

    # Media en fase checklist no sustituye el texto del checklist
    # (el video se pide después). Si mandan solo media en checklist, avisar.
    if tiene_media and not texto and fase in {"checklist", "hora", "funcionamiento"}:
        await message.channel.send(
            "Primero escribe el **estado/datos** en texto. "
            "El video del piñón te lo pediré en el siguiente paso (si la máquina está en uso)."
        )
        return

    if tiene_media and not texto and fase in FASES_CIERRE_APAGADO:
        await message.channel.send(
            "Escribe la respuesta en texto (sí o no, la hora o el número)."
        )
        return
 
    respuesta_para_ia = texto
    if tiene_media:
        nombres = ", ".join(a.filename for a in message.attachments)
        respuesta_para_ia = f"{texto}\n[Adjuntos: {nombres}]".strip()
 
    buffer_prev = state.get("buffer") or ""
    buffer_completo = (buffer_prev + "\n" + texto).strip() if buffer_prev else texto
 
    decision = await consultar_grok(state, respuesta_para_ia, tiene_media)

    if fase in FASES_CIERRE_APAGADO:
        decision = _combinar_decision_cierre(state, buffer_completo, decision)

    if not decision.get("respuesta_valida", False):
        state["buffer"] = buffer_completo
        if decision.get("pedir_detalle_limpieza"):
            state["limpieza_pido_detalle"] = True
        msg = decision.get("mensaje") or "Falta un dato. Completa solo lo que falta."
        # Neutralizar genéricos tóxicos
        if msg.strip().lower() in {
            "tu mensaje está incompleto.",
            "tu mensaje está incompleto",
            "tu respuesta está incompleta. di exactamente lo que se te pidió.",
            "responde completo lo que se te preguntó.",
        }:
            msg = "Me falta un dato concreto. Complétalo en un mensaje más (o di si la batidora no funciona)."
        await message.channel.send(msg)
        return
 
    # ===== Válida =====
    try:
        await message.add_reaction("✅")
    except Exception:
        pass
 
    fuera = decision.get("es_fuera_de_servicio", False)

    if fase in FASES_CIERRE_APAGADO:
        await _avanzar_cierre_apagado(message, state, buffer_completo, decision)
        return

    # --- Hora global (solo encendido) ---
    if fase == "hora":
        state["hora_global"] = buffer_completo
        state["answers"]["hora_encendido"] = buffer_completo
        state["buffer"] = ""
        state["fase"] = "checklist"
        state["batidora"] = 1
        await message.channel.send(_texto_checklist_para(state))
        return
 
    # --- Funcionamiento ---
    if fase == "funcionamiento":
        state["answers"][f"func_bat{bat}"] = buffer_completo
        state["buffer"] = ""
        await _ir_siguiente_batidora_o_fin(message, state)
        return
 
    # --- Checklist encendido / apagado ---
    if fase == "checklist":
        state["answers"][f"{tipo}_bat{bat}_checklist"] = buffer_completo
        state["buffer"] = ""
 
        if fuera:
            # Sin video si no funciona / no se usó
            state["answers"][f"{tipo}_bat{bat}_video"] = "N/A — fuera de servicio / no usada"
            await message.channel.send(
                f"Batidora {bat} marcada como **no en uso / fuera de servicio**. Siguiente…"
            )
            await _ir_siguiente_batidora_o_fin(message, state)
            return
 
        # Siempre pedir video si está en uso (regla fija — corrige el bug de saltarse videos)
        state["fase"] = "video"
        await message.channel.send(TXT_VIDEO.format(bat=bat))
        return
 
 
# ================== INICIO ==================
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

#!/usr/bin/env python3
"""
Audio de las notas (TTS neuronal) — voz humana pregenerada.
===========================================================
Genera un MP3 por artículo con una voz neuronal y lo cachea en content/audio/.
El sitio lo reproduce cuando existe; si no, cae en la voz del navegador
(Web Speech, ya con selección de la mejor voz disponible). Degrada con gracia.

ESTADO: listo para conectar. Se activa SOLO si defines AUDIO_TTS=1 y la clave
del proveedor. Por defecto no genera nada (no cuesta, no rompe el build).

Proveedor por defecto: OpenAI TTS (gpt-4o-mini-tts). Para usar otro (Amazon
Polly, ElevenLabs, Google), reemplaza `generar_tts()` manteniendo la firma
(recibe texto, devuelve bytes MP3).

Variables:
  AUDIO_TTS=1              activa la generación (por defecto apagado)
  OPENAI_API_KEY=...       clave del proveedor
  TTS_MODEL=gpt-4o-mini-tts
  TTS_VOICE=nova           voz (alloy, echo, fable, onyx, nova, shimmer, ...)
"""

import os

AUDIO_TTS = os.environ.get("AUDIO_TTS", "") == "1"
TTS_MODEL = os.environ.get("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.environ.get("TTS_VOICE", "nova")
_LIMITE = 3800  # límite seguro por llamada (OpenAI TTS admite ~4096 caracteres)


def _texto_para_audio(a):
    partes = [a["title"]]
    if a.get("subtitle"):
        partes.append(a["subtitle"])
    partes.extend(a.get("body", []))
    return "\n\n".join(partes)


def _trocear(texto, limite=_LIMITE):
    """Parte el texto en trozos <= limite respetando párrafos."""
    trozos, actual = [], ""
    for parrafo in texto.split("\n\n"):
        if len(actual) + len(parrafo) + 2 <= limite:
            actual += (("\n\n" + parrafo) if actual else parrafo)
        else:
            if actual:
                trozos.append(actual)
            actual = parrafo[:limite]
    if actual:
        trozos.append(actual)
    return trozos or [texto[:limite]]


def generar_tts(texto):
    """Genera el MP3 con OpenAI TTS y devuelve los bytes. Lanza si falla."""
    from openai import OpenAI  # import diferido
    client = OpenAI()
    audio = b""
    for trozo in _trocear(texto):
        r = client.audio.speech.create(
            model=TTS_MODEL, voice=TTS_VOICE, input=trozo,
            response_format="mp3")
        audio += r.content  # los frames MP3 se concatenan sin problema
    return audio


def build_audio(article, audiodir, basename):
    """Devuelve el nombre del MP3 (cacheado o generado) o None.

    Prioridad:
      1. Si ya existe un MP3 cacheado -> se reutiliza (no se vuelve a generar).
      2. Si AUDIO_TTS=1 y hay clave -> genera la voz neuronal.
      3. En cualquier otro caso -> None (el sitio usa la voz del navegador).
    """
    mp3, path = basename + ".mp3", os.path.join(audiodir, basename + ".mp3")
    if os.path.exists(path):
        return mp3
    if AUDIO_TTS and os.environ.get("OPENAI_API_KEY"):
        try:
            os.makedirs(audiodir, exist_ok=True)
            data = generar_tts(_texto_para_audio(article))
            with open(path, "wb") as f:
                f.write(data)
            print(f"  audio TTS generado: {mp3}")
            return mp3
        except Exception as e:  # noqa: BLE001
            print(f"  aviso: falló el TTS ({e}); uso la voz del navegador.")
    return None


def build_briefing(texto, audiodir, basename):
    """Briefing de audio del día (podcast corto del resumen). Devuelve el nombre
    del MP3 (cacheado o generado) o None.

    Prioridad:
      1. Si ya existe el MP3 del día -> se reutiliza (no se regenera).
      2. Si AUDIO_TTS=1 y hay clave -> genera la voz neuronal del resumen.
      3. En cualquier otro caso -> None (el sitio ofrece la voz del navegador).
    """
    mp3, path = basename + ".mp3", os.path.join(audiodir, basename + ".mp3")
    if os.path.exists(path):
        return mp3
    if AUDIO_TTS and os.environ.get("OPENAI_API_KEY") and texto.strip():
        try:
            os.makedirs(audiodir, exist_ok=True)
            data = generar_tts(texto)
            with open(path, "wb") as f:
                f.write(data)
            print(f"  briefing de audio generado: {mp3}")
            return mp3
        except Exception as e:  # noqa: BLE001
            print(f"  aviso: falló el briefing TTS ({e}); uso la voz del navegador.")
    return None

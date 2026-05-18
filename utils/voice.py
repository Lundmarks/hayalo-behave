import asyncio
import io
import os

import discord
from gtts import gTTS

import config


def _make_tts_gtts(text: str) -> io.BytesIO:
    buf = io.BytesIO()
    gTTS(text=text, lang="en").write_to_fp(buf)
    buf.seek(0)
    return buf


def _make_tts_elevenlabs(text: str) -> io.BytesIO:
    from elevenlabs import ElevenLabs
    client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    audio = client.text_to_speech.convert(
        voice_id=config.ELEVENLABS_VOICE_ID,
        text=text,
        model_id="eleven_multilingual_v2",
    )
    buf = io.BytesIO(b"".join(audio))
    buf.seek(0)
    return buf


def _make_tts(text: str) -> io.BytesIO:
    if config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID:
        try:
            return _make_tts_elevenlabs(text)
        except Exception as e:
            print(f"[voice] ElevenLabs TTS failed, falling back to gTTS: {e}")
    return _make_tts_gtts(text)


async def play_voice_announcement(
    guild: discord.Guild,
    voice_channel: discord.VoiceChannel,
    tts_text: str,
    sound_path: str | None = None,
) -> None:
    if guild.voice_client and guild.voice_client.is_connected():
        return

    vc: discord.VoiceClient | None = None
    try:
        vc = await voice_channel.connect(timeout=10.0, reconnect=False)

        if sound_path and os.path.isfile(sound_path):
            vc.play(discord.FFmpegPCMAudio(sound_path))
            while vc.is_playing():
                await asyncio.sleep(0.3)

        tts_buf = await asyncio.get_event_loop().run_in_executor(None, _make_tts, tts_text)
        vc.play(discord.FFmpegPCMAudio(tts_buf, pipe=True))
        while vc.is_playing():
            await asyncio.sleep(0.3)
    except Exception as e:
        print(f"[voice] failed to play announcement: {e}")
    finally:
        try:
            if vc and vc.is_connected():
                await vc.disconnect(force=True)
        except Exception:
            pass

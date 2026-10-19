"""Optional private-chat voice replies through a locally installed Piper CLI.

No voice model is bundled. This module does not choose Luna's persona or timbre.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from loguru import logger


async def synthesize_voice(
    text: str, executable: str, model_path: str, media_dir: Path,
) -> bytes | None:
    """Generate a small WAV safely; return None for text fallback."""
    if not text.strip() or len(text) > 500 or not model_path:
        return None
    model = Path(model_path).expanduser().resolve()
    if not model.is_file() or model.suffix != ".onnx":
        logger.warning("napcat: no valid Piper voice model configured")
        return None
    media_dir.mkdir(parents=True, exist_ok=True)
    output = media_dir / ("tts-" + uuid.uuid4().hex + ".wav")
    try:
        proc = await asyncio.create_subprocess_exec(
            executable, "--model", str(model), "--output_file", str(output),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(
                proc.communicate(text.encode("utf-8")), timeout=45,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning("napcat: Piper voice synthesis timed out")
            return None
        if proc.returncode != 0 or not output.is_file():
            logger.warning("napcat: Piper voice synthesis failed")
            return None
        if output.stat().st_size > 8 * 1024 * 1024:
            logger.warning("napcat: synthesized audio exceeded size budget")
            return None
        return await asyncio.to_thread(output.read_bytes)
    except (OSError, ValueError) as exc:
        logger.warning("napcat: Piper voice synthesis unavailable: {}", exc)
        return None
    finally:
        try:
            output.unlink(missing_ok=True)
        except OSError:
            pass

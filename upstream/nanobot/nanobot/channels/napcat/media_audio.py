"""Retrieve OneBot record segments without trusting arbitrary filesystem paths."""

from __future__ import annotations

import asyncio
import base64
import binascii
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Awaitable, Callable

import aiohttp

from nanobot.security.network import validate_url_target


class RecordMediaError(Exception):
    """Inbound record was unavailable or unsafe."""


def _unpack_base64(value: str, max_bytes: int) -> bytes:
    encoded = value.removeprefix("base64://")
    if len(encoded) > ((max_bytes + 2) // 3) * 4 + 8:
        raise RecordMediaError("audio payload too large")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RecordMediaError("invalid audio base64") from exc
    if not data or len(data) > max_bytes:
        raise RecordMediaError("audio payload outside size limit")
    return data


async def _fetch_audio(
    url: str, http: aiohttp.ClientSession | None, max_bytes: int,
) -> bytes:
    if http is None:
        raise RecordMediaError("HTTP session not ready")
    safe, _ = validate_url_target(url)
    if not safe:
        raise RecordMediaError("audio URL blocked by network policy")
    try:
        async with http.get(url, allow_redirects=False) as response:
            if response.status != 200:
                raise RecordMediaError("audio download failed or redirected")
            declared_size = int(response.headers.get("Content-Length", "0"))
            if declared_size > max_bytes:
                raise RecordMediaError("audio file too large")
            data = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise RecordMediaError("audio file too large")
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise RecordMediaError("audio download failed") from exc
    if not data:
        raise RecordMediaError("empty audio file")
    return bytes(data)


async def _read_shared_path(path: str, root: str, max_bytes: int, remote_root: str = "") -> bytes:
    if not root:
        raise RecordMediaError(
            "NapCat returned a local audio path inaccessible to nanobot; "
            "configure sharedRecordDir and mount the directory read-only"
        )
    safe_root = Path(root).expanduser().resolve(strict=True)
    # A container may return /app/.config/QQ/... while nanobot runs on the host.
    # Only map an explicit remote prefix into a fixed local mount.
    if remote_root:
        prefix = PurePosixPath(remote_root)
        remote = PurePosixPath(path)
        if (not remote.is_absolute() or not prefix.is_absolute()
                or str(prefix) == "/" or ".." in remote.parts):
            raise RecordMediaError("invalid remote audio path")
        try:
            relative = remote.relative_to(prefix)
        except ValueError as exc:
            raise RecordMediaError("remote audio path outside configured mount") from exc
        candidate = (safe_root / str(relative)).resolve(strict=True)
    else:
        candidate = Path(path).resolve(strict=True)
    if not candidate.is_relative_to(safe_root) or not candidate.is_file():
        raise RecordMediaError("audio path outside shared record directory")
    if candidate.stat().st_size > max_bytes:
        raise RecordMediaError("audio file too large")
    data = await asyncio.to_thread(candidate.read_bytes)
    if not data or len(data) > max_bytes:
        raise RecordMediaError("invalid audio file size")
    return data


async def resolve_record(
    record: dict[str, Any],
    call_action: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    http: aiohttp.ClientSession | None,
    media_dir: Path,
    *,
    max_bytes: int,
    shared_root: str = "",
    remote_root: str = "",
) -> Path:
    """Ask NapCat to transcode QQ Silk/AMR to MP3, then copy into local sandbox.

    Different NapCat versions return base64, a URL, or a local file path.
    Absolute paths are never read unless explicitly confined to a shared root.
    """
    token = record.get("file")
    if not isinstance(token, str) or not token or len(token) > 512 or "\x00" in token:
        raise RecordMediaError("invalid OneBot record identifier")
    declared = record.get("file_size")
    try:
        if declared is not None and int(declared) > max_bytes:
            raise RecordMediaError("incoming audio too large")
    except (ValueError, TypeError) as exc:
        raise RecordMediaError("invalid audio size") from exc

    try:
        reply = await call_action("get_record", {"file": token, "out_format": "mp3"})
    except (RuntimeError, asyncio.TimeoutError) as exc:
        raise RecordMediaError("NapCat get_record failed") from exc

    payload = reply.get("data")
    info = payload if isinstance(payload, dict) else {}
    base64_text = info.get("base64")
    converted = info.get("file")
    url = info.get("url") or record.get("url")
    if isinstance(base64_text, str) and base64_text:
        audio = _unpack_base64(base64_text, max_bytes)
    elif isinstance(converted, str) and converted.startswith("base64://"):
        audio = _unpack_base64(converted, max_bytes)
    elif isinstance(url, str) and url.startswith(("http://", "https://")):
        audio = await _fetch_audio(url, http, max_bytes)
    elif isinstance(converted, str):
        try:
            audio = await _read_shared_path(converted, shared_root, max_bytes, remote_root)
        except (OSError, ValueError) as exc:
            raise RecordMediaError("shared audio file unavailable") from exc
    else:
        raise RecordMediaError("NapCat did not return accessible audio data")

    media_dir.mkdir(parents=True, exist_ok=True)
    dest = media_dir / ("record-" + uuid.uuid4().hex + ".mp3")
    await asyncio.to_thread(dest.write_bytes, audio)
    return dest

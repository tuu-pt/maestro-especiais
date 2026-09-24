"""Image helpers: drop metadata (EXIF may hold GPS or names) and blank form images."""

import struct

import pymupdf

_JPEG_DROP = {*range(0xE1, 0xEE), 0xEF, 0xFE}  # APP1–APP13, APP15, COM (keep APP0/APP14)
_PNG_DROP = {b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def kind_of(data: bytes) -> str | None:
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:8] == _PNG_SIGNATURE:
        return "png"
    return None


def strip_metadata(data: bytes) -> bytes:
    """Same image without text/EXIF metadata. Unknown formats are returned unchanged."""
    kind = kind_of(data)
    if kind == "jpeg":
        return _strip_jpeg(data)
    if kind == "png":
        return _strip_png(data)
    return data


def _strip_jpeg(data: bytes) -> bytes:
    out = bytearray(data[:2])
    i = 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker == 0xDA:  # start of scan: the rest is image data
            out += data[i:]
            return bytes(out)
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            out += data[i : i + 2]
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2 : i + 4])
        segment = data[i : i + 2 + length]
        if marker not in _JPEG_DROP:
            out += segment
        i += 2 + length
    out += data[i:]
    return bytes(out)


def _strip_png(data: bytes) -> bytes:
    out = bytearray(_PNG_SIGNATURE)
    i = 8
    while i + 8 <= len(data):
        (length,) = struct.unpack(">I", data[i : i + 4])
        chunk_type = data[i + 4 : i + 8]
        chunk = data[i : i + 12 + length]
        if chunk_type not in _PNG_DROP:
            out += chunk
        i += 12 + length
    return bytes(out)


def blank(data: bytes) -> bytes | None:
    """White image of the same size and format, or None when that is not possible."""
    kind = kind_of(data)
    if kind is None:
        return None
    try:
        source = pymupdf.Pixmap(data)
    except Exception:  # noqa: BLE001 - unreadable image: caller reports it
        return None
    white = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, source.width, source.height), False)
    white.clear_with(255)
    return bytes(white.tobytes("jpeg" if kind == "jpeg" else "png"))

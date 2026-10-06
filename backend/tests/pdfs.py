"""Small PDFs written by the tests: a datasheet is only text for the reader (Phase 7).

No real datasheet is in data/fixtures yet (the team will add them): these files say what a
manufacturer's datasheet says, with the standard Helvetica font and Latin-1 text.
"""


def _escape(line: str) -> bytes:
    raw = line.encode("cp1252")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def pdf(pages: list[list[str]]) -> bytes:
    objects: list[bytes] = []
    kids = []
    font_id = 3 + 2 * len(pages)
    for n, lines in enumerate(pages):
        page_id, content_id = 3 + 2 * n, 4 + 2 * n
        kids.append(f"{page_id} 0 R")
        stream = b"BT /F1 11 Tf 50 780 Td 14 TL " + b" ".join(
            b"(" + _escape(line) + b") '" for line in lines) + b" ET"  # fmt: skip
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    header = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode(),
    ]
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    body = header + objects + [font]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(body, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(body) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(body) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def datasheet(*lines: str, more: list[str] | None = None) -> bytes:
    """A one or two page datasheet."""
    return pdf([list(lines)] + ([more] if more else []))

"""Bytes → text for files that do not say their encoding (brief 04 D2, step 3).

Adapted from PayCore `convert/encoding.decode_text`: BOMs first, then the whole file as UTF-8,
then line by line (a line that is valid UTF-8 is UTF-8, any other is cp1254: Turkish files
written on Windows). Changed on purpose (brief: no `errors="replace"`, which silently and for
good destroys Turkish letters): decoding is strict. A byte cp1254 leaves undefined, or broken
UTF-16, raises `UndecodableText`; the document fails with `encoding_undecodable` instead of
entering the index with U+FFFD in it.
"""

FALLBACK = "cp1254"


class UndecodableText(ValueError):
    def __init__(self, line: int):
        super().__init__(f"line {line} is neither UTF-8 nor {FALLBACK}")
        self.line = line


def decode_text(data: bytes) -> tuple[str, str]:
    """(text, encoding label): utf-8, utf-16, cp1254 or utf-8+cp1254."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            raise UndecodableText(0) from None
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    used: set[str] = set()
    out: list[str] = []
    for number, line in enumerate(data.split(b"\n"), start=1):
        try:
            out.append(line.decode("utf-8"))
            if any(b >= 0x80 for b in line):
                used.add("utf-8")
        except UnicodeDecodeError:
            try:
                out.append(line.decode(FALLBACK))
            except UnicodeDecodeError:
                raise UndecodableText(number) from None
            used.add(FALLBACK)
    return "\n".join(out), "+".join(sorted(used, key=["utf-8", FALLBACK].index))

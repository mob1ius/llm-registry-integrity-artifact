"""Minimal GGUF header/metadata parser.

Parses only the magic/version/counts + metadata key-value section of a GGUF
file (per the documented format: https://github.com/ggml-org/ggml/blob/master/docs/gguf.md).
Does NOT parse tensor info or tensor data, so it works on a truncated file --
e.g. the first few MB fetched via an HTTP Range request -- without needing the
full (often multi-GB) file. This lets a registry-scale audit inspect every
individual quantization file in a multi-file repo cheaply, rather than relying
on Hugging Face's repo-level `expand[]=gguf` API, which only reflects one
(unspecified) file per repo -- exactly the blind spot the "clean first file /
dirty subsequent file" attack pattern exploits.

Raises `TruncatedGGUFError` if the provided bytes run out before the metadata
section is fully parsed -- callers should re-fetch with a larger byte range.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum


class TruncatedGGUFError(Exception):
    """Raised when the provided byte buffer ends before metadata parsing completes."""


class GGUFValueType(IntEnum):
    UINT8 = 0
    INT8 = 1
    UINT16 = 2
    INT16 = 3
    UINT32 = 4
    INT32 = 5
    FLOAT32 = 6
    BOOL = 7
    STRING = 8
    ARRAY = 9
    UINT64 = 10
    INT64 = 11
    FLOAT64 = 12


_SCALAR_FORMATS = {
    GGUFValueType.UINT8: ("<B", 1),
    GGUFValueType.INT8: ("<b", 1),
    GGUFValueType.UINT16: ("<H", 2),
    GGUFValueType.INT16: ("<h", 2),
    GGUFValueType.UINT32: ("<I", 4),
    GGUFValueType.INT32: ("<i", 4),
    GGUFValueType.FLOAT32: ("<f", 4),
    GGUFValueType.BOOL: ("<B", 1),
    GGUFValueType.UINT64: ("<Q", 8),
    GGUFValueType.INT64: ("<q", 8),
    GGUFValueType.FLOAT64: ("<d", 8),
}

# Arrays of strings (e.g. tokenizer vocab, merges) can be tens of MB and are
# not needed for this audit. Skip decoding them past this many elements --
# just seek past their bytes and record a placeholder + element count.
MAX_ARRAY_ELEMENTS_TO_DECODE = 64


@dataclass
class GGUFHeaderResult:
    version: int
    tensor_count: int
    metadata_kv_count: int
    metadata: dict = field(default_factory=dict)
    bytes_consumed: int = 0
    truncated_keys_skipped: list[str] = field(default_factory=list)


class _Cursor:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _need(self, n: int) -> None:
        if self.pos + n > len(self.data):
            raise TruncatedGGUFError(
                f"need {n} bytes at offset {self.pos}, only {len(self.data) - self.pos} available"
            )

    def read(self, n: int) -> bytes:
        self._need(n)
        b = self.data[self.pos : self.pos + n]
        self.pos += n
        return b

    def read_u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def read_u64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def read_gguf_string(self) -> str:
        length = self.read_u64()
        raw = self.read(length)
        return raw.decode("utf-8", errors="replace")

    def read_scalar(self, vtype: GGUFValueType):
        fmt, size = _SCALAR_FORMATS[vtype]
        val = struct.unpack(fmt, self.read(size))[0]
        return bool(val) if vtype == GGUFValueType.BOOL else val

    def read_value(self, vtype: GGUFValueType):
        if vtype == GGUFValueType.STRING:
            return self.read_gguf_string()
        if vtype == GGUFValueType.ARRAY:
            elem_type = GGUFValueType(self.read_u32())
            length = self.read_u64()
            if elem_type == GGUFValueType.STRING:
                out = []
                for i in range(length):
                    s = self.read_gguf_string()
                    if i < MAX_ARRAY_ELEMENTS_TO_DECODE:
                        out.append(s)
                return {"_array_type": "STRING", "_length": length, "_sample": out}
            elif elem_type in _SCALAR_FORMATS:
                fmt, size = _SCALAR_FORMATS[elem_type]
                out = []
                for i in range(length):
                    v = struct.unpack(fmt, self.read(size))[0]
                    if i < MAX_ARRAY_ELEMENTS_TO_DECODE:
                        out.append(v)
                return {"_array_type": elem_type.name, "_length": length, "_sample": out}
            else:
                raise ValueError(f"nested array of arrays not supported: {elem_type}")
        return self.read_scalar(vtype)


def parse_gguf_header(data: bytes) -> GGUFHeaderResult:
    """Parse the magic/version/counts + metadata KV section from raw GGUF bytes.

    `data` may be a truncated prefix of the file (e.g. from an HTTP Range
    request) -- as long as it's long enough to contain the full metadata
    section. Raises TruncatedGGUFError if not; caller should retry with more
    bytes (doubling is a reasonable strategy).
    """
    c = _Cursor(data)
    magic = c.read(4)
    if magic != b"GGUF":
        raise ValueError(f"not a GGUF file (magic={magic!r})")
    version = c.read_u32()
    tensor_count = c.read_u64()
    metadata_kv_count = c.read_u64()

    metadata: dict = {}
    for _ in range(metadata_kv_count):
        key = c.read_gguf_string()
        vtype = GGUFValueType(c.read_u32())
        value = c.read_value(vtype)
        metadata[key] = value

    return GGUFHeaderResult(
        version=version,
        tensor_count=tensor_count,
        metadata_kv_count=metadata_kv_count,
        metadata=metadata,
        bytes_consumed=c.pos,
    )


def fetch_and_parse_remote_gguf_header(
    url: str,
    initial_bytes: int = 4 * 1024 * 1024,
    max_bytes: int = 64 * 1024 * 1024,
    session=None,
) -> GGUFHeaderResult:
    """Fetch a GGUF file's header via HTTP Range requests, growing the range
    (doubling) until the metadata section parses successfully or max_bytes is
    exceeded. Only ever downloads the header/metadata prefix, never the
    (typically multi-GB) tensor data that follows.
    """
    import requests

    sess = session or requests.Session()
    n = initial_bytes
    while n <= max_bytes:
        resp = sess.get(url, headers={"Range": f"bytes=0-{n - 1}"}, timeout=60)
        resp.raise_for_status()
        try:
            return parse_gguf_header(resp.content)
        except TruncatedGGUFError:
            n *= 2
            continue
    raise TruncatedGGUFError(f"metadata section did not fit in {max_bytes} bytes for {url}")

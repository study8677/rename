"""Minimal protobuf wire-format reader/writer (stdlib only).

Used by the Antigravity adapter to peek at — and selectively rewrite — the
``trajectorySummaries`` blob in ``state.vscdb``. Only what we need: varint,
length-delimited fields, and a passthrough rewriter that re-emits unchanged
fields byte-for-byte while letting one field be replaced.

Not a full protobuf implementation. No reflection, no schema introspection,
no packed-repeated decoding. If you want those, use ``protobuf`` proper.
"""

from __future__ import annotations

WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LEN = 2
WIRE_FIXED32 = 5


def read_varint(buf: bytes, i: int) -> tuple[int, int]:
    """Decode one varint starting at ``i``. Returns (value, next_i)."""
    n = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if b < 0x80:
            return n, i
        shift += 7
        if shift >= 64:
            raise ValueError("varint too long")


def write_varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def iter_fields(buf: bytes):
    """Yield (field_num, wire_type, value, start_offset, end_offset).

    For wire_type 2, value is bytes. For 0, value is int. For 1/5, value is the
    raw 8/4 bytes. ``start_offset`` is the tag byte; ``end_offset`` is one past
    the value's last byte — handy for re-emitting a field verbatim.
    """
    i = 0
    n = len(buf)
    while i < n:
        start = i
        tag, i = read_varint(buf, i)
        fn = tag >> 3
        wt = tag & 7
        if wt == WIRE_LEN:
            ln, i = read_varint(buf, i)
            val = buf[i : i + ln]
            i += ln
        elif wt == WIRE_VARINT:
            val, i = read_varint(buf, i)
        elif wt == WIRE_FIXED64:
            val = buf[i : i + 8]
            i += 8
        elif wt == WIRE_FIXED32:
            val = buf[i : i + 4]
            i += 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        yield fn, wt, val, start, i


def encode_len_field(field_num: int, value: bytes) -> bytes:
    """Encode one length-delimited field (wire-type 2)."""
    tag = (field_num << 3) | WIRE_LEN
    return write_varint(tag) + write_varint(len(value)) + value


def rewrite(buf: bytes, *, when, replace) -> bytes:
    """Walk ``buf``, replacing fields where ``when(fn, wt, val) == True`` with
    ``replace(fn, wt, val) -> bytes`` (the bytes returned are the *full* field
    including its tag and length prefix — use ``encode_len_field`` etc.).

    Other fields are re-emitted verbatim. Unknown trailing bytes are preserved.
    """
    out = bytearray()
    for fn, wt, val, start, end in iter_fields(buf):
        if when(fn, wt, val):
            out += replace(fn, wt, val)
        else:
            out += buf[start:end]
    return bytes(out)


def timestamp_to_epoch(blob: bytes) -> float:
    """google.protobuf.Timestamp -> float seconds since the epoch."""
    seconds = 0
    nanos = 0
    for fn, wt, val, *_ in iter_fields(blob):
        if fn == 1 and wt == WIRE_VARINT:
            seconds = val
        elif fn == 2 and wt == WIRE_VARINT:
            nanos = val
    return seconds + nanos / 1e9

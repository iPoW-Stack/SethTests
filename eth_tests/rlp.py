from __future__ import annotations


def decode(data: bytes):
    value, pos = _decode_at(data, 0)
    if pos != len(data):
        raise ValueError("trailing RLP bytes")
    return value


def _decode_at(data: bytes, pos: int):
    if pos >= len(data):
        raise ValueError("unexpected end of RLP")
    b = data[pos]
    if b < 0x80:
        return bytes([b]), pos + 1
    if b <= 0xb7:
        size = b - 0x80
        start = pos + 1
        end = start + size
        return data[start:end], end
    if b <= 0xbf:
        len_size = b - 0xb7
        start = pos + 1
        size = int.from_bytes(data[start:start + len_size], "big")
        payload = start + len_size
        return data[payload:payload + size], payload + size
    if b <= 0xf7:
        size = b - 0xc0
        start = pos + 1
        return _decode_list_payload(data, start, start + size)
    len_size = b - 0xf7
    start = pos + 1
    size = int.from_bytes(data[start:start + len_size], "big")
    payload = start + len_size
    return _decode_list_payload(data, payload, payload + size)


def _decode_list_payload(data: bytes, start: int, end: int):
    out = []
    pos = start
    while pos < end:
        item, pos = _decode_at(data, pos)
        out.append(item)
    if pos != end:
        raise ValueError("RLP list length mismatch")
    return out, pos


def encode(value) -> bytes:
    if isinstance(value, list):
        payload = b"".join(encode(v) for v in value)
        return _prefix(payload, 0xc0)
    if isinstance(value, int):
        if value == 0:
            return bytes([0x80])
        value = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError(f"unsupported RLP value: {type(value)!r}")
    b = bytes(value)
    if len(b) == 1 and b[0] < 0x80:
        return b
    return _prefix(b, 0x80)


def _prefix(payload: bytes, short_offset: int) -> bytes:
    if len(payload) <= 55:
        return bytes([short_offset + len(payload)]) + payload
    size = len(payload).to_bytes((len(payload).bit_length() + 7) // 8, "big")
    return bytes([short_offset + 55 + len(size)]) + size + payload


def bytes_to_int(value: bytes) -> int:
    return int.from_bytes(value, "big") if value else 0


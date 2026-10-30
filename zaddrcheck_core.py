"""Zcash address parser: transparent Base58Check, Sapling Bech32, ZIP-316 UA."""
import hashlib

BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BASE58_PREFIXES = {bytes.fromhex(x) for x in ("1cb8", "1cbd", "1d25", "1cba")}
SAPLING_HRPS = {"zs", "ztestsapling", "zregtestsapling"}
UNIFIED_HRPS = {"u", "utest", "uregtest"}
GEN = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _base58check(address: str) -> bool:
    if not 30 <= len(address) <= 40:
        return False
    try:
        number = 0
        for char in address:
            number = number * 58 + BASE58.index(char)
        value = number.to_bytes((number.bit_length() + 7) // 8, "big")
        value = b"\0" * (len(address) - len(address.lstrip("1"))) + value
        if len(value) != 26:
            return False
        payload, checksum = value[:-4], value[-4:]
        calculated = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        return payload[:2] in BASE58_PREFIXES and checksum == calculated
    except (ValueError, OverflowError):
        return False


def _polymod(values: list[int]) -> int:
    check = 1
    for val in values:
        high = check >> 25
        check = ((check & 0x1FFFFFF) << 5) ^ val
        for i in range(5):
            if (high >> i) & 1:
                check ^= GEN[i]
    return check


def _decode_bech32(address: str):
    # Zcash permits strings longer than BIP-173's 90-character limit.
    if not 8 <= len(address) <= 8192 or not address.isascii():
        return None
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in address):
        return None
    if address.lower() != address and address.upper() != address:
        return None
    canonical = address.lower()
    separator = canonical.rfind("1")
    if separator < 1 or separator + 7 > len(canonical):
        return None
    hrp = canonical[:separator]
    try:
        data = [BECH32.index(ch) for ch in canonical[separator + 1:]]
    except ValueError:
        return None
    expanded = [ord(ch) >> 5 for ch in hrp] + [0] + [ord(ch) & 31 for ch in hrp]
    variant = _polymod(expanded + data)
    if variant not in (1, 0x2BC830A3):
        return None
    accum = 0
    bits = 0
    result = bytearray()
    for item in data[:-6]:
        accum = ((accum << 5) | item) & 0xFFF
        bits += 5
        if bits >= 8:
            bits -= 8
            result.append((accum >> bits) & 0xFF)
    if bits >= 5 or (accum & ((1 << bits) - 1)):
        return None
    return hrp, variant, bytes(result)


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _g(round_no: int, data: bytes, size: int) -> bytes:
    chunks = []
    for index in range((size + 63) // 64):
        person = b"UA_F4Jumble_G" + bytes((round_no,)) + index.to_bytes(2, "little")
        chunks.append(hashlib.blake2b(data, digest_size=64, person=person).digest())
    return b"".join(chunks)[:size]


def _h(round_no: int, data: bytes, size: int) -> bytes:
    person = b"UA_F4Jumble_H" + bytes((round_no, 0, 0))
    return hashlib.blake2b(data, digest_size=size, person=person).digest()


def _f4jumble_inverse(message: bytes) -> bytes:
    if not 38 <= len(message) <= 8192:
        raise ValueError("Unsupported Unified Address length")
    left_len = min(64, len(message) // 2)
    c, d = message[:left_len], message[left_len:]
    y = _xor(c, _h(1, d, left_len))
    x = _xor(d, _g(1, y, len(d)))
    a = _xor(y, _h(0, x, left_len))
    b = _xor(x, _g(0, a, len(d)))
    return a + b


def _compact_size(raw: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(raw):
        raise ValueError("Missing CompactSize")
    first = raw[offset]
    offset += 1
    if first < 253:
        value = first
    else:
        size = {253: 2, 254: 4, 255: 8}[first]
        if offset + size > len(raw):
            raise ValueError("Truncated CompactSize")
        value = int.from_bytes(raw[offset:offset + size], "little")
        offset += size
        if value < {253: 253, 254: 65536, 255: 4294967296}[first]:
            raise ValueError("Noncanonical CompactSize")
    if value > 0x2000000:
        raise ValueError("Oversized CompactSize")
    return value, offset


def _unified(payload: bytes, hrp: str) -> bool:
    try:
        decoded = _f4jumble_inverse(payload)
        suffix = hrp.encode("ascii").ljust(16, b"\0")
        if not decoded.endswith(suffix):
            return False
        raw = decoded[:-16]
        offset = 0
        previous = -1
        types = set()
        while offset < len(raw):
            typecode, offset = _compact_size(raw, offset)
            size, offset = _compact_size(raw, offset)
            if typecode <= previous or size > len(raw) - offset:
                return False
            data = raw[offset:offset + size]
            offset += size
            if typecode in (0, 1) and len(data) != 20:
                return False
            if typecode in (2, 3) and len(data) != 43:
                return False
            previous = typecode
            types.add(typecode)
        return bool(types & {2, 3}) and not ({0, 1} <= types)
    except (ValueError, OverflowError):
        return False


def classify(address: str) -> dict:
    """Return one stable JSON-compatible result even for empty/malformed input."""
    kind = "invalid"
    if isinstance(address, str) and address:
        if _base58check(address):
            kind = "transparent"
        else:
            parsed = _decode_bech32(address)
            if parsed is not None:
                hrp, variant, payload = parsed
                if hrp in SAPLING_HRPS and variant == 1 and len(payload) == 43:
                    kind = "sapling"
                elif hrp in UNIFIED_HRPS and variant == 0x2BC830A3 and _unified(payload, hrp):
                    kind = "unified"
    return {"input": address, "valid": kind != "invalid", "type": kind}

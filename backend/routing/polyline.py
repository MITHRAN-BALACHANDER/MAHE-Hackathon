"""Google-style polyline encoding/decoding for route geometries."""


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google-encoded polyline string into (lat, lon) tuples."""
    points: list[tuple[float, float]] = []
    idx, lat, lon = 0, 0, 0
    length = len(encoded)

    while idx < length:
        # Latitude
        shift, result = 0, 0
        while True:
            b = ord(encoded[idx]) - 63
            idx += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lat += (~(result >> 1) if (result & 1) else (result >> 1))

        # Longitude
        shift, result = 0, 0
        while True:
            b = ord(encoded[idx]) - 63
            idx += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lon += (~(result >> 1) if (result & 1) else (result >> 1))

        points.append((lat / 1e5, lon / 1e5))

    return points


def encode_polyline(coords: list[tuple[float, float]]) -> str:
    """Encode a list of (lat, lon) tuples into a Google polyline string."""
    result: list[str] = []
    prev_lat, prev_lon = 0, 0

    for lat, lon in coords:
        ilat = round(lat * 1e5)
        ilon = round(lon * 1e5)
        _encode_value(ilat - prev_lat, result)
        _encode_value(ilon - prev_lon, result)
        prev_lat, prev_lon = ilat, ilon

    return "".join(result)


def _encode_value(value: int, result: list[str]) -> None:
    value = ~(value << 1) if value < 0 else (value << 1)
    while value >= 0x20:
        result.append(chr((0x20 | (value & 0x1F)) + 63))
        value >>= 5
    result.append(chr(value + 63))

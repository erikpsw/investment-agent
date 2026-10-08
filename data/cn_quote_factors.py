"""Optional factors on Tencent's CN wire, shared by both quote clients."""
import math


def tencent_cn_factors(parts: list[str]) -> dict:
    def field(index):
        try:
            value = float(parts[index])
            return value if math.isfinite(value) else None
        except (IndexError, TypeError, ValueError):
            return None

    pb, ratio = field(46), field(49)
    if ratio is not None and ratio < 0:
        ratio = None
    return {"pb_ratio": pb, "volume_ratio": ratio,
            "pb_source": "Tencent" if pb is not None else None,
            "volume_ratio_source": "Tencent" if ratio is not None else None}

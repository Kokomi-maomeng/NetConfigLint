"""Translate diagnostic prose without replacing configuration tokens or object names."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _templates() -> tuple[tuple[re.Pattern[str], str], ...]:
    path = Path(__file__).with_name("diagnostics_zh.json")
    if not path.exists():
        return ()
    entries: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for source, translated in entries.items():
        parts = re.split(r"(\{\d+\})", source)
        pattern = "".join(r"(.+?)" if re.fullmatch(r"\{\d+\}", part) else re.escape(part) for part in parts)
        result.append((re.compile(pattern, re.DOTALL), translated))
    return tuple(result)


def _fill(translated: str, match: re.Match[str]) -> str:
    if translated == "采集结果中出现异常的{0}状态。":
        labels = {
            "installed card": "板卡",
            "fan": "风扇",
            "power module": "电源模块",
            "temperature sensor": "温度传感器",
        }
        return f"采集结果中出现异常的{labels.get(match.group(1), match.group(1))}状态。"
    return re.sub(r"\{(\d+)\}", lambda m: match.group(int(m[1]) + 1), translated)


def translate_diagnostic(value: str) -> str:
    if message := re.fullmatch(r"(.+) message: (.+)\.", value):
        return f"{message[1]} 信息\uff1a{translate_diagnostic(message[2])}。"
    if value.endswith(" Starting view was not supplied."):
        return (
            translate_diagnostic(value.removesuffix(" Starting view was not supplied.")) + " 未提供起始视图。"
        )
    for pattern, translated in _templates():
        match = pattern.fullmatch(value)
        if match:
            return _fill(translated, match)
    if "H3C Comware" in value:
        huawei_wording = value.replace("H3C Comware", "Huawei")
        translated = translate_diagnostic(huawei_wording)
        if translated != huawei_wording:
            return translated.replace("华为", "H3C Comware")
    suffix = re.fullmatch(r"(.+) Matching configuration lines: (\d+)\.", value, re.DOTALL)
    if suffix:
        return translate_diagnostic(suffix[1]) + f" 匹配的配置行数: {suffix[2]}。"
    return value

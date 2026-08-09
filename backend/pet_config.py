import json
from pathlib import Path
from typing import Any, Dict


PET_ACTIONS = ("idle", "blink", "thinking", "tool", "working", "walk", "jump", "wave")
PET_PLAYBACK_MODES = {"loop", "once", "pingpong"}
PET_END_BEHAVIORS = {"idle", "hold"}
DEFAULT_PET_ANIMATIONS = {
    "idle": {"fps": 7.0, "mode": "loop", "after": "idle"},
    "blink": {"fps": 33.0, "mode": "once", "after": "idle"},
    "thinking": {"fps": 20.0, "mode": "loop", "after": "idle"},
    "tool": {"fps": 20.0, "mode": "loop", "after": "idle"},
    "working": {"fps": 20.0, "mode": "loop", "after": "idle"},
    "walk": {"fps": 20.0, "mode": "loop", "after": "idle"},
    "jump": {"fps": 12.0, "mode": "once", "after": "idle"},
    "wave": {"fps": 27.0, "mode": "loop", "after": "idle"},
}
DEFAULT_PET_PLACEMENT = {"x": 0.0, "y": 0.0, "scale": 1.0}


def normalize_pet_animations(value: Any) -> Dict[str, Dict[str, Any]]:
    source = value if isinstance(value, dict) else {}
    result: Dict[str, Dict[str, Any]] = {}
    for action, defaults in DEFAULT_PET_ANIMATIONS.items():
        raw = source.get(action) if isinstance(source.get(action), dict) else {}
        try:
            fps = float(raw.get("fps", defaults["fps"]))
        except (TypeError, ValueError):
            fps = defaults["fps"]
        mode = raw.get("mode", defaults["mode"])
        after = raw.get("after", defaults["after"])
        result[action] = {
            "fps": max(1.0, min(60.0, fps)),
            "mode": mode if mode in PET_PLAYBACK_MODES else defaults["mode"],
            "after": after if after in PET_END_BEHAVIORS else defaults["after"],
        }
    return result


def validate_pet_animations(value: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("Pet animations must be an object")
    unsupported = set(value) - set(PET_ACTIONS)
    if unsupported:
        raise ValueError(f"Unsupported pet action: {sorted(unsupported)[0]}")
    for action, raw in value.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Pet animation '{action}' must be an object")
        try:
            fps = float(raw.get("fps"))
        except (TypeError, ValueError):
            raise ValueError(f"Pet animation '{action}' FPS must be a number")
        if not 1 <= fps <= 60:
            raise ValueError(f"Pet animation '{action}' FPS must be between 1 and 60")
        if raw.get("mode") not in PET_PLAYBACK_MODES:
            raise ValueError(f"Invalid playback mode for pet animation '{action}'")
        if raw.get("after") not in PET_END_BEHAVIORS:
            raise ValueError(f"Invalid end behavior for pet animation '{action}'")
    return normalize_pet_animations(value)


def normalize_pet_placements(value: Any) -> Dict[str, Dict[str, float]]:
    source = value if isinstance(value, dict) else {}
    result: Dict[str, Dict[str, float]] = {}
    for action in PET_ACTIONS:
        raw = source.get(action) if isinstance(source.get(action), dict) else {}
        placement = {}
        for key, minimum, maximum in (
            ("x", -1.0, 1.0),
            ("y", -1.0, 1.0),
            ("scale", 0.25, 3.0),
        ):
            try:
                number = float(raw.get(key, DEFAULT_PET_PLACEMENT[key]))
            except (TypeError, ValueError):
                number = DEFAULT_PET_PLACEMENT[key]
            placement[key] = max(minimum, min(maximum, number))
        result[action] = placement
    return result


def validate_pet_placements(value: Any) -> Dict[str, Dict[str, float]]:
    if not isinstance(value, dict):
        raise ValueError("Pet placements must be an object")
    unsupported = set(value) - set(PET_ACTIONS)
    if unsupported:
        raise ValueError(f"Unsupported pet placement action: {sorted(unsupported)[0]}")
    for action, raw in value.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Pet placement '{action}' must be an object")
        unsupported_options = set(raw) - set(DEFAULT_PET_PLACEMENT)
        if unsupported_options:
            raise ValueError(f"Unsupported pet placement option: {sorted(unsupported_options)[0]}")
        for key, minimum, maximum in (
            ("x", -1.0, 1.0),
            ("y", -1.0, 1.0),
            ("scale", 0.25, 3.0),
        ):
            if key not in raw:
                continue
            try:
                number = float(raw[key])
            except (TypeError, ValueError):
                raise ValueError(f"Pet placement '{action}' {key} must be a number")
            if not minimum <= number <= maximum:
                raise ValueError(
                    f"Pet placement '{action}' {key} must be between {minimum} and {maximum}"
                )
    return normalize_pet_placements(value)


def read_pet_config(theme_json: Path) -> Dict[str, Any]:
    data = {}
    if theme_json.exists():
        try:
            data = json.loads(theme_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    try:
        scale = float(data.get("pet_scale", 1.0))
    except (TypeError, ValueError):
        scale = 1.0
    return {
        "scale": max(0.6, min(1.8, scale)),
        "animations": normalize_pet_animations(data.get("pet_animations")),
        "placements": normalize_pet_placements(data.get("pet_placements")),
    }

import enum


class PrefKey(enum.StrEnum):
    Speak = "speak"
    Proactive = "proactive"
    Mode = "mode"
    Theme = "theme"
    Spotlight = "spotlight"


class Proactive(enum.StrEnum):
    Never = "never"
    Rarely = "rarely"
    Weekly = "weekly"


class ChatMode(enum.StrEnum):
    Text = "text"
    Voice = "voice"


class Theme(enum.StrEnum):
    System = "system"
    Light = "light"
    Dark = "dark"


class Spotlight(enum.StrEnum):
    """How the picture answers a tap on an event. Unified: a chip naming it and
    its dot do one thing (R-0168). Chip: the old chip spotlight, kept so one
    person can be switched back without a deploy."""

    Unified = "unified"
    Chip = "chip"


PREF_ENUMS = {
    PrefKey.Proactive: Proactive,
    PrefKey.Mode: ChatMode,
    PrefKey.Theme: Theme,
    PrefKey.Spotlight: Spotlight,
}

PREF_DEFAULTS = {
    PrefKey.Speak: False,
    PrefKey.Proactive: Proactive.Never,
    PrefKey.Mode: ChatMode.Text,
    PrefKey.Theme: Theme.System,
    PrefKey.Spotlight: Spotlight.Unified,
}


def coerce_pref(key: PrefKey, value):
    if key is PrefKey.Speak:
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a bool, got {value!r}")
        return value
    return PREF_ENUMS[key](value)

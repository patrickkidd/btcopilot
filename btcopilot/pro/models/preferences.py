import enum


class PrefKey(enum.StrEnum):
    Speak = "speak"
    Proactive = "proactive"
    Mode = "mode"
    Theme = "theme"


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


PREF_ENUMS = {
    PrefKey.Proactive: Proactive,
    PrefKey.Mode: ChatMode,
    PrefKey.Theme: Theme,
}

PREF_DEFAULTS = {
    PrefKey.Speak: False,
    PrefKey.Proactive: Proactive.Never,
    PrefKey.Mode: ChatMode.Text,
    PrefKey.Theme: Theme.System,
}


def coerce_pref(key: PrefKey, value):
    if key is PrefKey.Speak:
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a bool, got {value!r}")
        return value
    return PREF_ENUMS[key](value)

import enum


class PrefKey(enum.StrEnum):
    Speak = "speak"
    Proactive = "proactive"
    Mode = "mode"
    Theme = "theme"
    Spotlight = "spotlight"
    # Shown to a coder once: the task card's four numbered lines until they
    # tap Got it, and the hint on the first line they tap in the coding screen.
    HowItWorks = "how_it_works"
    LineHint = "line_hint"
    BugReports = "bug_reports"
    # The models each of this person's turns runs again on, for comparison
    # only [R-0596]; none is off.
    ShadowModels = "shadow_models"


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


class BugReports(enum.StrEnum):
    """Whether a turn or the page breaking asks before its report is sent."""

    Ask = "ask"
    Always = "always"


# The models a turn may run again on, as aliases in llmutil.MODEL_ALIASES.
SHADOW_CANDIDATES = ("sonnet", "gemini-pro")

PREF_ENUMS = {
    PrefKey.Proactive: Proactive,
    PrefKey.Mode: ChatMode,
    PrefKey.Theme: Theme,
    PrefKey.Spotlight: Spotlight,
    PrefKey.BugReports: BugReports,
}

PREF_DEFAULTS = {
    PrefKey.Speak: False,
    PrefKey.Proactive: Proactive.Never,
    PrefKey.Mode: ChatMode.Text,
    PrefKey.Theme: Theme.System,
    PrefKey.Spotlight: Spotlight.Unified,
    PrefKey.HowItWorks: True,
    PrefKey.LineHint: True,
    PrefKey.BugReports: BugReports.Ask,
    PrefKey.ShadowModels: (),
}


def coerce_pref(key: PrefKey, value):
    if key is PrefKey.ShadowModels:
        if not isinstance(value, (list, tuple)) or set(value) - set(SHADOW_CANDIDATES):
            raise ValueError(f"{key} must name only {SHADOW_CANDIDATES}, got {value!r}")
        return tuple(value)
    if isinstance(PREF_DEFAULTS[key], bool):
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a bool, got {value!r}")
        return value
    return PREF_ENUMS[key](value)

"""The credential names a sandbox must never inherit.

One list, here, because the launcher that blanks them and the health probe that
reports them have to agree: a name present in one copy and missing from the
other is a credential a sandbox silently keeps. Flask's app.run() loads the
nearest .env before serving, so a name omitted here reaches the process no
matter what the launcher's own environment looked like.
"""

LLM_KEYS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_EXTRACTION_API_KEY",
    "GOOGLE_GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "GROK_API_KEY",
    "MINIMAX_API_KEY",
)

SERVICE_KEYS = (
    "ASSEMBLYAI_API_KEY",
    "STRIPE_KEY",
    "FLASK_STRIPE_KEY",
    "FD_TEST_STRIPE_KEY",
    "ATLASSIAN_TOKEN",
    "GITHUB_TOKEN",
)

BLANKED = LLM_KEYS + SERVICE_KEYS

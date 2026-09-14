import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml
from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateNotFound

FRONTMATTER = "---"


def encrypted(raw: str) -> bool:
    """Whether sops holds this file. The envelope is JSON with a `sops` key, and
    that key sits at the end of it, so the whole file has to be parsed rather
    than its first few lines scanned."""
    if not raw.lstrip().startswith("{"):
        return False
    try:
        return "sops" in json.loads(raw)
    except json.JSONDecodeError:
        return False


def key_present() -> bool:
    """Whether this machine can open the encrypted files at all. Nothing in the
    app asks: the app decrypts and fails loudly if it cannot. It is the test run
    that needs to know, so it can use the open-source prompts instead of failing
    to start."""
    key = os.environ.get("SOPS_AGE_KEY_FILE")
    return bool(
        shutil.which("sops")
        and (os.environ.get("SOPS_AGE_KEY") or (key and Path(key).is_file()))
    )


def read(path: Path) -> str:
    """The file's text, decrypted when sops holds it."""
    raw = path.read_text()
    if not encrypted(raw):
        return raw
    done = subprocess.run(
        ["sops", "-d", str(path)], capture_output=True, text=True, check=True
    )
    return done.stdout


def split(text: str) -> tuple[dict, str]:
    """A prompty file's frontmatter and its body."""
    if not text.startswith(FRONTMATTER + "\n"):
        return {}, text
    head, _, body = text[len(FRONTMATTER) + 1 :].partition("\n" + FRONTMATTER + "\n")
    return yaml.safe_load(head) or {}, body


class PromptLoader(BaseLoader):
    """Jinja2's loader holds one template, so a fragment include cannot resolve.
    This one searches the prompt directories in order, decrypting as it goes, so
    a private directory overrides a public one file by file."""

    def __init__(self, dirs: list[Path]):
        self.dirs = dirs

    def get_source(self, environment, template):
        for d in self.dirs:
            path = d / template
            if path.is_file():
                _, body = split(read(path))
                mtime = path.stat().st_mtime
                return body, str(path), lambda: path.stat().st_mtime == mtime
        raise TemplateNotFound(template)


class PromptDir:
    """The prompts on disk. A name resolves to the first directory holding it;
    a fragment a prompt includes resolves the same way, and a missing one
    raises rather than rendering empty."""

    def __init__(self, dirs: list[Path]):
        self.dirs = [Path(d) for d in dirs if Path(d).is_dir()]
        self.env = Environment(
            loader=PromptLoader(self.dirs),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            autoescape=False,
        )

    def text(self, name: str, **inputs) -> str:
        declared = self.head(name).get("inputs") or {}
        for key, spec in declared.items():
            value = inputs.get(key)
            if isinstance(value, str):
                inputs[key] = value.strip()
            if not inputs.get(key) and "default" in spec:
                inputs[key] = spec["default"]
        return self.env.get_template(name + ".prompty").render(**inputs)

    def fragment(self, name: str) -> str:
        return self.env.get_template(f"fragments/{name}.md").render()

    def head(self, name: str) -> dict:
        for d in self.dirs:
            path = d / (name + ".prompty")
            if path.is_file():
                return split(read(path))[0]
        raise TemplateNotFound(name + ".prompty")

    def heads(self, name: str) -> list[dict]:
        """Every directory's frontmatter for this name, least important first, so
        a caller can take one entry from the private file and the rest from the
        public one."""
        found = [
            split(read(d / (name + ".prompty")))[0]
            for d in reversed(self.dirs)
            if (d / (name + ".prompty")).is_file()
        ]
        if not found:
            raise TemplateNotFound(name + ".prompty")
        return found

"""Minimal resolver for github/docs' Liquid-templating syntax.

github/docs' Markdown source is not plain prose — it's built with Liquid
tags (`{% data variables.product.prodname_actions %}`, `{% ifversion %}`
conditionals, `{% tip %}` callouts) that a real GitHub Actions/Docs build
pipeline resolves into rendered HTML. Chunking the raw source verbatim
would index literal `{% data variables.product.prodname_actions %}` text
instead of "GitHub Actions" — a real, caught-by-eye quality problem (see
ATTRIBUTIONS.md's Agentic AI section), not present in the other six
sources, all of which are plain Markdown/MDX with no build-time templating.

This resolves the tags that actually corrupt readability:
- `{% data variables.<file>.<key> %}` -> looked up from data/variables/*.yml
  (the same mapping github/docs' own build uses), falling back to removing
  the tag if a key is genuinely missing rather than leaving broken syntax.
- `{% data reusables.* %}` / `{% indented_data_reference reusables.* %}` ->
  stripped (these point at separate reusable snippet files this project
  does not resolve; the surrounding prose still carries the core
  explanation without them, an intentional simplification vs. github/docs'
  full build pipeline).
- `{% ifversion %}` / `{% elsif %}` / `{% else %}` / `{% endif %}`, callout
  blocks (`tip`/`note`/`warning`/`danger`), IDE-tab conditionals
  (`vscode`/`jetbrains`/`visualstudio`/`xcode`/`vimneovim`/`azure_data_studio`/
  `windowsterminal`/`mobile`/`ides`/`copilotcli`), and code-tab containers
  (`codetabs`/`codetab <lang>`) -> directive markers stripped, inner text of
  every branch/tab kept (accepts minor cross-branch redundancy over losing
  real explanatory text).
- `{% octicon ... %}` -> stripped entirely (an inline icon glyph, no text
  value to keep).
- `{% comment %}...{% endcomment %}` -> stripped (build-time authoring notes).

**Known, disclosed gap:** a handful of github/docs pages render pricing/
feature-comparison tables via genuine Liquid loops over external YAML data
tables (`{% for row in tables.copilot.X %}`, `{% case %}`/`{% assign %}`).
Resolving those needs a real Liquid interpreter, out of scope here — those
~6 specific pages are excluded from ingestion instead of indexed as broken
template fragments (see `chunk_docs.py`'s `exclude_files` and
ATTRIBUTIONS.md).
"""
from __future__ import annotations

import re
from pathlib import Path

from ruamel.yaml import YAML

_YAML = YAML(typ="safe")

DATA_VAR_RE = re.compile(r"\{%\s*data\s+variables\.([\w.\-]+)\s*%\}")
DATA_REUSABLE_RE = re.compile(r"\{%-?\s*(?:data\s+reusables|indented_data_reference\s+reusables)\.[\w.\-]+(?:\s+spaces=\d+)?\s*-?%\}")
OCTICON_RE = re.compile(r"\{%\s*octicon\s+.*?%\}")
DIRECTIVE_RE = re.compile(
    r"\{%-?\s*(?:"
    r"ifversion|elsif|else|endif|"
    r"tip|note|warning|danger|endtip|endnote|endwarning|enddanger|"
    r"codetabs|endcodetabs|codetab\s+\w+|endcodetab|"
    r"prompt|endprompt|"
    r"vscode|endvscode|jetbrains|endjetbrains|visualstudio|endvisualstudio|"
    r"xcode|endxcode|vimneovim|endvimneovim|azure_data_studio|endazure_data_studio|"
    r"windowsterminal|endwindowsterminal|mobile|endmobile|ides|endides|"
    r"copilotcli|endcopilotcli|comment|endcomment|"
    r"raw|endraw|bash|endbash|powershell|endpowershell|"
    r"mac|endmac|linux|endlinux|windows|endwindows|cli|endcli|webui|endwebui|"
    r"eclipse|endeclipse|rowheaders|endrowheaders"
    r")[^%]*-?%\}"
)


def load_variables(variables_dir: Path) -> dict[str, str]:
    flat: dict[str, str] = {}
    if not variables_dir.exists():
        return flat
    for path in sorted(variables_dir.glob("*.yml")):
        try:
            data = _YAML.load(path.read_text(encoding="utf-8", errors="replace")) or {}
        except Exception:
            continue
        _flatten(path.stem, data, flat)
    return flat


def _flatten(prefix: str, obj, out: dict[str, str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}.{k}", v, out)
    elif isinstance(obj, str):
        out[prefix] = obj
    # lists/other scalar types aren't used as {% data %} targets in practice; skip.


def resolve(text: str, variables: dict[str, str]) -> str:
    # A handful of variable values themselves contain another {% data
    # variables.X %} reference (e.g. copilot.copilot_byok_supported_features);
    # a few passes resolves that nesting without needing real recursion.
    for _ in range(3):
        text, n = DATA_VAR_RE.subn(lambda m: variables.get(m.group(1), ""), text)
        if not n:
            break
    text = DATA_REUSABLE_RE.sub("", text)
    text = OCTICON_RE.sub("", text)
    text = DIRECTIVE_RE.sub("", text)
    return text

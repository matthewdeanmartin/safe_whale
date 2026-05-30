"""Browser-hosted Python app scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
import shlex
import webbrowser
from pathlib import Path
from typing import Literal

from safe_whale.storage import pyodide_apps_dir

PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.29.4/full/pyodide.mjs"
PYSCRIPT_CORE_JS = "https://pyscript.net/releases/2026.3.1/core.js"
PYSCRIPT_CORE_CSS = "https://pyscript.net/releases/2026.3.1/core.css"
BrowserPythonRuntime = Literal["pyodide", "pyscript"]

DEMO_PACKAGE = "snowballstemmer"
DEMO_ARGS = "running containers safely"
DEMO_CODE = """try:
    from pyscript import display
except Exception:
    display = print

try:
    words = SAFE_WHALE_ARGS.to_py()
except AttributeError:
    words = list(SAFE_WHALE_ARGS)
except NameError:
    words = ["running", "containers", "safely"]

import snowballstemmer

stemmer = snowballstemmer.stemmer("english")
stems = stemmer.stemWords(words)
display("snowballstemmer demo")
display("input:  " + ", ".join(words))
display("stems:  " + ", ".join(stems))
"""


@dataclass(frozen=True)
class BrowserPyodideConfig:
    """Configuration for a browser-hosted Python app."""

    code: str
    package_spec: str = ""
    cli_args: str = ""
    name: str = "pyodide-terminal"
    runtime: BrowserPythonRuntime = "pyodide"


@dataclass(frozen=True)
class BrowserPyodideApp:
    """Generated browser app metadata."""

    directory: Path
    index_path: Path
    url: str
    runtime: BrowserPythonRuntime


def create_browser_pyodide_app(cfg: BrowserPyodideConfig, root: Path | None = None) -> BrowserPyodideApp:
    """Create a static browser Python app and return its launch path."""
    base = root or pyodide_apps_dir()
    directory = base / _app_dir_name(cfg)
    directory.mkdir(parents=True, exist_ok=True)
    index_path = directory / "index.html"
    index_path.write_text(_render_index(cfg), encoding="utf-8")
    return BrowserPyodideApp(
        directory=directory,
        index_path=index_path,
        url=index_path.resolve().as_uri(),
        runtime=cfg.runtime,
    )


def open_browser_pyodide_app(app: BrowserPyodideApp) -> bool:
    """Open a generated Pyodide browser app in the user's default browser."""
    return webbrowser.open(app.url)


def _app_dir_name(cfg: BrowserPyodideConfig) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", cfg.name.strip()).strip("-") or "browser-python"
    digest_input = "\n".join([cfg.runtime, cfg.name, cfg.package_spec, cfg.cli_args, cfg.code])
    digest = hashlib.sha1(digest_input.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    return f"{cfg.runtime}-{safe_name}-{digest}"


def _render_index(cfg: BrowserPyodideConfig) -> str:
    if cfg.runtime == "pyscript":
        return _render_pyscript_index(cfg)
    return _render_pyodide_index(cfg)


def _render_pyodide_index(cfg: BrowserPyodideConfig) -> str:
    package_specs = _split_packages(cfg.package_spec)
    payload = {
        "code": cfg.code,
        "packageSpec": cfg.package_spec,
        "packageSpecs": package_specs,
        "args": _split_args(cfg.cli_args),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "pyodideUrl": PYODIDE_CDN,
    }
    payload_json = json.dumps(payload).replace("</", "<\\/")
    title = _escape_html(cfg.name or "Pyodide Terminal")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      background: #101216;
      color: #e8edf2;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }}
    header, footer {{
      padding: 12px 16px;
      background: #181b21;
      border-color: #2d333d;
    }}
    header {{ border-bottom: 1px solid #2d333d; }}
    footer {{ border-top: 1px solid #2d333d; color: #aeb8c4; }}
    main {{
      display: grid;
      grid-template-columns: minmax(280px, 35%) 1fr;
      min-height: 0;
    }}
    .editor, .terminal {{
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 12px;
    }}
    .editor {{ border-right: 1px solid #2d333d; background: #141820; }}
    label {{ display: grid; gap: 4px; color: #cbd5e1; font-size: 13px; }}
    input, textarea, button {{
      font: inherit;
      border: 1px solid #384150;
      background: #0d1117;
      color: #eef4fb;
      border-radius: 6px;
    }}
    input {{ padding: 8px; }}
    textarea {{
      flex: 1;
      min-height: 260px;
      padding: 10px;
      resize: none;
      line-height: 1.45;
    }}
    button {{
      padding: 8px 12px;
      cursor: pointer;
      background: #235789;
      border-color: #2f6ea8;
    }}
    button:disabled {{ opacity: .55; cursor: wait; }}
    #term {{
      flex: 1;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      background: #05070a;
      border: 1px solid #384150;
      border-radius: 6px;
      padding: 12px;
      line-height: 1.45;
    }}
    @media (max-width: 760px) {{
      main {{ grid-template-columns: 1fr; }}
      .editor {{ border-right: 0; border-bottom: 1px solid #2d333d; }}
    }}
  </style>
</head>
<body>
  <header>
    <strong>{title}</strong>
  </header>
  <main>
    <section class="editor">
      <label>Package spec
        <input id="packageSpec" autocomplete="off">
      </label>
      <label>Args
        <input id="args" autocomplete="off">
      </label>
      <label>Python
        <textarea id="code" spellcheck="false"></textarea>
      </label>
      <button id="run">Run</button>
    </section>
    <section class="terminal">
      <div id="term" role="log" aria-live="polite"></div>
    </section>
  </main>
  <footer>
    Browser-hosted Pyodide runs Python in WebAssembly. It cannot provide Tkinter, Docker, native wheels, or local web servers.
  </footer>
  <script id="safe-whale-payload" type="application/json">{payload_json}</script>
  <script type="module">
    const payload = JSON.parse(document.getElementById("safe-whale-payload").textContent);
    const term = document.getElementById("term");
    const run = document.getElementById("run");
    const packageSpec = document.getElementById("packageSpec");
    const args = document.getElementById("args");
    const code = document.getElementById("code");
    packageSpec.value = payload.packageSpec || "";
    args.value = (payload.args || []).join(" ");
    code.value = payload.code || "";

    let pyodidePromise;

    function write(text = "") {{
      term.textContent += text + "\\n";
      term.scrollTop = term.scrollHeight;
    }}

    async function pyodide() {{
      if (!pyodidePromise) {{
        write("$ booting Pyodide");
        const mod = await import(payload.pyodideUrl);
        pyodidePromise = mod.loadPyodide({{
          stdout: (text) => write(text),
          stderr: (text) => write(text),
        }});
      }}
      return pyodidePromise;
    }}

    async function runCode() {{
      run.disabled = true;
      term.textContent = "";
      try {{
        const py = await pyodide();
        const currentArgs = args.value.trim() ? args.value.trim().split(/\\s+/) : [];
        py.globals.set("SAFE_WHALE_ARGS", currentArgs);
        const packages = packageSpec.value.trim() ? packageSpec.value.trim().split(/\\s+/) : [];
        if (packages.length) {{
          write("$ installing " + packages.join(", "));
          await py.loadPackage("micropip");
          const micropip = py.pyimport("micropip");
          await micropip.install(packages);
        }}
        write("$ python");
        await py.runPythonAsync(code.value);
        write("[done]");
      }} catch (err) {{
        write("[error] " + (err && err.stack ? err.stack : err));
      }} finally {{
        run.disabled = false;
      }}
    }}

    run.addEventListener("click", runCode);
    runCode();
  </script>
</body>
</html>
"""


def _render_pyscript_index(cfg: BrowserPyodideConfig) -> str:
    package_specs = _split_packages(cfg.package_spec)
    config_json = _script_attr_json({"packages": package_specs}) if package_specs else "{}"
    args_json = json.dumps(_split_args(cfg.cli_args)).replace("</", "<\\/")
    title = _escape_html(cfg.name or "PyScript App")
    code = _escape_script_text(f"SAFE_WHALE_ARGS = {args_json}\n{cfg.code}")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="{PYSCRIPT_CORE_CSS}">
  <script type="module" src="{PYSCRIPT_CORE_JS}"></script>
  <style>
    :root {{
      color-scheme: dark;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      background: #101216;
      color: #e8edf2;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }}
    header, footer {{
      padding: 12px 16px;
      background: #181b21;
      border-color: #2d333d;
    }}
    header {{ border-bottom: 1px solid #2d333d; }}
    footer {{ border-top: 1px solid #2d333d; color: #aeb8c4; }}
    main {{
      padding: 16px;
      display: grid;
      gap: 12px;
    }}
    #output {{
      min-height: 280px;
      white-space: pre-wrap;
      word-break: break-word;
      background: #05070a;
      border: 1px solid #384150;
      border-radius: 6px;
      padding: 12px;
      line-height: 1.45;
    }}
    details {{
      border: 1px solid #384150;
      border-radius: 6px;
      background: #141820;
      padding: 10px;
    }}
    pre {{
      overflow: auto;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>
  <header>
    <strong>{title}</strong>
  </header>
  <main>
    <div id="output" role="log" aria-live="polite"></div>
    <details>
      <summary>Python source</summary>
      <pre>{_escape_html(cfg.code)}</pre>
    </details>
    <script type="py" target="output" config='{config_json}'>
{code}
    </script>
  </main>
  <footer>
    Browser-hosted PyScript uses Pyodide for PyPI packages. It cannot provide Tkinter, Docker, native wheels, or local web servers.
  </footer>
</body>
</html>
"""


def _split_args(value: str) -> list[str]:
    try:
        return shlex.split(value)
    except ValueError:
        return [part for part in value.split() if part]


def _split_packages(value: str) -> list[str]:
    return _split_args(value)


def _script_attr_json(value: object) -> str:
    return _escape_html(json.dumps(value).replace("</", "<\\/"))


def _escape_script_text(value: str) -> str:
    return value.replace("</script", "<\\/script").replace("</SCRIPT", "<\\/SCRIPT")


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )

"""sync_relay core: one hook script for Claude Code and Codex (`python3 sync_relay.py claude|codex`).

The main interactive session only orchestrates; work goes to subagents. Standard library only, Python >= 3.9.

- PreToolUse: denies work tools in the main interactive session (mode `enforce`). Subagents (`agent_id`),
  automation (`claude -p`, `codex exec`) and orchestration tools pass. Also let through: Bash matching `read_commands` (ONE simple
  command, no shell metacharacter), small Read, and `allowed_commands` of <repo>/.claude/sync_relay.json (only loosens).
- UserPromptSubmit: short reminder per message; the word `relay` (whole message, `/` optional) asks for the handoff file.
  `relay off|remind|on` (whole message) sets the lock mode of THIS session (file `_modo-<key>.txt`, key = CLAUDE_PID or
  session id); precedence session > SYNC_RELAY_MODE > config. SYNCLABS_RELAY_* still work until 0.4.0 (one notice).
- SessionStart: routing table (from config) for the main session; delivers a pending handoff to a new session
  (`startup`/`clear`), the only one that does in both CLIs (the band mod only triggers the switch); deletes handoff
  files older than 7 days.
- Stop: warns at the switch point, floor + min(D, 0.8 x (C - floor)): D = `threshold_tokens` (default 150k), C = the CLI's
  auto-compaction point (see compactacao); not while a subagent runs.
- SubagentStop: asks once for a shorter report when it passes `report_max_chars`. Holds a subagent (block, at most 2x) while a
  shell or monitor background task still runs.

Config: see README (file `sync_relay/config.json`; env SYNC_RELAY_MODE / _LANG / _CONFIG win over it).
Any error: do nothing (fail open). Output is ASCII JSON: under a pipe the Windows stdout is cp1252.
"""
import json
import locale
import ntpath
import os
import posixpath
import re
import shutil
import stat
import sys
import time
from fnmatch import fnmatchcase
from pathlib import Path

LIVRES = {
    # Claude Code
    "Agent", "Task", "SendMessage", "ListAgents", "AskUserQuestion", "TaskCreate", "TaskUpdate",
    "TaskList", "TaskGet", "TaskStop", "TaskOutput", "ToolSearch", "Skill", "Workflow",
    "ReadNotifications", "ScheduleWakeup", "SendUserFile", "PushNotification", "EnterPlanMode",
    "ExitPlanMode", "CronCreate", "CronList", "CronDelete", "EndConversation", "TodoWrite",
    "SendUserMessage", "TeamCreate", "SendFeedback",  # SendFeedback drafts a local report, sends nothing
    "REPL",  # Code Mode wrapper: each inner tools.X() call fires its own PreToolUse with the real name, still judged
    "Poll",  # Code Mode: waits for the result of the REPL or of a background agent
    # Codex
    "spawn_agent", "wait_agent", "wait", "send_input", "send_message", "followup_task", "list_agents",
    "interrupt_agent", "close_agent", "resume_agent", "update_plan", "request_user_input",
}
CAMADAS = ("lookup", "judgment", "build", "hard", "plan")


def _camada(claude, codex):
    return {"claude": dict(claude), "codex": dict(codex)}


PADRAO = {
    "mode": "enforce",
    "lang": "auto",
    "threshold_tokens": 150000,  # optional in the file: absent = this value
    "button": True,  # read by the band only (fixed button above the prompt); here so the shared file stays valid
    "stop_warning": True,
    "report_max_chars": 4000,
    "handoff_dir": "",
    "allowed_tools": [],
    "allow_reads": True,  # false turns off read_commands and the Read exception (not the repo file)
    # The seed of the lock's read exception: a starting point, not a rule hidden in the code. Whole command, token by token:
    # `*` as a token = one word (the last token = one or more words), inside a token = any characters; `!x` = deny when
    # any argument matches x. Replace or empty it in the config; the fixed part is only the shell-structure check.
    "read_commands": ["git status", "git status *", "git log", "git log *", "git diff --stat", "git diff --stat *",
                      "git diff --name-only", "git diff --name-only *", "git branch", "ls", "ls *", "pwd",
                      "cat *", "head *", "tail *", "* status", "* --version",
                      "!-o", "!--ou*", "!-f*", "!-F*", "!-[!-]*f*", "!-[!-]*F*", "!--follow*"],
    "read_max_kb": 64,  # cat/head/tail/Read of a file over this are not read exceptions
    "read_max_lines": 200,  # Read with `limit` up to this is allowed whatever the file size
    "codex_interactive_originators": ["codex-tui", "codex_work_desktop"],  # measured in real rollouts
    "routing": {  # model None = do not pass a model, the subagent inherits the session's
        "lookup": _camada({"agent": "Explore", "model": "haiku", "effort": "low"},
                          {"agent": "explorer", "model": None, "effort": "low"}),
        "judgment": _camada({"agent": "general-purpose", "model": "sonnet", "effort": "medium"},
                            {"agent": "explorer", "model": None, "effort": "medium"}),
        "build": _camada({"agent": "general-purpose", "model": "sonnet", "effort": "medium"},
                         {"agent": "worker", "model": None, "effort": "medium"}),
        "hard": _camada({"agent": "general-purpose", "model": "opus", "effort": "high"},
                        {"agent": "worker", "model": None, "effort": "high"}),
        "plan": _camada({"agent": "general-purpose", "model": "opus", "effort": "xhigh"},
                        {"agent": "worker", "model": None, "effort": "high"}),
    },
}
MODOS = ("enforce", "remind", "off")
EVENTOS = {"PreToolUse", "UserPromptSubmit", "SessionStart", "Stop", "SubagentStop"}
PALAVRAS_HANDOFF = {"relay"}
INICIO_HANDOFF = {"startup", "clear"}  # fork, resume and compact never consume a handoff
VIDA_ARQUIVO = 7 * 86400
# slug() is [a-z0-9-] and never starts with '-': names have no separator and no other dot
NOME_DO_PLUGIN = re.compile(r"[a-z0-9-]+(\.usada)?\.md")  # only in the default folder
# underscore files: the plugin's own, cleaned in ANY folder (a configured one may hold the user's notes, never these)
NOME_SUBLINHADO = re.compile(r"_req-[0-9]+\.txt|_detect-[^/\\]+\.flag|_trace-[0-9a-f]{8}\.md"
                             r"|_modo-[ps][A-Za-z0-9]+\.txt|_(?:repo|alias)-[ps][A-Za-z0-9]+\.flag|_sub-[A-Za-z0-9_-]{1,64}\.n")
ALIAS_ANTIGOS = ("MODE", "LANG", "CONFIG")  # SYNCLABS_RELAY_<X> worked before 0.2.0; out in 0.4.0
MODOS_SESSAO = {"off": "off", "remind": "remind", "on": "enforce"}  # what the user types -> what is stored
MAX_BLOCOS_SUB = 2  # a subagent is held at most this many times for a background task
NAO_E_COMANDO_SIMPLES = re.compile(r"[|;&<>`$()\r\n]")  # the one fixed rule of the read exception: one simple command
FIM_DE_TAREFA = {"completed", "failed", "killed", "cancelled", "stopped"}
VALIDADE_PERMISSAO = 10 * 60  # the marker is fresh only while the handoff it asked for is being written
VALIDADE_HANDOFF = 30 * 60  # asked and switched right away; older belongs to another conversation
LIMITE_CONTEXTO = 9000  # hooks doc: additionalContext over 10,000 chars becomes a file path + 2,000-char preview
MAX_HANDOFF = 8000
JANELA_200K = 200000
JANELA_1M = 967000  # auto-compaction point of a 1M window (doc: model-config)
JANELA_MIN = 100000  # CLAUDE_CODE_AUTO_COMPACT_WINDOW and autoCompactWindow: the doc's minimum
MIN_1M = {"opus": (4, 7), "sonnet": (5, 0), "haiku": (5, 5)}  # first version with the 1M window by default


# ---------- config ----------
def _join(nt):
    return (ntpath if nt else posixpath).join


def caminho_config(env, home, nt):
    if env.get("SYNC_RELAY_CONFIG"):
        return env["SYNC_RELAY_CONFIG"]
    j = _join(nt)
    base = env.get("XDG_CONFIG_HOME") or (env.get("APPDATA") if nt else None) or j(home, ".config")
    return j(base, "sync_relay", "config.json")


def _str_ou_none(v):
    return v is None or isinstance(v, str)


def mesclar(user):
    """Defaults + user config, key by key (routing: layer by layer). Wrong types and unknown keys are ignored."""
    c = json.loads(json.dumps(PADRAO))
    if not isinstance(user, dict):
        return c
    for k, v in user.items():
        if k == "routing" and isinstance(v, dict):
            for camada, por_cli in v.items():
                for cli, r in (por_cli.items() if camada in CAMADAS and isinstance(por_cli, dict) else ()):
                    if cli in c["routing"][camada] and isinstance(r, dict):
                        for campo, val in r.items():
                            if campo in ("agent", "effort") and isinstance(val, str) and val:
                                c["routing"][camada][cli][campo] = val
                            elif campo == "model" and _str_ou_none(val):
                                c["routing"][camada][cli][campo] = val or None
        elif k in PADRAO and k != "routing" and type(v) is type(PADRAO[k]):
            if k == "mode" and v not in MODOS:
                continue
            if k in ("threshold_tokens", "read_max_kb", "read_max_lines") and v <= 0:
                continue
            if k in ("allowed_tools", "codex_interactive_originators", "read_commands") and not all(isinstance(x, str) for x in v):
                continue
            c[k] = v
    return c


def migrar_config(env, home, nt):
    """0.2.0: the product was renamed; copy the old config (synclabs-relay) to the new place once, never over a new one.
    shortcut: runs on every read until the new file exists, drop it in 0.3.0."""
    novo = caminho_config(env, home, nt)
    if env.get("SYNC_RELAY_CONFIG") or os.path.exists(novo):
        return
    m = ntpath if nt else posixpath
    antigo = m.join(m.dirname(m.dirname(novo)), "synclabs-relay", "config.json")
    try:
        if os.path.isfile(antigo):
            os.makedirs(os.path.dirname(novo), exist_ok=True)
            shutil.copyfile(antigo, novo)
    except OSError:
        pass  # cannot copy: the default config applies, as with any unreadable file


def ler_config(env, home, nt):
    migrar_config(env, home, nt)
    try:
        with open(caminho_config(env, home, nt), encoding="utf-8-sig") as f:  # utf-8-sig drops a BOM
            return mesclar(json.load(f))
    except (OSError, ValueError, RecursionError):  # deeply nested JSON: default config, lock stays on
        return mesclar(None)


def aliasar(env):
    """(env, names used): a SYNCLABS_RELAY_<X> stands in for SYNC_RELAY_<X> only when the new one is not set.
    shortcut: runs on every call; remove with the aliases in 0.4.0."""
    novo, usados = dict(env), []
    for x in ALIAS_ANTIGOS:
        if env.get("SYNCLABS_RELAY_" + x):
            usados.append("SYNCLABS_RELAY_" + x)
            if not env.get("SYNC_RELAY_" + x):
                novo["SYNC_RELAY_" + x] = env["SYNCLABS_RELAY_" + x]
    return novo, usados


def modo(cfg, env, sessao=None):
    """Session mode (typed by the user) > SYNC_RELAY_MODE > config. `on` in a session keeps `force` if the env asked for it."""
    m = env.get("SYNC_RELAY_MODE")
    m = m if m in ("off", "remind", "enforce", "force") else None
    if sessao:
        return "force" if sessao == "enforce" and m == "force" else sessao
    return m or cfg["mode"]


def pasta_configurada(valor, env, home, nt):
    """The configured handoff_dir if valid, else None. One rule, repeated by the band (tests/vectors/paths.json):
    '~' at the start expands to home; Windows needs a drive (C:\\ or C:/) or UNC (\\\\srv\\share), POSIX a '/';
    no '..' segment (Windows strips trailing dots and spaces, so '.. ' and '...' count). No isabs: it changed in 3.13."""
    d = valor
    if d == "~" or d[:2] in ("~/", "~\\"):
        d = (env.get("USERPROFILE" if nt else "HOME") or home) + d[1:]
    ok = re.match(r"[A-Za-z]:[\\/]|\\\\[^\\/]+\\[^\\/]", d) if nt else d.startswith("/")
    if ok and not any(re.fullmatch(r"\.\.[. ]*", p) for p in re.split(r"[\\/]", d)):
        return d
    return None


def handoff_dir(cfg, env, home, nt):
    if cfg.get("handoff_dir"):
        d = pasta_configurada(cfg["handoff_dir"], env, home, nt)
        if d:
            return d  # anything else falls to the default folder
    j = _join(nt)
    if nt:
        return j(env.get("LOCALAPPDATA") or j(home, "AppData", "Local"), "sync_relay", "handoffs")
    return j(env.get("XDG_STATE_HOME") or j(home, ".local", "state"), "sync_relay", "handoffs")


# ---------- i18n ----------
def lang_conhecido(v):
    """pt, pt-br, pt_BR, pt-* -> pt-BR; en, en-*, en_* -> en (any case); anything else None. The band repeats this."""
    m = re.fullmatch(r"(pt|en)(?:[-_].*)?", v.lower(), re.S) if isinstance(v, str) else None
    return None if not m else "pt-BR" if m.group(1) == "pt" else "en"


def escolher_lang(cfg_lang, env, getlocale=locale.getlocale):
    """The env var wins only if it names a language we know; then the config; then the system."""
    for v in (env.get("SYNC_RELAY_LANG"), cfg_lang):
        if lang_conhecido(v):
            return lang_conhecido(v)
    for k in ("LC_ALL", "LC_MESSAGES", "LANG"):  # POSIX precedence; the first one set wins
        if env.get(k):
            return "pt-BR" if env[k].lower().startswith("pt") else "en"
    try:
        loc = (getlocale()[0] or "").lower()  # Windows: no LANG, the locale module knows
    except (ValueError, TypeError):
        loc = ""
    return "pt-BR" if loc.startswith(("pt", "portuguese")) else "en"


def _carregar(nome):
    try:
        with open(Path(__file__).resolve().parent.parent / "messages" / (nome + ".json"), encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def mensagem(lang_msgs, en_msgs, chave):
    """Key missing in the chosen language falls back to English."""
    return lang_msgs.get(chave) or en_msgs.get(chave) or ""


def fmt(texto, **kw):
    try:
        return texto.format(**kw)
    except (KeyError, IndexError, ValueError):
        return texto


class Textos:
    def __init__(self, lang):
        self.en = _carregar("en")
        self.lang = self.en if lang == "en" else _carregar(lang)

    def __call__(self, chave, **kw):
        return fmt(mensagem(self.lang, self.en, chave), **kw)


# ---------- handoff folder ----------
def fnv1a(texto):
    """FNV-1a 32 bits over the UTF-8 bytes, 8 lowercase hex digits (no crypto needed in the band's runtime)."""
    h = 0x811C9DC5
    for b in texto.encode("utf-8", "replace"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return "%08x" % h


def normalizar_cwd(cwd, nt):
    """The path as it came; on Windows lowercase and '/' -> '\\'; no trailing separator (a root keeps it)."""
    if nt:
        cwd = cwd.lower().replace("/", "\\")
    sep = "\\" if nt else "/"
    while len(cwd) > 1 and cwd[-1] == sep and not (nt and re.fullmatch(r"[a-z]:\\", cwd)):
        cwd = cwd[:-1]
    return cwd


def slug(cwd, nt=os.name == "nt"):
    """Handoff file name base for a directory: <readable part>-<h8>. The readable part is the lowercase path with
    runs of non [a-z0-9] as '-', the last 60 chars; h8 is the hash of the normalized path, so my_app, my-app and
    My App never share a file. The band mod repeats this: tests/vectors/paths.json locks both."""
    c = normalizar_cwd(cwd or "", nt)
    legivel = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")[-60:].lstrip("-")
    return legivel + "-" + fnv1a(c) if legivel else fnv1a(c)


def nome_handoff(cwd, sid, cli):
    """Claude: one file per session (<slug>-<id[:8]>.md, the band mod repeats this), so two sessions in the same
    folder do not swap handoffs. Codex: <slug>.md."""
    return slug(cwd or "") + ("-" + sid[:8] if cli == "claude" and sid else "") + ".md"


_CONFIG_DIR = None  # the user's handoff_dir of this run; pasta_segura never changes its mode (shortcut: module state, one hook call per process; pass a parameter if the core ever gets long-lived)


def escolher_pasta(cfg, env, home, nt, criar):
    """Configured folder; if it exists unusable (or cannot be created when criar) the default one."""
    global _CONFIG_DIR
    cand, padrao = handoff_dir(cfg, env, home, nt), handoff_dir({}, env, home, nt)
    _CONFIG_DIR = cand if cand != padrao else None
    if cand != padrao and (criar or os.path.lexists(cand)) and pasta_segura(cand, criar) is None:
        return padrao
    return cand


def dono_e_modo(st, euid, chmod, apertar=True):
    """POSIX: False if the folder is not ours; else, in the default folder (apertar), closes group and other (0700)
    when they have any bit. The band's $.fs.write creates it with the engine's mode: tighten, never trust. A folder
    the user configured keeps its mode: protecting it is up to the user."""
    if st.st_uid != euid:
        return False
    if apertar and st.st_mode & 0o077:
        chmod(0o700)
    return True


def pasta_segura(pasta, criar):
    """The handoff folder if it is a real directory of this user (never a symlink or junction), else None."""
    try:
        try:
            st = os.lstat(pasta)
        except FileNotFoundError:
            if not criar:
                return None
            os.makedirs(pasta, mode=0o700, exist_ok=True)
            st = os.lstat(pasta)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode) or getattr(os.path, "isjunction", lambda _: False)(pasta):
            return None
        if hasattr(os, "geteuid") and not dono_e_modo(st, os.geteuid(), lambda m: os.chmod(pasta, m), pasta != _CONFIG_DIR):
            return None
        return pasta
    except OSError:
        return None


def limpar(pasta, padrao):
    """Deletes older than 7 days, in the handoff folder (no recursion), only names this plugin writes: the
    underscore files (_req-N.txt, _detect-*.flag, _trace-<id8>.md) in any folder, and <slug>[-<id8>][.usada].md only
    when padrao (the default folder is dedicated to the plugin; a configured one may hold notes named like a slug).
    Locked file: skip."""
    try:
        for e in os.scandir(pasta):
            try:
                if ((NOME_SUBLINHADO.fullmatch(e.name) or (padrao and NOME_DO_PLUGIN.fullmatch(e.name)))
                        and e.is_file(follow_symlinks=False)
                        and time.time() - e.stat().st_mtime > VIDA_ARQUIVO):
                    os.remove(e.path)
            except OSError:
                pass
    except OSError:
        pass


def escrita_do_handoff(d, pasta):
    """Write allowed only to <handoff folder>/*.md, directly in it (no subfolder, no '..', no symlink)."""
    f = (d.get("tool_input") or {}).get("file_path")
    if d.get("tool_name") != "Write" or not isinstance(f, str) or not f or not os.path.isabs(f):
        return False
    if pasta_segura(pasta, False) is None:
        return False
    alvo = os.path.normcase(os.path.abspath(f))
    nome = os.path.basename(alvo)
    # ":" in the name = NTFS alternate stream (a.txt:x.md)
    if os.path.dirname(alvo) != os.path.normcase(os.path.abspath(pasta)) or not nome.endswith(".md") or ":" in nome:
        return False
    try:
        return not stat.S_ISLNK(os.lstat(alvo).st_mode)
    except FileNotFoundError:
        return True
    except OSError:
        return False


def permite_passagem(d, pasta, env):
    """True only for the Write of this session's own handoff file: main session, Write, CLAUDE_PID with a fresh
    `_req-<PID>.txt` whose content (<slug of cwd>-<8hex>.md, written by the core) is exactly the file name, in the
    handoff folder, no '..', no ADS, not a link, content within MAX_HANDOFF. Anything else: no opinion."""
    ti = d.get("tool_input")
    f, texto = (ti.get("file_path"), ti.get("content")) if isinstance(ti, dict) else (None, None)
    pid = env.get("CLAUDE_PID") or ""
    if (d.get("agent_id") or d.get("tool_name") != "Write" or not re.fullmatch(r"[0-9]{1,10}", pid)
            or not isinstance(f, str) or not os.path.isabs(f) or not isinstance(texto, str) or len(texto) > MAX_HANDOFF
            or pasta_segura(pasta, False) is None):
        return False
    if ".." in re.split(r"[\\/]", f) or ":" in os.path.splitdrive(f)[1]:
        return False
    try:
        m = os.path.join(pasta, "_req-%s.txt" % pid)
        st = os.lstat(m)
        if not stat.S_ISREG(st.st_mode) or time.time() - st.st_mtime > VALIDADE_PERMISSAO:
            return False
        with open(m, encoding="utf-8") as fh:
            nome = fh.read().strip()
        if not re.fullmatch(re.escape(slug(d.get("cwd") or "")) + r"-[0-9a-f]{8}\.md", nome):
            return False
        alvo = os.path.normcase(os.path.abspath(f))
        if alvo != os.path.normcase(os.path.abspath(os.path.join(pasta, nome))):
            return False
        try:
            return not stat.S_ISLNK(os.lstat(alvo).st_mode)
        except FileNotFoundError:
            return True
    except (OSError, ValueError):
        return False


# ---------- session type ----------
def sessao_codex(transcript):
    """Rollout header (1st line): originator and source. Empty if unreadable. Never prints the header."""
    try:
        with open(transcript, encoding="utf-8", errors="replace") as f:
            meta = json.loads(f.readline())["payload"]
        return meta if isinstance(meta, dict) else {}
    except (OSError, TypeError, ValueError, KeyError):
        return {}


def tipo_sessao(d, cli, cfg, env, forcar, ignorar_sub=False):
    """True = main interactive session; False = subagent or automation; None = cannot tell (fail open)."""
    if not ignorar_sub and d.get("agent_id"):
        return False
    if forcar:
        return True
    if cli == "claude":
        ep = env.get("CLAUDE_CODE_ENTRYPOINT", "")
        return None if not ep else not ep.startswith("sdk")  # claude -p and the SDK arrive as sdk-*
    meta = sessao_codex(d.get("transcript_path"))
    orig = meta.get("originator")
    if not isinstance(orig, str) or not orig:
        return None
    if not ignorar_sub and isinstance(meta.get("source"), dict):  # Codex subagent: inherits originator, source is an object
        return False
    return orig in cfg["codex_interactive_originators"]


def marcar(pasta, nome):
    """True only the first time this marker file is created in the handoff folder."""
    if pasta_segura(pasta, True) is None:
        return False
    try:
        os.close(os.open(os.path.join(pasta, nome), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return True
    except OSError:
        return False


def avisar_uma_vez(d, pasta):
    """True only the first time per session id (marker file in the handoff folder)."""
    sid = re.sub(r"[^A-Za-z0-9]", "", str(d.get("session_id") or ""))[:24] or "nosid"
    return marcar(pasta, "_detect-" + sid + ".flag")


# ---------- mode of one session (v0.2.1) ----------
def chave_sessao(d, cli, env):
    """Claude: the process (CLAUDE_PID is the same across /clear, the session id is not); else the session id. The mod
    repeats this rule (hooks/register.tsx): `p<pid>` or `s<id, letters and digits, 24>`; None = no way to tell."""
    pid = env.get("CLAUDE_PID") or ""
    if cli == "claude" and re.fullmatch(r"[0-9]{1,10}", pid):
        return "p" + pid
    sid = re.sub(r"[^A-Za-z0-9]", "", str(d.get("session_id") or ""))[:24]
    return "s" + sid if sid else None


def modo_da_sessao(chave, pasta):
    """off, remind or enforce as the user set it for this session; None if none. Touches an old file so a session
    open for days keeps it out of the weekly cleanup."""
    if not chave or pasta_segura(pasta, False) is None:
        return None
    f = os.path.join(pasta, "_modo-%s.txt" % chave)
    try:
        st = os.lstat(f)
        if not stat.S_ISREG(st.st_mode):
            return None
        with open(f, encoding="utf-8") as fh:
            v = fh.read(16).strip()
        if time.time() - st.st_mtime > 86400:
            os.utime(f)
        return v if v in MODOS_SESSAO.values() else None
    except OSError:
        return None


def gravar_modo(chave, pasta, valor):
    if not chave or pasta_segura(pasta, True) is None:
        return False
    try:
        with open(os.path.join(pasta, "_modo-%s.txt" % chave), "w", encoding="utf-8") as f:
            f.write(valor)
        return True
    except OSError:
        return False


# ---------- what the lock lets through on the main session (v0.2.1) ----------
def _padrao_vale(p):
    return bool(re.search(r"[^\s*?\[\]!]", p))  # a pattern made only of wildcards would free everything


def _casa(tokens, padrao):
    """Token by token (fnmatch inside a token). A last `*` after other tokens stands for one or more words."""
    pt = padrao.split()
    if not pt:
        return False
    if len(pt) > 1 and pt[-1] == "*":
        return len(tokens) >= len(pt) and all(fnmatchcase(t, p) for t, p in zip(tokens, pt[:-1]))
    return len(tokens) == len(pt) and all(fnmatchcase(t, p) for t, p in zip(tokens, pt))


def por_padroes(cmd, padroes, negativos=True):
    """True if the whole command is ONE simple command (no shell metacharacter: the only fixed rule) that matches a
    pattern. `!x` entries (negativos) deny when any argument matches x. shortcut: no quote parsing, so a quoted
    metacharacter is also refused; upgrade only if that gets in the way."""
    if not isinstance(cmd, str) or NAO_E_COMANDO_SIMPLES.search(cmd):
        return False
    tokens = cmd.split()
    if not tokens:
        return False
    if negativos and any(fnmatchcase(t, p[1:]) for p in padroes if p.startswith("!") for t in tokens[1:]):
        return False
    return any(_casa(tokens, p) for p in padroes if not p.startswith("!") and _padrao_vale(p))


def _caminho(arq, cwd):
    return arq if os.path.isabs(arq) else os.path.join(cwd or "", arq)


def arquivo_pequeno(arq, cwd, max_kb):
    """True if the file does not exist (the command fails by itself) or is a regular file up to max_kb."""
    c = _caminho(arq, cwd)
    try:
        st = os.stat(c)
    except OSError:
        return not os.path.exists(c)  # exists but unreadable: no
    return stat.S_ISREG(st.st_mode) and st.st_size <= max_kb * 1024


def tamanho_ok(cmd, cwd, max_kb):
    """cat, head and tail: every file argument within max_kb, and at least one (no file = reads stdin, never ends)."""
    t = cmd.split()
    if os.path.basename(t[0]) not in ("cat", "head", "tail"):
        return True
    args = [a for a in t[1:] if not a.startswith("-")]
    return bool(args) and all(arquivo_pequeno(a, cwd, max_kb) for a in args)  # shortcut: `head -n 5` alone passes (the 5 counts as an argument); upgrade if seen


def leitura_ok(ti, cwd, cfg):
    """Read: `limit` within read_max_lines, or a file within read_max_kb."""
    f = ti.get("file_path")
    if not isinstance(f, str) or not f:
        return False
    lim = ti.get("limit")
    if type(lim) is int and 0 < lim <= cfg["read_max_lines"]:
        return True
    return arquivo_pequeno(f, cwd, cfg["read_max_kb"])


def arquivo_do_repo(cwd):
    """(path, allowed_commands) of the nearest valid .claude/sync_relay.json from cwd up to the git root (cwd only when
    there is no repo). A broken file is ignored. It only loosens the lock."""
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        return None, []
    pastas, atual = [], cwd
    while True:
        pastas.append(atual)
        if os.path.lexists(os.path.join(atual, ".git")):
            break
        pai = os.path.dirname(atual)
        if pai == atual:
            pastas = [cwd]
            break
        atual = pai
    for p in pastas:
        arq = os.path.join(p, ".claude", "sync_relay.json")
        j = _json_dict(arq)
        lista = j.get("allowed_commands") if j else None
        if isinstance(lista, list) and lista and len(lista) <= 100 and all(isinstance(x, str) and x for x in lista):
            return arq, lista
    return None, []


def liberada(d, cfg, pasta, cli, env, t):
    """(True, message or None) when the main session may run this tool call: the read exception (allow_reads) or the
    repo file. The message is the one-time notice of the first release by the repo file."""
    ti = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
    cwd = d.get("cwd") if isinstance(d.get("cwd"), str) else ""
    nome = d.get("tool_name")
    if nome == "Read":
        return cfg["allow_reads"] and leitura_ok(ti, cwd, cfg), None
    cmd = ti.get("command")
    if nome != "Bash" or not isinstance(cmd, str):
        return False, None
    if cfg["allow_reads"] and por_padroes(cmd, cfg["read_commands"]) and tamanho_ok(cmd, cwd, cfg["read_max_kb"]):
        return True, None
    arq, lista = arquivo_do_repo(cwd)
    if lista and por_padroes(cmd, lista, False) and tamanho_ok(cmd, cwd, cfg["read_max_kb"]):
        k = chave_sessao(d, cli, env)
        return True, t("repo_released", file=arq, cmd=cmd) if k and marcar(pasta, "_repo-%s.flag" % k) else None
    return False, None


def segura_subagente(pasta, agent_id):
    """True while this subagent has been held at most MAX_BLOCOS_SUB times (counter file); no counter = no hold."""
    aid = re.sub(r"[^A-Za-z0-9_-]", "", str(agent_id or ""))[:64]
    if not aid or pasta_segura(pasta, True) is None:
        return False
    f = os.path.join(pasta, "_sub-%s.n" % aid)
    try:
        try:
            with open(f, encoding="utf-8") as fh:
                n = int(fh.read(8).strip() or 0)
        except FileNotFoundError:
            n = 0
        if n >= MAX_BLOCOS_SUB:
            return False
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(str(n + 1))
        return True
    except (OSError, ValueError):
        return False


# ---------- context size ----------
def _ler_fim(caminho, n=512 * 1024):
    try:
        with open(caminho, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - n))
            return f.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return None


def _ler_inicio(caminho, n=1024 * 1024):
    try:
        with open(caminho, "rb") as f:
            return f.read(n).decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return None


def _entrada_codex(linhas):
    for linha in linhas:
        if '"token_count"' not in linha:
            continue
        try:
            info = json.loads(linha)["payload"].get("info") or {}
        except (ValueError, KeyError, AttributeError):
            continue
        uso = info.get("last_token_usage") or {}
        if "input_tokens" in uso:
            return uso["input_tokens"]
    return None


def _entrada_claude(linhas):
    """Input of the first 'assistant' line of the main chain: input + cache creation + cache read."""
    for linha in linhas:
        if '"assistant"' not in linha:
            continue
        try:
            j = json.loads(linha)
            uso = j["message"]["usage"]
            if j.get("type") != "assistant" or j.get("isSidechain"):
                continue
            total = sum(int(uso.get(k) or 0) for k in
                        ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if total > 0:
            return total
    return None


def tokens_e_piso(transcript, cli):
    """(tokens of the last call, floor of the session). shortcut: floor = first response, not the minimum, and
    the last response must sit in the final 512 KiB; upgrade if long tool outputs make the warning miss."""
    f = _entrada_claude if cli == "claude" else _entrada_codex
    fim, ini = _ler_fim(transcript), _ler_inicio(transcript)
    if fim is None or ini is None:
        return None, None
    return f(reversed(fim)), f(ini)


# ---------- switch point ----------
def janela_1m(modelo):
    """1M window by default: `[1m]` suffix, Fable, Sonnet >= 5, Haiku >= 5.5, Opus >= 4.7 (doc: model-config).
    Unknown id: False (200K, the conservative side). The band repeats this: tests/vectors/paths.json locks both."""
    m = (modelo or "").lower()
    if "[1m]" in m or "fable" in m:
        return True
    r = re.search(r"(opus|sonnet|haiku)-(\d{1,2})(?:[-.](\d{1,2}))?(?![0-9])", m)  # a date suffix is not a minor
    return bool(r) and (int(r.group(2)), int(r.group(3) or 0)) >= MIN_1M[r.group(1)]


def _inteiro(v, minimo, maximo=None, texto=True):
    """int from a string of digits (texto: env vars) or a number (never a bool), within the limits; else None."""
    if isinstance(v, str):
        if not texto:
            return None
        v = int(v.strip()) if re.fullmatch(r"\s*[0-9]{1,12}\s*", v) else None
    elif isinstance(v, bool) or not isinstance(v, (int, float)):
        v = None
    elif v != v or v in (float("inf"), float("-inf")):  # NaN / Infinity / 1e400 in the JSON: ignored, like the band
        v = None
    else:
        v = int(v)
    return v if v is not None and v >= minimo and (maximo is None or v <= maximo) else None


def compactacao(cli, modelo, env, settings, codex_limite):
    """(C, origin): the CLI's auto-compaction point in tokens, or (None, 'none'). Origin: env, settings, model,
    codex-config, none; '+pct' when CLAUDE_AUTOCOMPACT_PCT_OVERRIDE (1-100, it only lowers) applied.
    Claude: env CLAUDE_CODE_AUTO_COMPACT_WINDOW, else settings `autoCompactWindow`, else the model's window
    (CLAUDE_CODE_DISABLE_1M_CONTEXT=1 forces 200K). Codex: `model_auto_compact_token_limit` of config.toml."""
    if cli == "codex":
        return (codex_limite, "codex-config") if codex_limite else (None, "none")
    c, origem = _inteiro(env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW"), JANELA_MIN), "env"
    if c is None:
        c, origem = _inteiro((settings or {}).get("autoCompactWindow") if isinstance(settings, dict) else None, JANELA_MIN, texto=False), "settings"
    if c is None:
        grande = janela_1m(modelo) and env.get("CLAUDE_CODE_DISABLE_1M_CONTEXT") != "1"
        c, origem = JANELA_1M if grande else JANELA_200K, "model"
    pct = _inteiro(env.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"), 1, 100)
    return (c * pct // 100, origem + "+pct") if pct else (c, origem)


def ponto_de_troca(piso, d, c):
    """Context (tokens) where the switch is due: floor + min(D, 0.8 x (C - floor)); without a usable C: floor + D."""
    if c is None or c - piso <= 0:
        return piso + d
    return piso + min(d, (c - piso) * 8 // 10)


def modelo_do_transcript(transcript):
    """Model id of the last assistant response of the main chain (Claude transcript); None if unreadable."""
    linhas = _ler_fim(transcript)
    for linha in reversed(linhas or ()):
        if '"assistant"' not in linha:
            continue
        try:
            j = json.loads(linha)
            m = j["message"]["model"]
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if j.get("type") == "assistant" and not j.get("isSidechain") and isinstance(m, str) and not m.startswith("<"):
            return m
    return None


def _json_dict(caminho):
    try:
        with open(caminho, encoding="utf-8-sig") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else None
    except (OSError, ValueError, RecursionError):
        return None


def limite_codex(env, home):
    """`model_auto_compact_token_limit = <number>` of <CODEX_HOME or ~/.codex>/config.toml (top level only, one line).
    shortcut: not a TOML parser (no inline tables, no multi-line); use tomllib when the floor is Python 3.11."""
    try:
        with open(os.path.join(env.get("CODEX_HOME") or os.path.join(home, ".codex"), "config.toml"), encoding="utf-8-sig") as f:
            for linha in f:
                if linha.lstrip().startswith("["):
                    break
                m = re.fullmatch(r"\s*model_auto_compact_token_limit\s*=\s*([0-9]+(?:_[0-9]+)*)\s*(#.*)?", linha.rstrip("\r\n"))  # TOML: `_` only between digits
                if m:
                    return int(m.group(1).replace("_", ""))
    except (OSError, ValueError):
        pass
    return None


def troca_da_sessao(d, cli, cfg, env, home, piso):
    """Switch point of this session (see ponto_de_troca); reads the model from the transcript, the CLI's own config
    files from CLAUDE_CONFIG_DIR / CODEX_HOME (or ~/.claude, ~/.codex). Anything unreadable is ignored."""
    if cli == "codex":
        c, _ = compactacao(cli, None, env, None, limite_codex(env, home))
    else:
        settings = _json_dict(os.path.join(env.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude"), "settings.json"))
        c, _ = compactacao(cli, modelo_do_transcript(d.get("transcript_path")), env, settings, None)
    return ponto_de_troca(piso, cfg["threshold_tokens"], c)


# ---------- output ----------
def tabela(cfg, t, cli):
    claude = cli == "claude"
    rot = ("subagent_type", "model", "effort") if claude else ("agent_type", "model", "reasoning_effort")
    linhas = []
    for camada in CAMADAS:
        r = cfg["routing"][camada][cli]
        partes = ["%s=%s" % (rot[0], r["agent"])]
        if r.get("model"):
            partes.append("%s=%s" % (rot[1], r["model"]))
        partes.append("%s=%s" % (rot[2], r["effort"]))
        linhas.append(t("tier_" + camada, spec=", ".join(partes)))
    if claude:
        linhas.append(t("long_command"))
    texto = t("routing_header", tool="Agent" if claude else "spawn_agent", tiers="\n".join(linhas),
              max=cfg["report_max_chars"])
    if cfg["report_max_chars"] <= 0:  # the last line is the report-size contract
        texto = texto.rsplit("\n", 1)[0]
    return texto


def marcador(pasta, env):
    """Marker of the handoff this Claude process asked for. CLAUDE_PID is the same across /clear and differs between
    processes (measured, Claude Code 2.1.329), so the session after /clear finds its own handoff, never another
    session's in the same folder. shortcut: a reused pid within 30 min could pick an old request; upgrade if seen."""
    pid = env.get("CLAUDE_PID") or ""
    return os.path.join(pasta, "_req-%s.txt" % pid) if re.fullmatch(r"[0-9]{1,10}", pid) else None


def handoff_pendente(d, cli, pasta, env):
    """(text, used-file, file, marker) of the handoff this new session takes, already claimed, or None.
    Claude /clear: the file this same process asked for, else the Codex one of the cwd (<slug>.md). Claude startup:
    the Codex one. Codex: the newest of the cwd, Claude's per-session files included (switching CLI).
    The claim is an atomic rename BEFORE anything is printed: two sessions starting together never get the same one."""
    if d.get("source") not in INICIO_HANDOFF or pasta_segura(pasta, False) is None:
        return None
    base = slug(d.get("cwd") or "")
    proprio = None
    clear_claude = cli == "claude" and d.get("source") == "clear"
    m = marcador(pasta, env) if clear_claude else None
    marca = None  # (marker, content, mtime_ns): given back with the file, or the next /clear finds no request
    if m:  # an empty marker = the band canceled the switch: nothing is delivered by PID
        try:
            with open(m, encoding="utf-8") as f:
                proprio = f.read().strip()
            marca = (m, proprio, os.stat(m).st_mtime_ns)
            os.remove(m)
        except OSError:
            pass
    propria = re.compile(re.escape(base) + r"-[0-9a-f]{8}\.md")
    achados, soltos = [], []
    try:
        for e in os.scandir(pasta):
            if proprio and e.name == proprio and propria.fullmatch(e.name):
                prio = 1
            elif e.name == base + ".md" or (cli == "codex" and re.fullmatch(re.escape(base) + r"-[0-9a-f]{8}\.md", e.name)):
                prio = 0
            else:
                continue
            st = e.stat(follow_symlinks=False)
            if stat.S_ISREG(st.st_mode) and time.time() - st.st_mtime <= VALIDADE_HANDOFF:
                achados.append((prio, st.st_mtime, e.path))
        # no CLAUDE_PID: the one fresh per-session file of this cwd, if it is the only one (two = ambiguous)
        if clear_claude and not re.fullmatch(r"[0-9]{1,10}", env.get("CLAUDE_PID") or ""):
            for e in os.scandir(pasta):
                st = e.stat(follow_symlinks=False)
                if propria.fullmatch(e.name) and stat.S_ISREG(st.st_mode) and time.time() - st.st_mtime <= VALIDADE_HANDOFF:
                    soltos.append((1, st.st_mtime, e.path))
            if len(soltos) == 1:
                achados.append(soltos[0])
    except OSError:
        return None
    for _, _, arq in sorted(achados, reverse=True):
        usada = os.path.join(pasta, "%s-%d.usada.md" % (os.path.basename(arq)[:-3], time.time_ns()))
        try:
            os.rename(arq, usada)  # the claim: whoever renames first owns the delivery
        except OSError:
            continue
        try:
            with open(usada, encoding="utf-8", errors="replace") as f:
                return f.read(), usada, arq, marca
        except OSError:
            desfazer(usada, arq, marca)
            return None
    return None


def desfazer(usada, arq, marca=None):
    """Gives a claimed handoff back (it was not delivered), and the marker that named it, with its age, so the next
    /clear of this process still finds it. Never overwrites a newer handoff or marker."""
    try:
        if not os.path.lexists(arq):
            os.rename(usada, arq)
    except OSError:
        pass
    if marca:
        try:
            with open(marca[0], "x", encoding="utf-8") as f:
                f.write(marca[1])
            os.utime(marca[0], ns=(marca[2], marca[2]))
        except OSError:
            pass


def _u16(texto):
    """Length in UTF-16 units: how Claude counts the 10,000-char limit. Cutting at an even byte offset and
    dropping a dangling half never splits a surrogate pair."""
    return len(texto.encode("utf-16-le", "surrogatepass")) // 2


def _cortar(texto, n):
    """First n UTF-16 units of the text, never splitting a surrogate pair."""
    return texto.encode("utf-16-le")[:2 * max(0, n)].decode("utf-16-le", "ignore")


def _com_aviso(saida, aviso):
    return {**(saida or {}), **(aviso or {})} or None


def contexto(evento, texto):
    return {"hookSpecificOutput": {"hookEventName": evento, "additionalContext": texto}}


def processar(d, cli, env, home, nt):
    """(hook output or None, (used-file, file, marker) to give back if the output cannot be written, or None)."""
    evento = d.get("hook_event_name")
    if evento not in EVENTOS:
        return None, None
    env, antigos = aliasar(env)
    cfg = ler_config(env, home, nt)
    texto = " ".join(d["prompt"].lower().split()).lstrip("/") if evento == "UserPromptSubmit" and isinstance(d.get("prompt"), str) else ""
    pedido = texto in PALAVRAS_HANDOFF
    troca = texto[:6] == "relay " and texto[6:] in MODOS_SESSAO  # `relay off|remind|on`, the whole message
    # SessionStart creates too: it must resolve the folder exactly as the request did, or the handoff is never found
    pasta = escolher_pasta(cfg, env, home, nt, pedido or troca or evento == "SessionStart")
    chave = chave_sessao(d, cli, env)
    m = modo(cfg, env, modo_da_sessao(chave, pasta))
    if evento == "SessionStart" and pasta_segura(pasta, False):
        limpar(pasta, pasta == handoff_dir({}, env, home, nt))
    # the handoff Write is allowed in any mode: it only reaches this session's own handoff file
    if evento == "PreToolUse" and cli == "claude" and permite_passagem(d, pasta, env):
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                       "permissionDecisionReason": "sync_relay: this session's own handoff file"}}, None
    tipo = tipo_sessao(d, cli, cfg, env, m == "force", ignorar_sub=evento == "SubagentStop")
    t = Textos(escolher_lang(cfg["lang"], env))
    aviso = None
    if tipo is None:  # self-check: say it once, never deny; the handoff still works, only the lock stays out
        if m != "off" and avisar_uma_vez(d, pasta):
            aviso = {"systemMessage": t("detect_failed")}
        if evento not in ("UserPromptSubmit", "SessionStart"):
            return aviso, None
        trava = lembra = False
    elif not tipo:
        return None, None
    else:
        trava = m in ("enforce", "force")
        lembra = m != "off"
    if troca and tipo is not False:  # only the user's own message gets here: a hook input, never a model tool call
        ok = gravar_modo(chave, pasta, MODOS_SESSAO[texto[6:]])
        return {"systemMessage": t("mode_" + texto[6:] if ok else "mode_failed"),
                "hookSpecificOutput": {"hookEventName": evento, "additionalContext": t("mode_ack")}}, None
    if antigos and evento in ("UserPromptSubmit", "SessionStart") and marcar(pasta, "_alias-%s.flag" % (chave or "nosid")):
        aviso = {"systemMessage": chr(10).join(x for x in ((aviso or {}).get("systemMessage"), t("alias_warn", names=", ".join(antigos))) if x)}
    if evento == "PreToolUse":
        if not trava or d.get("tool_name") in LIVRES or d.get("tool_name") in cfg["allowed_tools"]:
            return None, None
        if cli == "claude" and escrita_do_handoff(d, pasta):
            return None, None
        livre, nota = liberada(d, cfg, pasta, cli, env, t)
        if livre:
            return ({"systemMessage": nota} if nota else None), None
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": t("denied")}}, None
    if evento == "UserPromptSubmit":
        partes = []
        if pedido and pasta_segura(pasta, True):
            arq = os.path.join(pasta, nome_handoff(d.get("cwd"), d.get("session_id"), cli))
            m = marcador(pasta, env) if cli == "claude" else None
            if m:
                try:
                    with open(m, "w", encoding="utf-8") as f:
                        f.write(os.path.basename(arq))
                except OSError:
                    pass  # no marker: the /clear falls back to the Codex file only
            partes.append(t("handoff_request", file=arq, max=MAX_HANDOFF, how=t("handoff_how_" + cli)))
        elif pedido:  # no usable folder: say so instead of silence
            aviso = {**(aviso or {}), "systemMessage": t("handoff_dir_unusable")}
        if lembra:
            partes.append(t("reminder"))
        return _com_aviso(contexto(evento, "\n\n".join(partes)) if partes else None, aviso), None
    if evento == "SessionStart":
        tab = tabela(cfg, t, cli) if lembra else ""
        pend, mover, bloco = handoff_pendente(d, cli, pasta, env), None, ""
        if pend:  # the handoff first: it is never cut for the table (over 10k Claude Code delivers a path and a preview)
            texto, usada, arq, marca = pend
            try:
                cab = t("handoff_injected", file=usada)
                fim = t("handoff_cut", file=usada)
                resto = LIMITE_CONTEXTO - _u16(cab)
                if _u16(texto) > resto:
                    texto = _cortar(texto, resto - _u16(fim)) + fim
                bloco = cab + texto
            except Exception:  # claimed but nothing will be printed: give it back, fail open
                desfazer(usada, arq, marca)
                return None, None
            mover = (usada, arq, marca)
        sobra = LIMITE_CONTEXTO - _u16(bloco) - (2 if bloco else 0)  # the routing table gets what is left
        if _u16(tab) > sobra:
            corte = t("routing_cut")
            n = sobra - _u16(corte) - 1
            tab = (_cortar(tab, n).rpartition("\n")[0] + "\n" + corte).lstrip("\n") if n >= 0 else ""
        partes = [x for x in (tab, bloco) if x]
        return _com_aviso(contexto(evento, "\n\n".join(partes)) if partes else None, aviso), mover
    # a subagent still running (Claude Stop input `background_tasks`): its report would land in the new session out of
    # context, so warn at the turn that brings it; shells never hold the warning (a server may never end)
    tarefas = d.get("background_tasks") if isinstance(d.get("background_tasks"), list) else []
    sub_vivo = any(isinstance(x, dict) and x.get("type") == "subagent" for x in tarefas)
    if evento == "Stop" and not d.get("stop_hook_active") and not sub_vivo and (cli != "claude" or cfg["stop_warning"]):
        n, piso = tokens_e_piso(d.get("transcript_path"), cli)
        if n and piso is not None:
            troca = troca_da_sessao(d, cli, cfg, env, home, piso)
            if n >= troca:
                return {"systemMessage": t("stop_warning", total=n // 1000, extra=(n - piso) // 1000,
                                           limit=troca // 1000)}, None
    if evento == "SubagentStop" and lembra and not d.get("stop_hook_active"):
        # Claude Code sends every Bash over ~180 s to the background; the subagent would end and its result never come back
        tarefas = d.get("background_tasks") if isinstance(d.get("background_tasks"), list) else []
        vivas = [x for x in tarefas if isinstance(x, dict) and x.get("type") in ("shell", "monitor") and x.get("status") not in FIM_DE_TAREFA]
        if vivas and segura_subagente(pasta, d.get("agent_id")):
            return {"decision": "block", "reason": t("sub_wait", n=len(vivas))}, None
    if evento == "SubagentStop" and trava and not d.get("stop_hook_active"):
        msg = d.get("last_assistant_message")
        limite = cfg["report_max_chars"]
        if limite > 0 and isinstance(msg, str) and len(msg) > limite:
            return {"decision": "block", "reason": t("report_too_long", max=limite)}, None
    return None, None


def main():
    cli = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("claude", "codex") else "claude"
    try:  # a hook never takes the session down
        # utf-8-sig: Windows PowerShell 5.1 pipes stdin with a BOM when $OutputEncoding is UTF-8
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", "replace") or "{}")
        if not isinstance(d, dict):
            return
        saida, devolver = processar(d, cli, os.environ, str(Path.home()), os.name == "nt")
    except Exception:
        return
    try:
        if saida:
            sys.stdout.write(json.dumps(saida))  # ASCII on purpose
            sys.stdout.flush()
    except Exception:
        if devolver:  # claimed but not delivered: give it back for the next session
            desfazer(*devolver)


if __name__ == "__main__":
    main()

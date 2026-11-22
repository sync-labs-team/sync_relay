"""Tests for plugins/sync_relay/scripts/sync_relay.py (the core of sync_relay).

Run from the repo root: python -I -m unittest
Hooks run as subprocesses with the same command shape as hooks/*.json, in a sandbox: every user-level path
(HOME, LOCALAPPDATA, XDG_*, config, handoff_dir) points into a temp dir, never into the real user folders.
"""
import importlib.util
import json
import ntpath
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "sync_relay"
SCRIPT = PLUGIN / "scripts" / "sync_relay.py"
VET = json.loads((RAIZ / "tests" / "vectors" / "paths.json").read_text("utf-8"))
CMD = ("import os,runpy;runpy.run_path(os.path.join(os.environ['CLAUDE_PLUGIN_ROOT'],'scripts',"
       "'sync_relay.py'),run_name='__main__')")
CHAVES = ["reminder", "denied", "routing_header", "tier_lookup", "tier_judgment", "tier_build", "tier_hard",
          "tier_plan", "handoff_request", "handoff_injected", "stop_warning", "report_too_long", "detect_failed",
          "handoff_dir_unusable", "routing_cut", "mode_off", "mode_remind", "mode_on", "repo_released", "alias_warn", "sub_wait", "long_command", "mode_ack", "mode_failed", "lock_hint", "pattern_ignored"]

spec = importlib.util.spec_from_file_location("relay", SCRIPT)
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)

SB = Path(tempfile.mkdtemp(prefix="relay-test-"))
HD = SB / "handoffs"
SBENV = {"HOME": str(SB), "USERPROFILE": str(SB), "LOCALAPPDATA": str(SB / "local"), "APPDATA": str(SB / "roaming"),
         "XDG_CONFIG_HOME": str(SB / "xdgc"), "XDG_STATE_HOME": str(SB / "xdgs")}
BASE_CFG = {"handoff_dir": str(HD)}
PADRAO = Path(relay.handoff_dir({}, SBENV, str(SB), os.name == "nt"))  # the plugin's own folder: the only one cleaned
SA = relay.slug("C:\\Proj\\A")  # handoff name base of the cwds the tests use
SX = relay.slug("C:\\x")
CLI = {"CLAUDE_CODE_ENTRYPOINT": "cli", "LANG": "en_US.UTF-8"}
EN = json.loads((PLUGIN / "messages" / "en.json").read_text("utf-8"))
PT = json.loads((PLUGIN / "messages" / "pt-BR.json").read_text("utf-8"))


def tearDownModule():
    shutil.rmtree(SB, ignore_errors=True)


def rodar(cli, entrada, env=None, cfg=None, cru=None):
    e = {k: v for k, v in os.environ.items()
         if not k.startswith(("SYNC_RELAY_", "SYNCLABS_RELAY_", "CLAUDE_CODE_", "CLAUDE_PID", "CLAUDE_CONFIG_DIR", "CLAUDE_AUTOCOMPACT_", "CODEX_HOME", "LC_", "LANG"))}
    e.update(SBENV)
    e["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN)
    cf = SB / "config.json"
    cf.write_bytes(cru if cru is not None else json.dumps({**BASE_CFG, **(cfg or {})}).encode("utf-8"))
    e["SYNC_RELAY_CONFIG"] = str(cf)
    e.update(env or {})
    dados = entrada if isinstance(entrada, bytes) else json.dumps(entrada, ensure_ascii=False).encode("utf-8")
    r = subprocess.run([sys.executable, "-I", "-c", CMD, cli], input=dados, capture_output=True, env=e, timeout=60, cwd=str(SB))
    assert r.returncode == 0, r.stderr
    r.stdout.decode("ascii")  # scenario 14: output is always ASCII
    s = r.stdout.decode("ascii")
    return json.loads(s) if s.strip() else None


def negou(s):
    return bool(s) and s.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def ctx(s):
    return s["hookSpecificOutput"]["additionalContext"]


def rollout(pasta, originator, tokens=None, source="cli", primeiro=None):
    p = os.path.join(pasta, f"rollout-{originator}-{tokens}-{primeiro}-{len(json.dumps(source))}.jsonl")
    meta = {"source": source}
    if originator:
        meta["originator"] = originator
    linhas = [{"type": "session_meta", "payload": meta}]
    for n in (primeiro, tokens):  # the first token_count is the session floor
        if n is not None:
            linhas.append({"type": "event_msg", "payload": {"type": "token_count", "info": {
                "last_token_usage": {"input_tokens": n}, "model_context_window": 500000}}})
    Path(p).write_text("\n".join(json.dumps(x) for x in linhas) + "\n", "utf-8")
    return p


def transcript_claude(pasta, nome, totais, extra=()):
    """totais: soma dos tres campos de entrada de cada resposta 'assistant' (principal)."""
    linhas = [{"type": "user", "message": {"content": "oi"}}]
    for t in totais:
        linhas.append({"type": "assistant", "isSidechain": False, "message": {"usage": {
            "input_tokens": 100, "cache_creation_input_tokens": 400, "cache_read_input_tokens": t - 500,
            "output_tokens": 5}}})
    linhas += list(extra)
    p = os.path.join(pasta, nome + ".jsonl")
    Path(p).write_text("\n".join(json.dumps(x) for x in linhas) + "\n", "utf-8")
    return p


PRE = {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {}, "cwd": "C:\\x", "session_id": "s-1"}
UPS = {"hook_event_name": "UserPromptSubmit", "prompt": "oi", "cwd": "C:\\x", "session_id": "s-1"}
STOP = {"hook_event_name": "Stop", "stop_hook_active": False, "cwd": "C:\\x", "session_id": "s-1"}
SS = {"hook_event_name": "SessionStart", "source": "startup", "cwd": "C:\\Proj\\A", "session_id": "s-1"}


class Limpo(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(HD, ignore_errors=True)


class Vetores(unittest.TestCase):  # contract shared with the mod
    def test_slug(self):
        for c in VET["slug_cases"]:
            self.assertEqual(relay.slug(c["cwd"], c["windows"]), c["slug"], c["name"])

    def test_slug_distintos_e_iguais(self):  # item 1: projects that used to collide now get their own file
        por_nome = {c["name"]: relay.slug(c["cwd"], c["windows"]) for c in VET["slug_cases"]}
        for grupo in VET["distinct"]:
            self.assertEqual(len({por_nome[n] for n in grupo}), len(grupo), grupo)
        for grupo in VET["same"]:
            self.assertEqual(len({por_nome[n] for n in grupo}), 1, grupo)
        for v in por_nome.values():
            self.assertRegex(v, r"[a-z0-9-]*[0-9a-f]{8}")
            self.assertFalse(v.startswith("-"))

    def test_codex_nao_recebe_a_passagem_de_outro_projeto(self):  # item 1: the reviewer's proof, end to end
        HD.mkdir(parents=True, exist_ok=True)
        a, b = "C:\\w\\my_app", "C:\\w\\my-app"
        (HD / relay.nome_handoff(a, "", "codex")).write_text("SECRET OF PROJECT A", "utf-8")
        with tempfile.TemporaryDirectory() as t:
            tr = rollout(t, "codex-tui")
            self.assertNotIn("SECRET OF PROJECT A", json.dumps(rodar("codex", {**SS, "cwd": b, "transcript_path": tr})))
            self.assertIn("SECRET OF PROJECT A", ctx(rodar("codex", {**SS, "cwd": a, "transcript_path": tr})))

    def test_copia_embutida_no_band_igual_ao_json(self):  # the band test cannot read files: its copy must not drift
        txt = (RAIZ / "plugins" / "sync_relay" / "band.test.tsx").read_text("utf-8")
        m = re.search(r"^const vectors = (\{.*?^\})\s*$", txt, re.S | re.M)
        self.assertTrue(m)
        esperado = {k: v for k, v in VET.items() if k != "_comment"}
        self.assertEqual(json.loads(m.group(1)), esperado)

    def test_regra_do_handoff_dir(self):  # item 3: the band repeats these cases
        r = VET["handoff_dir_rule"]
        for nt, chave in ((True, "windows"), (False, "posix")):
            home = r["home"][chave]
            padrao = relay.handoff_dir({}, {}, home, nt)
            for ok in r[chave]["ok"]:
                self.assertNotEqual(relay.handoff_dir({"handoff_dir": ok}, {}, home, nt), padrao, (chave, ok))
            for ruim in r[chave]["bad"]:
                self.assertEqual(relay.handoff_dir({"handoff_dir": ruim}, {}, home, nt), padrao, (chave, ruim))
        self.assertEqual(relay.handoff_dir({"handoff_dir": "~/h"}, {}, "/home/alice", False), "/home/alice/h")
        self.assertEqual(relay.handoff_dir({"handoff_dir": "~\\h"}, {}, "C:\\Users\\alice", True), "C:\\Users\\alice\\h")
        self.assertEqual(relay.handoff_dir({"handoff_dir": "~"}, {"HOME": "/x"}, "/home/alice", False), "/x")

    def test_lang_mesma_regra_do_band(self):  # item 4
        for v, esperado in VET["lang"]:
            for loc, outro in (("pt_BR", "pt-BR"), ("en_US", "en")):
                got = relay.escolher_lang(v, {}, lambda: (loc, "x"))
                self.assertEqual(got, outro if esperado == "locale" else esperado, (v, loc))
        # env wins only when it is a language we know; otherwise the config decides (same as the band)
        self.assertEqual(relay.escolher_lang("pt", {"SYNC_RELAY_LANG": "xx"}, lambda: ("en_US", "x")), "pt-BR")
        self.assertEqual(relay.escolher_lang("en", {"SYNC_RELAY_LANG": "PT_br"}, lambda: ("en_US", "x")), "pt-BR")

    def test_handoff_dir(self):
        d = VET["handoff_dir"]["default"]
        w, px, ph = d["windows"], d["posix_xdg"], d["posix_home"]
        self.assertEqual(relay.handoff_dir({}, w["env"], "C:\\Users\\alice", True), w["expected"])
        self.assertEqual(relay.handoff_dir({}, px["env"], "/home/alice", False), px["expected"])
        self.assertEqual(relay.handoff_dir({}, ph["env"], ph["home"], False), ph["expected"])
        self.assertEqual(relay.handoff_dir({"handoff_dir": "/custom/h"}, {}, "/home/alice", False), "/custom/h")

    def test_messages_same_keys(self):
        self.assertEqual(set(EN), set(PT))
        for k in CHAVES:
            self.assertTrue(EN[k].strip() and PT[k].strip(), k)


class PastaPrivada(Limpo):  # item 2: the folder is 0700 whatever created it (the band's $.fs.write uses the engine mode)
    def test_logica_com_stat_falso(self):  # runs on any OS
        from types import SimpleNamespace as St
        chamadas = []
        self.assertTrue(relay.dono_e_modo(St(st_uid=7, st_mode=0o40755), 7, chamadas.append))
        self.assertEqual(chamadas, [0o700])
        chamadas.clear()
        self.assertTrue(relay.dono_e_modo(St(st_uid=7, st_mode=0o40700), 7, chamadas.append))
        self.assertEqual(chamadas, [])
        self.assertFalse(relay.dono_e_modo(St(st_uid=0, st_mode=0o40700), 7, chamadas.append))  # not ours: unsafe
        self.assertEqual(chamadas, [])

    def test_pasta_configurada_nao_leva_chmod(self):  # runs on any OS (fake stat, fake geteuid)
        from types import SimpleNamespace as St
        from unittest import mock
        chamadas = []
        self.assertTrue(relay.dono_e_modo(St(st_uid=7, st_mode=0o40755), 7, chamadas.append, False))
        self.assertEqual(chamadas, [])
        self.assertFalse(relay.dono_e_modo(St(st_uid=0, st_mode=0o40700), 7, chamadas.append, False))  # still unsafe
        HD.mkdir(parents=True)
        antes = relay._CONFIG_DIR
        try:
            with mock.patch.object(relay.os, "geteuid", lambda: os.lstat(HD).st_uid, create=True),                     mock.patch.object(relay.os, "chmod") as ch:
                relay._CONFIG_DIR = str(HD)
                self.assertEqual(relay.pasta_segura(str(HD), False), str(HD))
                ch.assert_not_called()
                relay._CONFIG_DIR = str(HD) + "-other"  # HD is now the default folder
                if os.name != "nt":
                    os.chmod(HD, 0o755)
                relay.pasta_segura(str(HD), False)
                if os.name != "nt":
                    ch.assert_called_once_with(str(HD), 0o700)
        finally:
            relay._CONFIG_DIR = antes

    def test_pasta_existente_larga_vira_0700(self):
        if os.name == "nt":
            self.skipTest("POSIX modes")
        HD.mkdir(parents=True)
        os.chmod(HD, 0o755)
        self.assertEqual(relay.pasta_segura(str(HD), False), str(HD))
        self.assertEqual(os.stat(HD).st_mode & 0o777, 0o700)
        os.chmod(HD, 0o775)
        rodar("claude", {**SS, "source": "resume"}, CLI)  # SessionStart uses the folder
        self.assertEqual(os.stat(HD).st_mode & 0o777, 0o700)


class GanchosDoCodex(Limpo):  # item 7: T6 measured only PLUGIN_ROOT and PLUGIN_DATA in a Codex 0.170 plugin hook
    def comando(self, arquivo):
        h = json.loads((PLUGIN / "hooks" / arquivo).read_text("utf-8"))["hooks"]
        return {ev: re.search(r'-c "(.*)" (claude|codex)$', v[0]["hooks"][0]["command"]).groups() for ev, v in h.items()}

    def roda(self, codigo, cli, var):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_", "PLUGIN_", "SYNC_RELAY_"))}
        e.update(SBENV)
        e[var] = str(PLUGIN)
        cf = SB / "config.json"
        cf.write_text(json.dumps(BASE_CFG), "utf-8")
        e["SYNC_RELAY_CONFIG"] = str(cf)
        with tempfile.TemporaryDirectory() as t:
            ent = {**SS, "transcript_path": rollout(t, "codex-tui")}
            r = subprocess.run([sys.executable, "-I", "-c", codigo, cli], input=json.dumps(ent).encode(),
                               capture_output=True, env=e, timeout=60, cwd=str(SB))
        return r.returncode, r.stdout.decode("ascii")

    def test_codex_acha_o_script_so_com_plugin_root(self):
        for ev, (codigo, cli) in self.comando("codex.json").items():
            self.assertEqual(cli, "codex")
            for var in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):  # the measured one, and the documented alias
                rc, out = self.roda(codigo, cli, var)
                self.assertEqual(rc, 0, (ev, var))
                if ev == "SessionStart":
                    self.assertIn("spawn_agent", out, (ev, var))

    def test_claude_continua_com_claude_plugin_root(self):
        for ev, (codigo, cli) in self.comando("claude.json").items():
            self.assertEqual(cli, "claude")
            self.assertIn("CLAUDE_PLUGIN_ROOT", codigo)


class Trava(Limpo):  # scenarios 1-3
    def test_claude(self):
        self.assertTrue(negou(rodar("claude", PRE, CLI)))
        self.assertNotIn("relay off", rodar("claude", PRE, CLI)["hookSpecificOutput"]["permissionDecisionReason"])  # review F
        self.assertIsNone(rodar("claude", {**PRE, "agent_id": "a1"}, CLI))
        self.assertIsNone(rodar("claude", PRE, {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))
        for livre in ("Agent", "AskUserQuestion", "ToolSearch", "TodoWrite", "SendUserMessage", "TeamCreate"):
            self.assertIsNone(rodar("claude", {**PRE, "tool_name": livre}, CLI), livre)
        self.assertTrue(negou(rodar("claude", {**PRE, "tool_name": "mcp__x__y"}, CLI)))

    def test_repl_code_mode(self):  # REPL is the Code Mode wrapper; its inner calls fire their own PreToolUse; Poll waits for its result
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "REPL"}, CLI))
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "Poll"}, CLI))
        self.assertTrue(negou(rodar("claude", {**PRE, "tool_name": "Read"}, CLI)))
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "Agent"}, CLI))

    def test_sendfeedback_livre(self):  # drafts a local report, sends nothing (tools-reference); Monitor and WebFetch stay denied
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "SendFeedback"}, CLI))
        for preso in ("Monitor", "WebFetch"):
            self.assertTrue(negou(rodar("claude", {**PRE, "tool_name": preso}, CLI)), preso)

    def test_force_e_off(self):
        sdk = {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}
        self.assertTrue(negou(rodar("claude", PRE, {**sdk, "SYNC_RELAY_MODE": "force"})))
        self.assertIsNone(rodar("claude", {**PRE, "agent_id": "a1"}, {**sdk, "SYNC_RELAY_MODE": "force"}))
        self.assertIsNone(rodar("claude", PRE, {**CLI, "SYNC_RELAY_MODE": "off"}))
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, "SYNC_RELAY_MODE": "enforce"}, {"mode": "off"})))  # env wins

    def test_remind_e_off(self):
        self.assertIsNone(rodar("claude", PRE, CLI, {"mode": "remind"}))
        self.assertEqual(ctx(rodar("claude", UPS, CLI, {"mode": "remind"})), EN["reminder"])
        self.assertIsNone(rodar("claude", PRE, CLI, {"mode": "off"}))
        self.assertIsNone(rodar("claude", UPS, CLI, {"mode": "off"}))
        pedido = ctx(rodar("claude", {**UPS, "prompt": "relay"}, CLI, {"mode": "off"}))
        self.assertIn(str(HD), pedido)
        self.assertNotIn(EN["reminder"], pedido)

    def test_allowed_tools(self):
        cfg = {"allowed_tools": ["mcp__x__y"]}
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "mcp__x__y"}, CLI, cfg))
        self.assertTrue(negou(rodar("claude", {**PRE, "tool_name": "mcp__x__z"}, CLI, cfg)))
        self.assertTrue(negou(rodar("claude", PRE, CLI, cfg)))

    def test_codex(self):
        with tempfile.TemporaryDirectory() as t:
            tui, desk, exe, cc = (rollout(t, o) for o in ("codex-tui", "codex_work_desktop", "codex_exec", "Claude Code"))
            sub = rollout(t, "codex-tui", source={"subagent": {"thread_spawn": {"parent_thread_id": "p"}}})
            outro = rollout(t, "outro")
            cp = {**PRE, "tool_name": "Bash"}
            self.assertTrue(negou(rodar("codex", {**cp, "transcript_path": tui})))
            self.assertTrue(negou(rodar("codex", {**cp, "transcript_path": desk})))
            self.assertIsNone(rodar("codex", {**cp, "transcript_path": exe}, CLI))
            self.assertIsNone(rodar("codex", {**cp, "transcript_path": cc}, CLI))
            self.assertIsNone(rodar("codex", {**cp, "transcript_path": sub}))
            self.assertIsNone(rodar("codex", {**cp, "transcript_path": tui, "agent_id": "s1"}))
            self.assertIsNone(rodar("codex", {**cp, "transcript_path": tui, "tool_name": "spawn_agent"}))
            self.assertIsNone(rodar("codex", {**cp, "transcript_path": outro}))
            self.assertTrue(negou(rodar("codex", {**cp, "transcript_path": outro},
                                        cfg={"codex_interactive_originators": ["outro"]})))
            self.assertIsNone(rodar("codex", {**cp, "transcript_path": tui}, cfg={"codex_interactive_originators": ["outro"]}))
            for ferr in ("apply_patch", "Write"):  # Codex has no handoff-path exception
                self.assertTrue(negou(rodar("codex", {**cp, "tool_name": ferr, "transcript_path": tui})), ferr)


class Idioma(Limpo):  # scenario 5
    def test_cfg_e_env(self):
        self.assertEqual(ctx(rodar("claude", UPS, CLI, {"lang": "pt-BR"})), PT["reminder"])
        self.assertEqual(ctx(rodar("claude", UPS, CLI, {"lang": "en"})), EN["reminder"])
        self.assertEqual(ctx(rodar("claude", UPS, {**CLI, "SYNC_RELAY_LANG": "pt-BR"}, {"lang": "en"})), PT["reminder"])
        self.assertNotEqual(EN["reminder"], PT["reminder"])

    def test_auto_por_ambiente(self):
        self.assertEqual(ctx(rodar("claude", UPS, {**CLI, "LANG": "pt_BR.UTF-8"})), PT["reminder"])
        self.assertEqual(ctx(rodar("claude", UPS, {**CLI, "LANG": "en_US.UTF-8"})), EN["reminder"])
        self.assertEqual(ctx(rodar("claude", UPS, {**CLI, "LC_ALL": "pt_BR.UTF-8", "LANG": "en_US.UTF-8"})), PT["reminder"])

    def test_auto_sem_lang_cai_no_locale(self):
        f = relay.escolher_lang
        self.assertEqual(f("auto", {}, lambda: ("pt_BR", "cp1252")), "pt-BR")
        self.assertEqual(f("auto", {}, lambda: ("en_US", "cp1252")), "en")
        self.assertEqual(f("auto", {}, lambda: (None, None)), "en")
        self.assertEqual(f("auto", {"LANG": "C"}, lambda: ("pt_BR", "x")), "en")
        self.assertEqual(f("pt", {}, lambda: (None, None)), "pt-BR")
        self.assertEqual(f("de", {"LANG": "pt_BR"}, lambda: (None, None)), "pt-BR")  # unknown value: same as auto

    def test_chave_ausente_no_ptbr_cai_no_en(self):
        self.assertEqual(relay.mensagem({"x": "a"}, {"x": "b", "y": "c"}, "y"), "c")
        self.assertEqual(relay.mensagem({"x": "a"}, {"x": "b", "y": "c"}, "x"), "a")


class MigracaoDaConfig(Limpo):  # 0.2.0: synclabs-relay/config.json is copied once to sync_relay/config.json
    def _env(self):
        base = SB / "mig"
        shutil.rmtree(base, ignore_errors=True)
        return {"XDG_CONFIG_HOME": str(base)}, base

    def test_copia_a_antiga_no_primeiro_uso(self):
        env, base = self._env()
        (base / "synclabs-relay").mkdir(parents=True)
        (base / "synclabs-relay" / "config.json").write_text('{"mode": "remind"}', "utf-8")
        self.assertEqual(relay.ler_config(env, str(SB), False)["mode"], "remind")
        self.assertEqual(json.loads((base / "sync_relay" / "config.json").read_text("utf-8")), {"mode": "remind"})
        self.assertTrue((base / "synclabs-relay" / "config.json").exists())  # the old one stays

    def test_a_nova_vence_e_nao_e_sobrescrita(self):
        env, base = self._env()
        for d, m in (("synclabs-relay", "remind"), ("sync_relay", "off")):
            (base / d).mkdir(parents=True)
            (base / d / "config.json").write_text('{"mode": "%s"}' % m, "utf-8")
        self.assertEqual(relay.ler_config(env, str(SB), False)["mode"], "off")
        self.assertEqual(json.loads((base / "sync_relay" / "config.json").read_text("utf-8"))["mode"], "off")

    def test_sem_antiga_nao_cria_nada_e_config_explicita_nao_migra(self):
        env, base = self._env()
        base.mkdir(parents=True)
        relay.ler_config(env, str(SB), False)
        self.assertFalse((base / "sync_relay").exists())
        (base / "synclabs-relay").mkdir()
        (base / "synclabs-relay" / "config.json").write_text("{}", "utf-8")
        relay.ler_config({**env, "SYNC_RELAY_CONFIG": str(base / "x.json")}, str(SB), False)
        self.assertFalse((base / "sync_relay").exists())


class Lembrete(Limpo):
    def test_so_na_principal(self):
        self.assertEqual(ctx(rodar("claude", UPS, CLI)), EN["reminder"])
        self.assertIsNone(rodar("claude", UPS, {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))
        self.assertLess(len(EN["reminder"]), 400)
        self.assertLess(len(PT["reminder"]), 400)

    def test_pedido_de_passagem(self):
        for palavra in ("relay", " /Relay ", "/RELAY"):
            c = ctx(rodar("claude", {**UPS, "prompt": palavra, "cwd": "C:\\Proj\\A"}, CLI))
            self.assertIn(str(HD / (SA + "-s-1.md")), c, palavra)  # Claude: <slug>-<id[:8]>.md
            self.assertIn(EN["reminder"], c)
        for palavra in ("handoff", "/handoff", "passagem", "/passagem", "relay now", "relays", "/relay auto"):
            c = ctx(rodar("claude", {**UPS, "prompt": palavra, "cwd": "C:\\Proj\\A"}, CLI))
            self.assertEqual(c, EN["reminder"], palavra)  # only the reminder: no handoff request
        c = ctx(rodar("codex", {**UPS, "prompt": "relay", "transcript_path": rollout(str(SB), "codex-tui")}, CLI))
        self.assertIn("fork_context", c)
        self.assertIn("8000", c)
        if os.name != "nt":
            self.assertEqual(os.stat(HD).st_mode & 0o777, 0o700)
        self.assertTrue(HD.is_dir())  # the hook creates the folder before asking for the write

    def test_pedido_leva_meta_agendamentos_e_segundo_plano(self):  # v0.1.1, measured: /clear drops the goal, keeps the rest
        for lang, msgs in (("en", EN), ("pt-BR", PT)):
            c = ctx(rodar("claude", {**UPS, "prompt": "relay"}, CLI, {"lang": lang}))
            for termo in ("/goal", "CronList", "/clear"):
                self.assertIn(termo, c, (lang, termo))
            self.assertLess(len(msgs["handoff_request"]), 1800, lang)
        self.assertIn("subagent", ctx(rodar("claude", {**UPS, "prompt": "relay"}, CLI, {"lang": "en"})))
        self.assertIn("subagente", ctx(rodar("claude", {**UPS, "prompt": "relay"}, CLI, {"lang": "pt-BR"})))


class SessionStartTabela(Limpo):  # scenario 6
    def test_tabela_da_config(self):
        c = ctx(rodar("claude", SS, CLI))
        for v in ("haiku", "Explore", "opus", "xhigh", "sonnet"):
            self.assertIn(v, c)
        self.assertIn("Agent", c)
        self.assertLess(len(c), 1500)
        cfg = {"routing": {"lookup": {"claude": {"agent": "Foo", "model": "m1"}}, "hard": {"claude": {"model": None}}}}
        c = ctx(rodar("claude", SS, CLI, cfg))
        self.assertIn("Foo", c)
        self.assertIn("m1", c)
        self.assertNotIn("haiku", c)
        hard = [x for x in c.splitlines() if "effort=high" in x and "general-purpose" in x]
        self.assertTrue(hard and all("model" not in x for x in hard), hard)  # model: null = line does not cite a model
        self.assertIn("sonnet", c)  # other layers keep the default

    def test_codex_tem_a_propria_linha(self):
        c = ctx(rodar("codex", {**SS, "transcript_path": rollout(str(SB), "codex-tui")}))
        self.assertIn("spawn_agent", c)
        self.assertIn("explorer", c)
        self.assertNotIn("haiku", c)

    def test_so_interativa_e_so_fora_do_off(self):
        self.assertIsNone(rodar("claude", SS, {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))
        self.assertIsNone(rodar("claude", SS, CLI, {"mode": "off"}))
        self.assertIsNone(rodar("claude", {**SS, "agent_id": "a"}, CLI))


class Passagem(Limpo):
    def escreve(self, texto, cwd="C:\\Proj\\A", nome=None):
        HD.mkdir(parents=True, exist_ok=True)
        p = HD / (nome or relay.slug(cwd) + ".md")
        p.write_text(texto, "utf-8")
        return p

    def cod(self, tmp, extra=None, **kw):
        return rodar("codex", {**SS, "transcript_path": rollout(tmp, "codex-tui"), **kw}, extra)

    def test_corte_em_9000(self):  # scenario 7
        longa = "# Long\n" + "handoff line with accents \u00e7\u00e3o \u2713\n" * 700
        self.assertGreater(len(longa), 20000)
        arq = self.escreve(longa)
        c = ctx(rodar("claude", {**SS, "source": "clear"}, CLI))
        self.assertLessEqual(len(c), 9500)
        self.assertLessEqual(len(c), 9000)
        m = re.search(r"(\S+\.usada\.md)", c.splitlines()[-1])
        self.assertTrue(m, c[-300:])
        self.assertEqual(Path(m.group(1)).read_text("utf-8"), longa)
        self.assertFalse(arq.exists())

    def test_curta_inteira_e_so_uma_vez(self):
        arq = self.escreve("short one")
        c = ctx(rodar("claude", SS, CLI))
        self.assertTrue(c.endswith("short one"))
        usada = re.search(r"\((\S+\.usada\.md)\)", c).group(1)  # the header cites the file that still exists
        self.assertEqual(Path(usada).read_text("utf-8"), "short one")
        self.assertFalse(arq.exists())
        self.assertNotIn("short one", ctx(rodar("claude", SS, CLI)))  # already used: only the table

    def test_claude_para_codex_e_inverso(self):  # scenario 8
        with tempfile.TemporaryDirectory() as t:
            cwd = "C:\\Proj\\A"
            pedido = ctx(rodar("claude", {**UPS, "prompt": "relay", "cwd": cwd, "session_id": "00000000-0000-4000-8000-000000000001"}, CLI))
            alvo = re.search(r"(\S+%s-00000000\.md)" % SA, pedido).group(1)
            Path(alvo).write_text("from claude \u2192 codex", "utf-8")
            # a new Claude window never takes another Claude session's file; only the /clear of the asking process does
            self.assertNotIn("from claude", ctx(rodar("claude", SS, CLI)))
            c = ctx(self.cod(t))
            self.assertIn("from claude", c)
            self.assertFalse(Path(alvo).exists())
            pedido = ctx(rodar("codex", {**UPS, "prompt": "relay", "cwd": cwd,
                                         "transcript_path": rollout(t, "codex-tui")}))
            alvo = re.search(r"(\S+%s\.md)" % SA, pedido).group(1)
            Path(alvo).write_text("from codex", "utf-8")
            self.assertIn("from codex", ctx(rodar("claude", {**SS, "source": "clear"}, CLI)))

    def test_nome_do_arquivo(self):
        sid = "00000000-0000-4000-8000-000000000001"
        self.assertEqual(relay.nome_handoff("C:\\x", sid, "claude"), SX + "-00000000.md")
        self.assertEqual(relay.nome_handoff("C:\\x", sid, "codex"), SX + ".md")
        self.assertEqual(relay.nome_handoff("C:\\x", None, "claude"), SX + ".md")

    def test_duas_sessoes_claude_na_mesma_pasta(self):
        a = ctx(rodar("claude", {**UPS, "prompt": "relay", "session_id": "aaaaaaaa-1"}, CLI))
        b = ctx(rodar("claude", {**UPS, "prompt": "relay", "session_id": "bbbbbbbb-2"}, CLI))
        self.assertIn("-aaaaaaaa.md", a)
        self.assertIn("-bbbbbbbb.md", b)
        self.assertNotIn("-aaaaaaaa", b)

    def test_fontes_e_validade(self):
        with tempfile.TemporaryDirectory() as t:
            arq = self.escreve("pending")
            for fonte in ("resume", "compact", "fork"):  # table yes, handoff no
                self.assertNotIn("pending", ctx(self.cod(t, source=fonte)), fonte)
                self.assertNotIn("pending", ctx(rodar("claude", {**SS, "source": fonte}, CLI)), fonte)
            self.assertTrue(arq.exists())
            old = time.time() - 31 * 60
            os.utime(arq, (old, old))
            self.assertNotIn("pending", ctx(self.cod(t)))
            os.utime(arq, None)
            sub = rollout(t, "codex-tui", source={"subagent": {}})
            self.assertIsNone(rodar("codex", {**SS, "transcript_path": sub}))
            self.assertIsNone(rodar("codex", {**SS, "transcript_path": rollout(t, "codex_exec")}))
            self.assertIsNone(rodar("claude", SS, {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))
            self.assertIn("pending", ctx(self.cod(t)))

    def test_utf8_invalido_e_off_ainda_entrega(self):
        arq = self.escreve("")
        arq.write_bytes(b"broken \xff end")
        with tempfile.TemporaryDirectory() as t:
            self.assertIn("end", ctx(self.cod(t)))
            self.assertFalse(arq.exists())
            self.escreve("with mode off")
            off = rodar("codex", {**SS, "transcript_path": rollout(t, "codex-tui")}, None, {"mode": "off"})
            self.assertIn("with mode off", ctx(off))

    def test_limpeza_de_7_dias(self):
        PADRAO.mkdir(parents=True, exist_ok=True)
        dia = 86400

        def cria(nome, dias):
            p = PADRAO / nome
            p.write_text("x", "utf-8")
            t = time.time() - dias * dia
            os.utime(p, (t, t))
            return p
        velha, nova, txt, pend = cria("a.usada.md", 8), cria("b.usada.md", 1), cria("d.txt", 8), cria("c.md", 8)
        rodar("claude", {**SS, "source": "resume"}, CLI, {"handoff_dir": ""})
        self.assertFalse(velha.exists() or pend.exists())
        self.assertTrue(nova.exists() and txt.exists())

    def test_pasta_configurada_nunca_e_limpa(self):  # A1
        HD.mkdir(parents=True)
        nota = HD / "todo.md"
        nota.write_text("x", "utf-8")
        t = time.time() - 9 * 86400
        os.utime(nota, (t, t))
        rodar("claude", {**SS, "source": "resume"}, CLI)
        self.assertTrue(nota.exists())

    def test_limpeza_so_nomes_do_plugin(self):  # A1
        PADRAO.mkdir(parents=True, exist_ok=True)

        def cria(nome, dias):
            p = PADRAO / nome
            p.write_text("x", "utf-8")
            t = time.time() - dias * 86400
            os.utime(p, (t, t))
            return p
        seus = [cria("Minha Nota.md", 8), cria("lista.flag", 8), cria("Notas-2026.usada.md", 8)]
        meus = [cria(SA + ".md", 8), cria(SA + "-0a1b2c3d.md", 8), cria(SA + "-20260101-101010.usada.md", 8),
                cria("_detect-s1.flag", 8), cria("_req-4242.txt", 8)]
        rodar("claude", {**SS, "source": "resume"}, CLI, {"handoff_dir": ""})
        self.assertTrue(all(p.exists() for p in seus))
        self.assertEqual([p.name for p in meus if p.exists()], [])

    def test_pasta_configurada_limpa_so_o_sublinhado_do_plugin(self):  # item 3
        HD.mkdir(parents=True)

        def cria(nome, dias):
            p = HD / nome
            p.write_text("x", "utf-8")
            t = time.time() - dias * 86400
            os.utime(p, (t, t))
            return p
        seus = [cria("todo.md", 9), cria(SA + "-0a1b2c3d.md", 9), cria(SX + ".usada.md", 9), cria("_req-abc.txt", 9),
                cria("_trace-abcdef1.md", 9), cria("_req-2.txt", 1)]
        meus = [cria("_req-1.txt", 9), cria("_trace-abcdef12.md", 9), cria("_detect-s1.flag", 9)]
        rodar("claude", {**SS, "source": "resume"}, CLI)
        self.assertTrue(all(p.exists() for p in seus))
        self.assertEqual([p.name for p in meus if p.exists()], [])

    def test_tipo_indeterminado_ainda_faz_a_passagem(self):  # B3: only the lock stays out
        r = rodar("claude", {**UPS, "prompt": "relay"}, {"LANG": "en_US.UTF-8"})  # no CLAUDE_CODE_ENTRYPOINT
        self.assertIn(str(HD), ctx(r))
        self.assertEqual(r["systemMessage"], EN["detect_failed"])
        self.assertIsNone(rodar("claude", PRE, {"LANG": "en_US.UTF-8"}))  # no lock
        self.escreve("passed on")
        e = rodar("claude", {**SS, "source": "clear"}, {"LANG": "en_US.UTF-8"})
        self.assertIn("passed on", ctx(e))
        with tempfile.TemporaryDirectory() as t:
            sem = rollout(t, None)
            r = rodar("codex", {**UPS, "prompt": "relay", "transcript_path": sem}, {"LANG": "en_US"})
            self.assertIn(str(HD), ctx(r))

    def test_juncao_do_windows(self):  # C1
        if os.name != "nt":
            self.skipTest("junctions exist only on Windows")
        alvo = SB / "elsewhere-j"
        alvo.mkdir(exist_ok=True)
        (alvo / (relay.slug("C:\\Proj\\A") + ".md")).write_text("planted", "utf-8")
        HD.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cmd", "/c", "mklink", "/J", str(HD), str(alvo)], check=True, capture_output=True)
        try:
            self.assertNotIn("planted", ctx(rodar("claude", {**SS, "source": "clear"}, CLI)))
            self.assertIsNone(relay.pasta_segura(str(HD), True))
        finally:
            os.rmdir(HD)

    def test_handoff_dir_invalido_cai_no_padrao(self):  # C3
        padrao = relay.handoff_dir({}, SBENV, str(SB), os.name == "nt")
        arq = SB / "umarquivo"
        arq.write_text("x", "utf-8")
        for ruim in ("relativa/pasta", str(SB / "a" / ".." / "b"), str(arq), str(SB / "a") + os.sep + ".. ",
                     str(SB / "a" / "...") + os.sep + "b"):
            r = rodar("claude", {**UPS, "prompt": "relay"}, CLI, {"handoff_dir": ruim})
            self.assertIn(padrao, ctx(r), ruim)
            self.assertNotIn("systemMessage", r)
        shutil.rmtree(padrao, ignore_errors=True)

    def test_handoff_dir_nao_criavel_entrega(self):  # C3: SessionStart resolves the folder like UserPromptSubmit
        arq = SB / "umarquivo3"
        arq.write_text("x", "utf-8")
        cfg = {"handoff_dir": str(arq / "sub")}
        with tempfile.TemporaryDirectory() as t:
            tr = rollout(t, "codex-tui")
            pedido = ctx(rodar("codex", {**UPS, "prompt": "relay", "cwd": SS["cwd"], "transcript_path": tr}, None, cfg))
            alvo = re.search(r"(\S+%s\.md)" % SA, pedido).group(1)
            Path(alvo).write_text("delivered body", "utf-8")
            r = rodar("codex", {**SS, "transcript_path": tr}, None, cfg)
            self.assertIn("delivered body", ctx(r))
        shutil.rmtree(PADRAO, ignore_errors=True)

    def test_sem_pasta_usavel_avisa(self):  # C3
        arq = SB / "umarquivo2"
        arq.write_text("x", "utf-8")
        env = {**CLI, "LOCALAPPDATA": str(arq), "XDG_STATE_HOME": str(arq), "HOME": str(arq), "USERPROFILE": str(arq)}
        r = rodar("claude", {**UPS, "prompt": "relay"}, env, {"handoff_dir": ""})
        self.assertEqual(r["systemMessage"], EN["handoff_dir_unusable"])
        self.assertNotIn("[handoff]", ctx(r))  # no file to write: no request

    def test_tabela_grande_nao_derruba_a_passagem(self):  # item 6: the reviewer's case, 5 x 3000 chars of routing
        grande = {c: {"claude": {"agent": "x" * 3000}} for c in relay.CAMADAS}
        for fonte in ("startup", "clear"):
            self.escreve("PASSAGEM INTEIRA aqui")
            c = ctx(rodar("claude", {**SS, "source": fonte}, CLI, {"routing": grande}))
            self.assertIn("PASSAGEM INTEIRA aqui", c, fonte)
            self.assertLessEqual(len(c.encode("utf-16-le")) // 2, 9000, fonte)
            self.assertIn(EN["routing_cut"], c, fonte)
        c = ctx(rodar("claude", {**SS, "source": "resume"}, CLI, {"routing": grande}))  # no handoff: the table is cut too
        self.assertLessEqual(len(c.encode("utf-16-le")) // 2, 9000)
        self.assertTrue(c.endswith(EN["routing_cut"]))

    def test_corte_em_utf16(self):  # C4
        arq = self.escreve("# Long\n" + "\U0001F600" * 20000)
        c = ctx(rodar("claude", {**SS, "source": "clear"}, CLI))
        self.assertLessEqual(len(c.encode("utf-16-le")) // 2, 9000)
        self.assertGreater(len(c), 4000)
        self.assertFalse(arq.exists())

    def test_pasta_com_link_simbolico(self):  # scenario 11
        alvo = SB / "elsewhere"
        alvo.mkdir(exist_ok=True)
        (alvo / (relay.slug("C:\\Proj\\A") + ".md")).write_text("planted", "utf-8")
        HD.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(alvo, HD, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("cannot create symlinks here (Windows without privilege)")
        try:
            self.assertNotIn("planted", ctx(rodar("claude", SS, CLI)))  # does not deliver
            r = rodar("claude", {**UPS, "prompt": "relay", "cwd": "C:\\Proj\\A"}, CLI)
            self.assertNotIn(str(HD), ctx(r))  # does not ask for a write through the link
            w = {**PRE, "tool_name": "Write", "tool_input": {"file_path": str(HD / "x.md")}}
            self.assertTrue(negou(rodar("claude", w, CLI)))
            self.assertEqual(sorted(p.name for p in alvo.iterdir()), [relay.slug("C:\\Proj\\A") + ".md"])
        finally:
            os.unlink(HD)


class Juncao(Limpo):
    """The core is the only one that delivers, in both CLIs (the band mod only triggers the switch)."""
    A, B = "aaaaaaaa-1111", "bbbbbbbb-2222"

    def pede(self, sid, pid, texto, cwd="C:\\Proj\\A"):
        c = ctx(rodar("claude", {**UPS, "prompt": "relay", "cwd": cwd, "session_id": sid}, {**CLI, "CLAUDE_PID": pid}))
        alvo = Path(re.search(r"(\S+-%s\.md)" % sid[:8], c).group(1))
        alvo.write_text(texto, "utf-8")
        return alvo

    def clear(self, pid, sid="novo-1"):
        return ctx(rodar("claude", {**SS, "source": "clear", "session_id": sid}, {**CLI, "CLAUDE_PID": pid}))

    def test_claude_para_claude_sem_band(self):  # B2: the /clear of the asking process gets its own handoff
        a = self.pede(self.A, "111", "state of A")
        b = self.pede(self.B, "222", "state of B")  # another session, same folder
        (HD / (SA + ".md")).write_text("from codex", "utf-8")  # own request wins over the Codex one
        c = self.clear("111")
        self.assertIn("state of A", c)
        self.assertNotIn("state of B", c)
        self.assertNotIn("from codex", c)
        self.assertFalse(a.exists())
        self.assertTrue(b.exists())
        self.assertIn("state of B", self.clear("222"))
        self.assertIn("from codex", self.clear("111"))  # own request already used: falls to the Codex one
        self.assertNotIn("[handoff]", self.clear("111"))  # nothing left

    def test_clear_de_outro_processo_nao_leva(self):  # sessions in one folder never swap handoffs
        a = self.pede(self.A, "111", "state of A")
        self.assertNotIn("state of A", self.clear("333"))
        self.assertTrue(a.exists())
        self.assertIn("state of A", self.clear("111"))

    def test_sem_pid_um_arquivo_recente_entrega(self):  # fallback: exactly one fresh <slug>-<8hex>.md
        a = self.pede(self.A, "", "state of A")
        self.assertIn("state of A", self.clear(""))
        self.assertFalse(a.exists())

    def test_sem_pid_dois_ou_velho_nao_entrega(self):
        a = self.pede(self.A, "", "state of A")
        b = self.pede(self.B, "", "state of B")
        self.assertNotIn("[handoff]", self.clear(""))  # two = ambiguous
        self.assertTrue(a.exists() and b.exists())
        t = time.time() - 31 * 60
        os.utime(a, (t, t))
        os.utime(b, (t, t))
        self.assertNotIn("[handoff]", self.clear(""))  # old
        self.assertTrue(a.exists() and b.exists())

    def test_marcador_vazio_e_cancelado(self):  # P2: the band blanks the marker on Cancel
        a = self.pede(self.A, "111", "state of A")
        (HD / "_req-111.txt").write_text("", "utf-8")
        self.assertNotIn("[handoff]", self.clear("111"))
        self.assertTrue(a.exists())
        self.assertNotIn("[handoff]", self.clear("111"))  # no fallback either: a PID is present

    def test_marcador_so_aceita_o_nome_da_sessao(self):  # S10: not any [a-z0-9-]+.md
        HD.mkdir(parents=True, exist_ok=True)
        (HD / "secret-notes.md").write_text("secret", "utf-8")
        (HD / "_req-555.txt").write_text("secret-notes.md", "utf-8")
        self.assertNotIn("secret", self.clear("555"))
        self.assertTrue((HD / "secret-notes.md").exists())

    def test_excecao_depois_da_posse_devolve(self):  # claimed, then processar blows up: the file goes back
        from unittest import mock
        HD.mkdir(parents=True, exist_ok=True)
        arq = HD / (SA + ".md")
        arq.write_text("keep me", "utf-8")
        env = {**SBENV, "SYNC_RELAY_CONFIG": str(SB / "config.json"), "LANG": "en_US.UTF-8",
               "CLAUDE_CODE_ENTRYPOINT": "cli"}
        (SB / "config.json").write_text(json.dumps(BASE_CFG), "utf-8")
        with mock.patch.object(relay, "_u16", side_effect=RuntimeError("boom")):
            saida, devolver = relay.processar({**SS, "source": "clear"}, "claude", env, str(SB), os.name == "nt")
        self.assertIsNone(saida)
        self.assertEqual(arq.read_text("utf-8"), "keep me")
        self.assertEqual([p.name for p in HD.iterdir()], [arq.name])

    def test_excecao_depois_da_posse_devolve_o_marcador(self):  # v0.1.1: given back with its marker, never stranded
        from unittest import mock
        a = self.pede(self.A, "111", "state of A")
        m = HD / "_req-111.txt"
        nome, quando = m.read_text("utf-8"), os.stat(m).st_mtime_ns
        env = {**SBENV, "SYNC_RELAY_CONFIG": str(SB / "config.json"), "LANG": "en_US.UTF-8",
               "CLAUDE_CODE_ENTRYPOINT": "cli", "CLAUDE_PID": "111"}
        with mock.patch.object(relay, "_u16", side_effect=RuntimeError("boom")):
            saida, _ = relay.processar({**SS, "source": "clear", "session_id": "novo-1"}, "claude", env, str(SB),
                                       os.name == "nt")
        self.assertIsNone(saida)
        self.assertTrue(a.exists())
        self.assertEqual(m.read_text("utf-8"), nome)
        self.assertEqual(os.stat(m).st_mtime_ns, quando)  # same age: the Write window does not reopen
        self.assertIn("state of A", self.clear("111"))  # the next /clear of this process still delivers

    def test_saida_que_falha_devolve_o_marcador(self):  # v0.1.1: same, when the output cannot be written
        import io
        from unittest import mock
        a = self.pede(self.A, "111", "state of A")
        nome = (HD / "_req-111.txt").read_text("utf-8")

        class Quebrado(io.StringIO):
            def write(self, s):
                raise OSError("pipe closed")
        env = {**SBENV, "SYNC_RELAY_MODE": "force", "SYNC_RELAY_CONFIG": str(SB / "config.json"),
               "LANG": "en_US.UTF-8", "CLAUDE_PID": "111"}
        entrada = io.TextIOWrapper(io.BytesIO(json.dumps({**SS, "source": "clear", "session_id": "novo-1"}).encode()))
        with mock.patch.dict(os.environ, env), mock.patch.object(sys, "stdin", entrada), \
                mock.patch.object(sys, "stdout", Quebrado()), mock.patch.object(sys, "argv", ["x", "claude"]):
            relay.main()
        self.assertTrue(a.exists())
        self.assertEqual((HD / "_req-111.txt").read_text("utf-8"), nome)
        self.assertIn("state of A", self.clear("111"))

    def test_slug_que_comeca_com_hifen(self):  # the cut of a long cwd used to start with '-'
        cwd = "C:\\Users\\alice\\projects\\demo\\" + "a" * 33 + "\\work\\sandbox\\t3\\cwd"
        self.assertFalse(relay.slug(cwd).startswith("-"))  # the readable part is cut at 60 and never starts with '-'
        a = self.pede(self.A, "111", "state of A", cwd)
        self.assertIn("state of A", ctx(rodar("claude", {**SS, "source": "clear", "cwd": cwd}, {**CLI, "CLAUDE_PID": "111"})))
        self.assertFalse(a.exists())
        PADRAO.mkdir(parents=True, exist_ok=True)
        velha = PADRAO / (relay.slug(cwd) + "-1.usada.md")
        velha.write_text("x", "utf-8")
        t = time.time() - 8 * 86400
        os.utime(velha, (t, t))
        rodar("claude", {**SS, "source": "resume"}, CLI, {"handoff_dir": ""})
        self.assertFalse(velha.exists())

    def test_entregue_nao_volta_no_codex(self):  # B1b: delivered once, never again
        self.pede(self.A, "111", "state of A")
        self.assertIn("state of A", self.clear("111"))
        with tempfile.TemporaryDirectory() as t:
            self.assertNotIn("state of A", ctx(rodar("codex", {**SS, "transcript_path": rollout(t, "codex-tui")})))

    def test_reivindica_antes_de_imprimir(self):  # C5: the rename happens before the output, not after
        arq = HD / (SA + ".md")
        HD.mkdir(parents=True, exist_ok=True)
        arq.write_text("only once", "utf-8")
        (SB / "config.json").write_text(json.dumps(BASE_CFG), "utf-8")
        env = {**SBENV, "SYNC_RELAY_MODE": "force", "SYNC_RELAY_CONFIG": str(SB / "config.json"),
               "LANG": "en_US.UTF-8"}
        saida, devolver = relay.processar({**SS, "source": "clear"}, "claude", env, str(SB), os.name == "nt")
        self.assertFalse(arq.exists())  # already claimed when processar returns
        self.assertIn("only once", ctx(saida))
        self.assertTrue(Path(devolver[0]).exists())

    def test_dois_codex_juntos_um_so_recebe(self):  # C5 under real concurrency
        with tempfile.TemporaryDirectory() as t:
            tr = rollout(t, "codex-tui")
            e = {k: v for k, v in os.environ.items() if not k.startswith(("SYNC_RELAY_", "SYNCLABS_RELAY_", "CLAUDE_CODE_", "CLAUDE_PID"))}
            cf = SB / "config.json"
            cf.write_text(json.dumps(BASE_CFG), "utf-8")
            e.update({**SBENV, "CLAUDE_PLUGIN_ROOT": str(PLUGIN), "SYNC_RELAY_CONFIG": str(cf)})
            dados = json.dumps({**SS, "transcript_path": tr}).encode()
            for rodada in range(8):
                HD.mkdir(parents=True, exist_ok=True)
                (HD / (SA + ".md")).write_text("round %d" % rodada, "utf-8")
                ps = [subprocess.Popen([sys.executable, "-I", "-c", CMD, "codex"], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, env=e, cwd=str(SB)) for _ in range(2)]
                saidas = [p.communicate(dados, timeout=60)[0].decode("ascii") for p in ps]
                self.assertEqual(sum("round %d" % rodada in s for s in saidas), 1, saidas)

    def test_saida_que_falha_devolve_a_passagem(self):  # claimed but not printed: the next session still gets it
        import io
        from unittest import mock
        HD.mkdir(parents=True, exist_ok=True)
        arq = HD / (SA + ".md")
        arq.write_text("keep me", "utf-8")

        class Quebrado(io.StringIO):
            def write(self, s):
                raise OSError("pipe closed")
        env = {**SBENV, "SYNC_RELAY_MODE": "force", "SYNC_RELAY_CONFIG": str(SB / "config.json"),
               "LANG": "en_US.UTF-8"}
        (SB / "config.json").write_text(json.dumps(BASE_CFG), "utf-8")
        entrada = io.TextIOWrapper(io.BytesIO(json.dumps({**SS, "source": "clear"}).encode()))
        with mock.patch.dict(os.environ, env), mock.patch.object(sys, "stdin", entrada), \
                mock.patch.object(sys, "stdout", Quebrado()), mock.patch.object(sys, "argv", ["x", "claude"]):
            relay.main()
        self.assertEqual(arq.read_text("utf-8"), "keep me")


class EscritaDaPassagem(Limpo):
    def setUp(self):
        super().setUp()
        HD.mkdir(parents=True)  # the handoff request creates it before the model writes

    def w(self, caminho, ferr="Write", cli="claude"):
        return rodar(cli, {**PRE, "tool_name": ferr, "tool_input": {"file_path": caminho}}, CLI)

    def test_so_a_pasta(self):
        ok = str(HD / (SX + ".md"))
        self.assertIsNone(self.w(ok))
        self.assertIsNone(self.w(ok.replace("\\", "/")))
        if os.name == "nt":  # NTFS is case-insensitive
            self.assertIsNone(self.w(str(HD / "A.MD")))
        for ruim in (str(HD / ".." / "x.md"), str(HD / "sub" / "x.md"), "C:\\outro\\x.md", str(HD / "x.txt"),
                     str(HD / "a.txt:x.md"), str(HD / "a.md:x"), "c-x.md", ""):
            self.assertTrue(negou(self.w(ruim)), ruim)
        self.assertTrue(negou(self.w(ok, "Edit")))
        self.assertTrue(negou(self.w(ok, "Bash")))


class PermissaoDaPassagem(Limpo):  # P1: allow only for the Write of this session's own handoff file
    CWD = "C:\\Proj\\A"

    def setUp(self):
        super().setUp()
        self.env = {**CLI, "CLAUDE_PID": "111"}
        c = ctx(rodar("claude", {**UPS, "prompt": "relay", "cwd": self.CWD, "session_id": "aaaaaaaa-1111"}, self.env))
        self.alvo = re.search(r"(\S+-aaaaaaaa\.md)", c).group(1)

    def pre(self, caminho=None, env=None, cfg=None, conteudo="x", **extra):
        ti = {"file_path": caminho or self.alvo}
        if conteudo is not None:
            ti["content"] = conteudo
        e = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": self.CWD, "session_id": "aaaaaaaa-1111",
             "tool_input": ti, **extra}
        return rodar("claude", e, env or self.env, cfg)

    def permitiu(self, s):
        return bool(s) and s.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_tudo_certo_permite_em_qualquer_modo(self):
        for cfg in (None, {"mode": "remind"}, {"mode": "off"}):
            self.assertTrue(self.permitiu(self.pre(cfg=cfg)), cfg)
        self.assertTrue(self.permitiu(self.pre(self.alvo.replace("\\", "/"))))

    def test_cada_condicao_falhando_nao_permite(self):
        nome = Path(self.alvo).name
        casos = {
            "subagente": lambda: self.pre(agent_id="a1"),
            "outra ferramenta": lambda: self.pre(tool_name="Edit"),
            "sem pid": lambda: self.pre(env=CLI),
            "outro pid": lambda: self.pre(env={**CLI, "CLAUDE_PID": "222"}),
            "outro nome": lambda: self.pre(str(HD / (SA + "-bbbbbbbb.md"))),
            "outro slug": lambda: self.pre(str(HD / "secret-notes.md")),
            "..": lambda: self.pre(str(HD / ".." / HD.name / nome)),
            "subpasta": lambda: self.pre(str(HD / "sub" / nome)),
            "ADS": lambda: self.pre(self.alvo + ":x"),
            "conteudo grande": lambda: self.pre(conteudo="x" * 8001),
            "sem conteudo": lambda: self.pre(conteudo=None),
            "outro cwd": lambda: self.pre(cwd="C:\\Outra"),
        }
        for rotulo, f in casos.items():
            self.assertFalse(self.permitiu(f()), rotulo)
        self.assertTrue(self.permitiu(self.pre(conteudo="x" * 8000)))

    def test_marcador_velho_vazio_ou_ausente(self):
        m = HD / "_req-111.txt"
        t = time.time() - 11 * 60
        os.utime(m, (t, t))
        self.assertFalse(self.permitiu(self.pre()), "old")
        m.write_text("", "utf-8")
        self.assertFalse(self.permitiu(self.pre()), "empty")
        m.unlink()
        self.assertFalse(self.permitiu(self.pre()), "missing")

    def test_alvo_que_e_link_nao_permite(self):
        (HD / "fora.md").write_text("x", "utf-8")
        try:
            os.symlink(HD / "fora.md", self.alvo)
        except (OSError, NotImplementedError):
            self.skipTest("no symlink privilege")
        self.assertFalse(self.permitiu(self.pre()))

    def test_codex_e_pasta_ausente_nao_permitem(self):
        e = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": self.CWD,
             "tool_input": {"file_path": self.alvo, "content": "x"}}
        self.assertFalse(self.permitiu(rodar("codex", e, self.env)))
        shutil.rmtree(HD)
        self.assertFalse(self.permitiu(self.pre()))


class Stop(Limpo):
    def test_claude_scenario_9(self):  # floor 10k: 160k is exactly +150k, 140k is +130k
        with tempfile.TemporaryDirectory() as t:
            side = {"type": "assistant", "isSidechain": True, "message": {"usage": {
                "input_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 900000}}}
            alto = transcript_claude(t, "alto", [10000, 160000], [side])
            baixo = transcript_claude(t, "baixo", [10000, 140000], [side])
            unico = transcript_claude(t, "unico", [160000])
            msg = rodar("claude", {**STOP, "transcript_path": alto}, CLI)["systemMessage"]
            self.assertIn("160k", msg)
            self.assertIn("+150k", msg)
            self.assertIn("switch point (160k)", msg)  # floor 10k + min(150k, 0.8 x (200k - 10k)): unknown model = 200K window
            self.assertIn("Type relay (or /relay on Claude Code)", msg)  # the word works without the band and on Codex
            self.assertNotIn("Type: handoff", msg)
            self.assertIsNone(rodar("claude", {**STOP, "transcript_path": baixo}, CLI))
            self.assertIsNone(rodar("claude", {**STOP, "transcript_path": unico}, CLI))  # no floor: no warning
            self.assertIsNone(rodar("claude", {**STOP, "transcript_path": alto}, CLI, {"stop_warning": False}))
            self.assertIsNone(rodar("claude", {**STOP, "transcript_path": alto, "stop_hook_active": True}, CLI))
            self.assertIsNone(rodar("claude", {**STOP, "transcript_path": alto, "agent_id": "a"}, CLI))
            self.assertIsNone(rodar("claude", {**STOP, "transcript_path": alto}, {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))
            self.assertIsNotNone(rodar("claude", {**STOP, "transcript_path": baixo}, CLI, {"threshold_tokens": 100000}))
            self.assertIsNotNone(rodar("claude", {**STOP, "transcript_path": alto}, {**CLI, "SYNC_RELAY_MODE": "off"}))
            self.assertIsNone(rodar("claude", {**STOP, "transcript_path": os.path.join(t, "nope.jsonl")}, CLI))

    def test_subagente_rodando_adia_o_aviso(self):  # v0.1.1: format measured in claude -p 2.1.329 (Stop input)
        sub = {"id": "a954cfc0cbd3f8644", "type": "subagent", "status": "running", "description": "bg sleeper",
               "agent_type": "general-purpose"}
        shell = {"id": "b7lan9eo0", "type": "shell", "status": "running", "description": "dev server", "command": "npm run dev"}
        with tempfile.TemporaryDirectory() as t:
            alto = {**STOP, "transcript_path": transcript_claude(t, "alto", [10000, 160000])}
            self.assertIsNone(rodar("claude", {**alto, "background_tasks": [sub, shell]}, CLI))  # warns at the turn its report brings
            for bt in ([shell], [], None, "junk", [None, 3]):  # a shell may never end (a server): it never holds the warning
                self.assertIn("systemMessage", rodar("claude", {**alto, "background_tasks": bt}, CLI), bt)
        # SubagentStop carries the same field: the report limit still applies
        r = rodar("claude", {**SubagentStop.SUB, "background_tasks": [sub]}, CLI)
        self.assertEqual(r["decision"], "block")

    def test_codex(self):
        with tempfile.TemporaryDirectory() as t:
            alto = rollout(t, "codex-tui", 245000, primeiro=90000)
            quase = rollout(t, "codex-tui", 230000, primeiro=90000)
            msg = rodar("codex", {**STOP, "transcript_path": alto})["systemMessage"]
            self.assertIn("245k", msg)
            self.assertIn("155k", msg)
            self.assertRegex(msg, r"(Type relay \(or|Digite relay \(ou) /relay")  # language follows the machine; the word works on Codex
            self.assertIsNone(rodar("codex", {**STOP, "transcript_path": quase}))
            self.assertIsNone(rodar("codex", {**STOP, "transcript_path": rollout(t, "codex-tui", 245000)}))  # no floor
            self.assertIsNone(rodar("codex", {**STOP, "transcript_path": rollout(t, "codex_exec", 245000, primeiro=90000)}))
            sub = rollout(t, "codex-tui", 245000, {"subagent": {}}, primeiro=90000)
            self.assertIsNone(rodar("codex", {**STOP, "transcript_path": sub}))
            self.assertIsNotNone(rodar("codex", {**STOP, "transcript_path": quase}, cfg={"threshold_tokens": 100000}))


def modelo_claude(pasta, nome, totais, modelo):
    """Like transcript_claude, with a model id on every assistant response (the last one is read)."""
    p = transcript_claude(pasta, nome, totais)
    linhas = [json.loads(x) for x in Path(p).read_text("utf-8").splitlines()]
    for x in linhas:
        if x.get("type") == "assistant":
            x["message"]["model"] = modelo
    Path(p).write_text("\n".join(json.dumps(x) for x in linhas) + "\n", "utf-8")
    return p


class PontoDeTroca(Limpo):  # v0.1.1: switch = floor + min(D, 0.8 x (C - floor)), shared vectors with the mod
    CASOS = VET["compaction_cases"]["cases"]

    def test_vetores_compactacao_e_troca(self):
        for k in self.CASOS:
            c, origem = relay.compactacao(k["cli"], k["model"], k["env"], k["settings"], k["codex_limit"])
            self.assertEqual((c, origem), (k["c"], k["origem"]), k["name"])
            self.assertEqual(relay.ponto_de_troca(k["floor"], k["threshold"] or 150000, c), k["switch"], k["name"])

    def test_exemplos_do_dono(self):  # floor 30k
        por = {k["name"]: k["switch"] for k in self.CASOS}
        self.assertEqual(por["claude_1m_opus_4_7"], 180000)
        self.assertEqual(por["claude_200k_sonnet_4_6"], 166000)
        self.assertEqual(por["codex_limit_120k"], 102000)
        self.assertEqual(por["codex_no_limit"], 180000)
        self.assertEqual(por["threshold_300k_claude_200k"], 166000)

    def stop(self, cli, caminho, env=None, cfg=None):
        return rodar(cli, {**STOP, "transcript_path": caminho}, {**CLI, **(env or {})}, cfg)

    def test_stop_claude_pelo_modelo_do_transcript(self):  # floor 30k: 1M model switches at 180k, 200K model at 166k
        with tempfile.TemporaryDirectory() as t:
            for modelo, total, avisa in (("claude-opus-4-7", 170000, False), ("claude-opus-4-7", 180000, True),
                                         ("claude-sonnet-4-6", 165000, False), ("claude-sonnet-4-6", 166000, True),
                                         ("claude-sonnet-4-6[1m]", 166000, False)):
                tr = modelo_claude(t, "m-%s-%d" % (modelo[-6:], total), [30000, total], modelo)
                r = self.stop("claude", tr)
                self.assertEqual(r is not None, avisa, (modelo, total))
            tr = modelo_claude(t, "m1", [30000, 180000], "claude-opus-4-7")
            self.assertIn("switch point (180k)", self.stop("claude", tr)["systemMessage"])
            # threshold_tokens 300000 with a 200K model: the ceiling still applies
            tr = modelo_claude(t, "m2", [30000, 166000], "claude-sonnet-4-6")
            self.assertIsNotNone(self.stop("claude", tr, cfg={"threshold_tokens": 300000}))
            tr = modelo_claude(t, "m3", [30000, 165000], "claude-sonnet-4-6")
            self.assertIsNone(self.stop("claude", tr, cfg={"threshold_tokens": 300000}))

    def test_stop_claude_com_env_e_settings(self):
        with tempfile.TemporaryDirectory() as t:
            tr = modelo_claude(t, "e1", [30000, 126000], "claude-opus-4-7")
            self.assertIsNone(self.stop("claude", tr))  # 1M model: switch at 180k
            cc = Path(t) / "cc"
            cc.mkdir()
            (cc / "settings.json").write_text(json.dumps({"autoCompactWindow": 150000}), "utf-8")
            self.assertIsNotNone(self.stop("claude", tr, {"CLAUDE_CONFIG_DIR": str(cc)}))  # settings: 126k
            (cc / "settings.json").write_text("{broken", "utf-8")
            self.assertIsNone(self.stop("claude", tr, {"CLAUDE_CONFIG_DIR": str(cc)}))  # unreadable: ignored
            for bruto in ('1e400', 'NaN', 'Infinity', '-Infinity'):  # not finite: ignored, the warning stays (model: 180k)
                (cc / "settings.json").write_text('{"autoCompactWindow": %s}' % bruto, "utf-8")
                tr2 = modelo_claude(t, "inf" + bruto[-3:], [30000, 180000], "claude-opus-4-7")
                self.assertIn("switch point (180k)", self.stop("claude", tr2, {"CLAUDE_CONFIG_DIR": str(cc)})["systemMessage"], bruto)
            self.assertIsNotNone(self.stop("claude", tr, {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "150000"}))
            self.assertIsNone(self.stop("claude", tr, {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "100"}))  # 967k: still 180k

    def test_stop_codex_com_config_toml(self):  # floor 30k: limit 120k -> 102k; none -> 180k
        with tempfile.TemporaryDirectory() as t:
            ch = Path(t) / "ch"
            ch.mkdir()
            env = {"CODEX_HOME": str(ch)}
            alto = rollout(t, "codex-tui", 110000, primeiro=30000)
            self.assertIsNone(self.stop("codex", alto, env))  # no file: no ceiling, 180k
            (ch / "config.toml").write_text('model = "x"\nmodel_auto_compact_token_limit = 120000  # comment\n[profiles.p]\n', "utf-8")
            self.assertIn("switch point (102k)", self.stop("codex", alto, env)["systemMessage"])
            (ch / "config.toml").write_text('[profiles.p]\nmodel_auto_compact_token_limit = 120000\n', "utf-8")
            self.assertIsNone(self.stop("codex", alto, env))  # a key inside a table is not the global one
            (ch / "config.toml").write_text('model_auto_compact_token_limit = "x"\n', "utf-8")
            self.assertIsNone(self.stop("codex", alto, env))
            (ch / "config.toml").write_text('model_auto_compact_token_limit = 120_000\n', "utf-8")  # TOML underscores
            self.assertIn("switch point (102k)", self.stop("codex", alto, env)["systemMessage"])
            for ruim in ("_120000", "120000_", "120__000"):
                (ch / "config.toml").write_text('model_auto_compact_token_limit = %s\n' % ruim, "utf-8")
                self.assertIsNone(self.stop("codex", alto, env), ruim)


class SubagentStop(Limpo):  # scenario 10
    SUB = {"hook_event_name": "SubagentStop", "agent_id": "a1", "stop_hook_active": False, "session_id": "s-1",
           "last_assistant_message": "x" * 5000}

    def test_bloqueia_uma_vez(self):
        r = rodar("claude", self.SUB, CLI)
        self.assertEqual(r["decision"], "block")
        self.assertIn("4000", r["reason"])
        self.assertIsNone(rodar("claude", {**self.SUB, "stop_hook_active": True}, CLI))
        self.assertIsNone(rodar("claude", self.SUB, {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))
        self.assertIsNone(rodar("claude", {**self.SUB, "last_assistant_message": "x" * 4000}, CLI))
        self.assertIsNone(rodar("claude", self.SUB, CLI, {"report_max_chars": 0}))
        self.assertIsNone(rodar("claude", {**self.SUB, "last_assistant_message": "x" * 5000}, CLI, {"report_max_chars": 6000}))
        self.assertIsNone(rodar("claude", {k: v for k, v in self.SUB.items() if k != "last_assistant_message"}, CLI))
        self.assertIsNone(rodar("claude", self.SUB, CLI, {"mode": "remind"}))
        self.assertIsNone(rodar("claude", self.SUB, CLI, {"mode": "off"}))

    def test_codex_sem_campo_nao_faz_nada(self):
        with tempfile.TemporaryDirectory() as t:
            sub = rollout(t, "codex-tui", source={"subagent": {}})
            self.assertEqual(rodar("codex", {**self.SUB, "transcript_path": sub})["decision"], "block")
            self.assertIsNone(rodar("codex", {**self.SUB, "transcript_path": rollout(t, "codex_exec")}))
            self.assertIsNone(rodar("codex", {"hook_event_name": "SubagentStop", "transcript_path": sub}))


class Robustez(Limpo):
    def test_config_bom_quebrada_e_chave_estranha(self):  # scenario 12
        bom = b"\xef\xbb\xbf" + json.dumps({**BASE_CFG, "mode": "remind", "banana": 1}).encode()
        self.assertIsNone(rodar("claude", PRE, CLI, cru=bom))  # remind: BOM stripped, config applied, unknown key ignored
        self.assertEqual(ctx(rodar("claude", UPS, CLI, cru=bom)), EN["reminder"])
        for lixo in (b"{broken", b"[1,2]", b"", b'{"mode": 7, "threshold_tokens": "x", "routing": 3, "lang": []}'):
            self.assertTrue(negou(rodar("claude", PRE, CLI, cru=lixo)), lixo)  # defaults: enforce
            self.assertIsNotNone(rodar("claude", UPS, CLI, cru=lixo))
        miss = rodar("claude", PRE, {**CLI, "SYNC_RELAY_CONFIG": str(SB / "missing.json")})
        self.assertTrue(negou(miss))  # missing file: defaults

    def test_config_muito_aninhada_nao_desliga_a_trava(self):  # C2
        self.assertTrue(negou(rodar("claude", PRE, CLI, cru=b"[" * 100000)))

    def test_sem_entrypoint_avisa_uma_vez(self):  # scenario 13
        env = {"LANG": "en_US.UTF-8"}
        a = rodar("claude", PRE, env)
        self.assertEqual(a, {"systemMessage": EN["detect_failed"]})
        self.assertIsNone(rodar("claude", PRE, env))
        self.assertEqual(rodar("claude", {**PRE, "session_id": "s-2"}, env), {"systemMessage": EN["detect_failed"]})
        self.assertIsNone(rodar("claude", {**PRE, "session_id": "s-2", "tool_name": "Bash"}, env))
        self.assertIsNone(rodar("claude", {**PRE, "session_id": "s-3", "agent_id": "a"}, env))  # subagent: nothing to detect
        self.assertIsNone(rodar("claude", {**PRE, "session_id": "s-4"}, {**env, "SYNC_RELAY_MODE": "off"}))

    def test_codex_sem_originator_avisa(self):
        with tempfile.TemporaryDirectory() as t:
            sem = rollout(t, None)
            r = rodar("codex", {**PRE, "tool_name": "Bash", "transcript_path": sem}, {"LANG": "en_US"})
            self.assertEqual(r, {"systemMessage": EN["detect_failed"]})
            self.assertIsNone(rodar("codex", {**PRE, "tool_name": "Bash", "transcript_path": sem}, {"LANG": "en_US"}))

    def test_ascii_com_cp1252(self):  # scenario 14
        HD.mkdir(parents=True)
        (HD / (SA + ".md")).write_text("next: X \u2192 a\u00e7\u00e3o \u2713 decis\u00e3o", "utf-8")
        r = rodar("claude", {**SS, "source": "clear"}, {**CLI, "PYTHONIOENCODING": "cp1252"})
        self.assertIn("next: X", ctx(r))  # decoded back from \u escapes
        self.assertIn("a\u00e7\u00e3o \u2713", ctx(r))
        rodar("claude", {**UPS, "prompt": "relay"}, {**CLI, "LANG": "pt_BR.UTF-8"})  # pt-BR text with accents

    def test_entrada_com_bom(self):  # Windows PowerShell 5.1 pipes stdin with a BOM when $OutputEncoding is UTF-8
        bom = b"\xef\xbb\xbf" + json.dumps(PRE).encode() + b"\r\n"
        self.assertTrue(negou(rodar("claude", bom, CLI)))

    def test_entrada_nao_json(self):  # scenario 15
        for lixo in (b"not json", b"", b"[]", b"null", b"\xff\xfe"):
            self.assertIsNone(rodar("claude", lixo, CLI), lixo)
            self.assertIsNone(rodar("codex", lixo), lixo)

    def test_sem_rede(self):
        src = SCRIPT.read_text("utf-8")
        self.assertIsNone(re.search(r"urllib|http\.client|socket|requests|fetch\(", src))


def _bash(cmd, cfg=None, cwd=None, cli="claude", env=None, extra=None):
    e = {**CLI, **(env or {})} if cli == "claude" else (env or {})
    return rodar(cli, {**PRE, "tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd or str(SB), **(extra or {})}, e, cfg)


def _lido(caminho, **ti):
    return rodar("claude", {**PRE, "tool_name": "Read", "tool_input": {"file_path": str(caminho), **ti}, "cwd": str(SB)}, CLI)


class Leitura(Limpo):  # v0.2.1: reads on the main session. The seed lives in the default config, the structure is fixed
    def setUp(self):
        super().setUp()
        self.peq = SB / "small.txt"
        self.peq.write_text("x" * 100, "utf-8")
        self.gra = SB / "big.txt"
        self.gra.write_text("x" * (70 * 1024), "utf-8")

    def test_semente_libera(self):
        for c in ("git status", "git status -s", "git log --oneline -5", "git diff --stat", "git diff --stat HEAD",
                  "git diff --name-only main", "git branch", "ls", "ls -la src", "pwd", "git --version",
                  "cat small.txt", "head -n 5 small.txt", "tail -n 5 small.txt"):
            self.assertIsNone(_bash(c), c)

    def test_escapes_negados(self):  # the structural rule (b): one simple command, no shell metacharacter
        for c in ("git status | sh", "git status; rm -rf x", "git status && rm x", "git status || rm x",
                  "git log $(rm x)", "git log `rm x`", "ls > out", "ls < in", "cat small.txt > b", "git status &",
                  "ls; rm x", 'ls "a; rm b"', "ls 'a' && rm b", "git status\nrm x", "git status\r\nrm x",
                  "git -c core.pager=x status", "git log --output=f", "git log --outp=f", "git diff --stat -o f",
                  "tail -f small.txt", "tail -fn 5 small.txt", "tail -F small.txt", "tail --follow small.txt",
                  "ls $HOME", "rm -rf x", "git commit -m x", "git branch -D x", "git push", "ls (rm x)"):
            self.assertTrue(negou(_bash(c)), c)

    def test_arquivo_grande(self):
        self.assertTrue(negou(_bash("cat big.txt")))
        self.assertTrue(negou(_bash("head -n 3 big.txt")))
        self.assertTrue(negou(_bash("tail -n 3 big.txt")))
        self.assertTrue(negou(_bash("cat")))  # stdin would hang
        self.assertIsNone(_bash("cat big.txt", {"read_max_kb": 100}))

    def test_configuravel(self):
        self.assertTrue(negou(_bash("git status", {"allow_reads": False})))
        self.assertTrue(negou(_bash("git status", {"read_commands": []})))
        self.assertIsNone(_bash("echo hi", {"read_commands": ["echo *"]}))
        self.assertTrue(negou(_bash("git status", {"read_commands": ["echo *"]})))
        self.assertTrue(negou(_bash("echo hi; ls", {"read_commands": ["echo *"]})))  # structure holds for any pattern
        self.assertTrue(negou(_bash("anything", {"read_commands": ["*"]})))  # a pattern with no literal word is ignored

    def test_subagente_e_codex(self):
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "Bash", "tool_input": {"command": "rm x"}, "agent_id": "a1"}, CLI))
        with tempfile.TemporaryDirectory() as t:
            tui = rollout(t, "codex-tui")
            self.assertIsNone(_bash("git status", cli="codex", extra={"transcript_path": tui}))
            self.assertTrue(negou(_bash("git status; ls", cli="codex", extra={"transcript_path": tui})))

    def test_read_tool(self):
        self.assertIsNone(_lido(self.peq))
        self.assertTrue(negou(_lido(self.gra)))
        self.assertIsNone(_lido(self.gra, limit=200))
        self.assertTrue(negou(_lido(self.gra, limit=201)))
        self.assertTrue(negou(_lido(self.gra, limit=0)))
        self.assertTrue(negou(_lido(self.gra, limit="5")))
        self.assertIsNone(_lido(SB / "nofile.txt"))
        self.assertTrue(negou(rodar("claude", {**PRE, "tool_name": "Read", "tool_input": {}}, CLI)))
        for cfg, esperado in (({"read_max_kb": 100}, True), ({"read_max_lines": 300}, True), ({"allow_reads": False}, False)):
            r = rodar("claude", {**PRE, "tool_name": "Read", "tool_input": {"file_path": str(self.gra), "limit": 250}, "cwd": str(SB)}, CLI, cfg)
            self.assertEqual(r is None, esperado, cfg)
        self.assertTrue(negou(rodar("claude", {**PRE, "tool_name": "Read", "tool_input": {"file_path": str(self.peq)}, "cwd": str(SB)}, CLI, {"allow_reads": False})))

    def test_semente_no_config_padrao(self):  # not a hidden rule: the seed is the default value of read_commands
        self.assertIn("git status", relay.PADRAO["read_commands"])
        self.assertEqual(relay.PADRAO["read_max_kb"], 64)
        self.assertEqual(relay.PADRAO["read_max_lines"], 200)
        self.assertIs(relay.PADRAO["allow_reads"], True)


class ArquivoDoRepo(Limpo):  # v0.2.1: <repo>/.claude/sync_relay.json only loosens
    def setUp(self):
        super().setUp()
        self.repo = SB / "repo"
        shutil.rmtree(self.repo, ignore_errors=True)
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / ".claude").mkdir()
        (self.repo / "sub" / "deep").mkdir(parents=True)
        self.arq = self.repo / ".claude" / "sync_relay.json"
        self.arq.write_text(json.dumps({"allowed_commands": ["cargo xtask ci", "cargo xtask ci *"]}), "utf-8")

    def test_libera_e_avisa_uma_vez(self):
        r = _bash("cargo xtask ci", cwd=str(self.repo / "sub" / "deep"))  # parent up to the git root
        self.assertEqual(list(r), ["systemMessage"])
        self.assertIn("sync_relay: ", r["systemMessage"])
        self.assertIn("sync_relay.json", r["systemMessage"])
        self.assertIn("`cargo xtask ci`", r["systemMessage"])
        self.assertIsNone(_bash("cargo xtask ci", cwd=str(self.repo)))  # once per session
        self.assertIsNone(_bash("cargo xtask ci --locked", cwd=str(self.repo)))
        r2 = _bash("cargo xtask ci", cwd=str(self.repo), extra={"session_id": "s-other"})
        self.assertIn("systemMessage", r2)

    def test_so_o_que_o_arquivo_diz(self):
        for c in ("cargo build", "cargo xtask ci; rm x", "cargo xtask ci | sh", "cargo xtaskx ci", "cargo xtask cix", "rm x"):
            self.assertTrue(negou(_bash(c, cwd=str(self.repo))), c)

    def test_nunca_aperta(self):
        self.arq.write_text(json.dumps({"allowed_commands": [], "read_commands": [], "allow_reads": False}), "utf-8")
        self.assertIsNone(_bash("git status", cwd=str(self.repo)))

    def test_quebrado_ignorado(self):
        for lixo in (b"{broken", b"[1]", b'{"allowed_commands": "cargo"}', b'{"allowed_commands": [1, 2]}', b""):
            self.arq.write_bytes(lixo)
            self.assertTrue(negou(_bash("cargo xtask ci", cwd=str(self.repo))), lixo)
            self.assertIsNone(_bash("git status", cwd=str(self.repo)), lixo)

    def test_so_ate_a_raiz_do_repo(self):
        (SB / ".claude").mkdir(exist_ok=True)
        (SB / ".claude" / "sync_relay.json").write_text(json.dumps({"allowed_commands": ["make *"]}), "utf-8")
        try:
            self.assertTrue(negou(_bash("make all", cwd=str(self.repo / "sub"))))
        finally:
            shutil.rmtree(SB / ".claude", ignore_errors=True)

    def test_funciona_com_allow_reads_off(self):  # an explicit repo opt-in is not the read list
        self.assertIn("systemMessage", _bash("cargo xtask ci", {"allow_reads": False}, cwd=str(self.repo)))

    def test_sem_git_so_o_cwd(self):
        solto = SB / "solto"
        (solto / ".claude").mkdir(parents=True, exist_ok=True)
        (solto / ".claude" / "sync_relay.json").write_text(json.dumps({"allowed_commands": ["make *"]}), "utf-8")
        (solto / "x").mkdir(exist_ok=True)
        self.assertIn("systemMessage", _bash("make all", cwd=str(solto)))
        self.assertTrue(negou(_bash("make all", cwd=str(solto / "x"))))

    def test_subagente_ignora(self):
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "Bash", "tool_input": {"command": "cargo xtask ci"},
                                           "cwd": str(self.repo), "agent_id": "a"}, CLI))


class ModoDaSessao(Limpo):  # v0.2.1: /relay off | remind | on, typed as a word when there is no mod
    P1 = {"CLAUDE_PID": "4242"}

    def digitar(self, texto, env=None, **extra):
        return rodar("claude", {**UPS, "prompt": texto, **extra}, {**CLI, **(env or self.P1)})

    def test_off_remind_on(self):
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, **self.P1})))
        r = self.digitar("relay off")
        self.assertIn("systemMessage", r)
        self.assertIn("OFF", r["systemMessage"])
        self.assertIsNone(rodar("claude", PRE, {**CLI, **self.P1}))
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, "CLAUDE_PID": "999"})))  # another process keeps its mode
        self.assertTrue(negou(rodar("claude", PRE, CLI)))  # no pid, other session id: untouched
        self.digitar("/Relay  REMIND")
        self.assertIsNone(rodar("claude", PRE, {**CLI, **self.P1}))
        self.assertEqual(ctx(rodar("claude", UPS, {**CLI, **self.P1})), EN["reminder"])
        self.digitar("relay on")
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, **self.P1})))

    def test_vence_env_e_config(self):
        self.digitar("relay off")
        self.assertIsNone(rodar("claude", PRE, {**CLI, **self.P1, "SYNC_RELAY_MODE": "enforce"}, {"mode": "enforce"}))
        self.digitar("relay on")
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, **self.P1, "SYNC_RELAY_MODE": "off"}, {"mode": "off"})))

    def test_so_a_mensagem_inteira(self):
        for t in ("please relay off", "relay off now", "relay offf", "relay"):
            self.digitar(t)
            self.assertTrue(negou(rodar("claude", PRE, {**CLI, **self.P1})), t)

    def test_sobrevive_ao_clear_e_id_novo(self):
        self.digitar("relay off")
        rodar("claude", {**SS, "source": "clear", "session_id": "novo"}, {**CLI, **self.P1})
        self.assertIsNone(rodar("claude", {**PRE, "session_id": "novo"}, {**CLI, **self.P1}))

    def test_subagente_nao_aciona(self):
        self.digitar("relay off", env={"CLAUDE_PID": "7"}, agent_id="a")  # a subagent never submits prompts: ignored
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, "CLAUDE_PID": "7"})))

    def test_codex_por_session_id(self):
        with tempfile.TemporaryDirectory() as t:
            tui = rollout(t, "codex-tui")
            ups = {**UPS, "transcript_path": tui, "session_id": "cx-1"}
            pre = {**PRE, "tool_name": "Bash", "transcript_path": tui, "session_id": "cx-1"}
            self.assertTrue(negou(rodar("codex", pre)))
            self.assertIn("systemMessage", rodar("codex", {**ups, "prompt": "relay off"}))
            self.assertIsNone(rodar("codex", pre))
            self.assertTrue(negou(rodar("codex", {**pre, "session_id": "cx-2"})))

    def test_arquivo_velho_e_limpo(self):
        self.digitar("relay off")
        f = next(Path(relay.handoff_dir(BASE_CFG, SBENV, str(SB), os.name == "nt")).glob("_modo-*.txt"))
        velho = time.time() - 8 * 86400
        os.utime(f, (velho, velho))
        rodar("claude", {**SS, "session_id": "z"}, CLI)
        self.assertFalse(f.exists())

    def test_recusa_diz_como_desligar(self):
        for t in (EN, PT):  # review F: the model is never taught the way out; only the user is
            for palavra in ("relay off", "relay remind", "SYNC_RELAY_MODE", "read_commands", "sync_relay.json"):
                self.assertNotIn(palavra, t["denied"])
            self.assertIn("/relay off", t["lock_hint"])


class AliasAntigo(Limpo):  # v0.2.1: SYNCLABS_RELAY_* still work until 0.4.0
    def test_modo(self):
        self.assertIsNone(rodar("claude", PRE, {**CLI, "SYNCLABS_RELAY_MODE": "off"}))
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, "SYNCLABS_RELAY_MODE": "off", "SYNC_RELAY_MODE": "enforce"})))

    def test_lingua_e_config(self):
        self.assertEqual(ctx(rodar("claude", UPS, {**CLI, "SYNCLABS_RELAY_LANG": "pt-BR"})), PT["reminder"])
        cf = SB / "velha.json"
        cf.write_text(json.dumps({"mode": "off"}), "utf-8")
        # rodar() always sets SYNC_RELAY_CONFIG: drop it through a custom run
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SYNC_RELAY_", "SYNCLABS_RELAY_", "CLAUDE_CODE_"))}
        e.update(SBENV)
        e.update({"CLAUDE_PLUGIN_ROOT": str(PLUGIN), "SYNCLABS_RELAY_CONFIG": str(cf), **CLI})
        r = subprocess.run([sys.executable, "-I", "-c", CMD, "claude"], input=json.dumps(PRE).encode(), capture_output=True, env=e, cwd=str(SB), timeout=60)
        self.assertEqual(r.stdout.strip(), b"")  # config "off" applied through the old name

    def test_aviso_unico(self):
        env = {**CLI, "SYNCLABS_RELAY_MODE": "remind"}
        a = rodar("claude", UPS, env)
        self.assertIn("0.4.0", a["systemMessage"])
        self.assertIn("SYNCLABS_RELAY_MODE", a["systemMessage"])
        self.assertNotIn("systemMessage", rodar("claude", UPS, env) or {})
        self.assertNotIn("systemMessage", rodar("claude", UPS, CLI) or {})


class SubagenteComTarefa(Limpo):  # v0.2.1: do not let a subagent vanish while a background task runs
    TAREFA = {"id": "t1", "type": "shell", "status": "running", "description": "sleep", "command": "sleep 200"}

    def sub(self, tarefas, **kw):
        return {"hook_event_name": "SubagentStop", "agent_id": kw.pop("agent_id", "a1"), "stop_hook_active": False,
                "session_id": "s-1", "last_assistant_message": "parcial", "background_tasks": tarefas, **kw}

    def test_bloqueia_com_tarefa_rodando(self):
        r = rodar("claude", self.sub([self.TAREFA]), CLI)
        self.assertEqual(r["decision"], "block")
        self.assertIn("1", r["reason"])
        self.assertIn("final", r["reason"])

    def test_nao_bloqueia(self):
        self.assertIsNone(rodar("claude", self.sub([]), CLI))
        self.assertIsNone(rodar("claude", self.sub([self.TAREFA], stop_hook_active=True), CLI))
        self.assertIsNone(rodar("claude", self.sub([{**self.TAREFA, "type": "subagent"}]), CLI))  # parallel subagents do not hold each other
        self.assertIsNone(rodar("claude", self.sub([{**self.TAREFA, "status": "completed"}]), CLI))
        self.assertIsNone(rodar("claude", self.sub([self.TAREFA]), CLI, {"mode": "off"}))
        self.assertIsNone(rodar("claude", self.sub([self.TAREFA]), {**CLI, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))
        self.assertIsNone(rodar("claude", {k: v for k, v in self.sub([self.TAREFA]).items() if k != "background_tasks"}, CLI))
        self.assertIsNone(rodar("claude", {**self.sub([self.TAREFA]), "background_tasks": "x"}, CLI))

    def test_limite_de_blocos(self):
        r = [rodar("claude", self.sub([self.TAREFA], agent_id="a9"), CLI) for _ in range(4)]
        self.assertEqual([bool(x) for x in r], [True, True, False, False])
        self.assertTrue(rodar("claude", self.sub([self.TAREFA], agent_id="a10"), CLI))  # another agent has its own count

    def test_tabela_tem_comando_longo(self):
        r = rodar("claude", SS, CLI)
        self.assertIn(EN["long_command"], ctx(r))
        self.assertIn("180", EN["long_command"])
        r = rodar("claude", SS, {**CLI, "LANG": "pt_BR.UTF-8"})
        self.assertIn(PT["long_command"], ctx(r))


def _ss_msg(r):
    return (r or {}).get("systemMessage", "")


class Revisao021(Limpo):  # review of v0.2.1: findings A-F, each one failed before the fix
    def setUp(self):
        super().setUp()
        self.peq = SB / "small.txt"
        self.peq.write_text("x" * 100, "utf-8")
        self.repo = SB / "repo2"
        shutil.rmtree(self.repo, ignore_errors=True)
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / ".claude").mkdir()
        self.arq = self.repo / ".claude" / "sync_relay.json"

    def test_A_semente_sem_curinga_na_primeira_palavra(self):
        for c in relay.PADRAO["read_commands"]:
            if not c.startswith("!"):
                self.assertNotRegex(c.split()[0], r"[*?\[]", c)
        for c in ("rm status", "touch status", "bash status", "python status", "npx status", "./install.sh --version",
                  "FOO=1 status", "/c/tmp/evil.exe --version", "node --version"):
            self.assertTrue(negou(_bash(c)), c)
        self.assertIsNone(_bash("git --version"))

    def test_AE_primeira_palavra_literal_config_e_repo(self):
        for pad in (["[a-z]* *"], ["* *"], ["?* *"], ["*/ *"], ["r* *"], ["[r]m *"]):
            self.assertTrue(negou(_bash("rm -rf /x", {"read_commands": pad})), pad)
            self.arq.write_text(json.dumps({"allowed_commands": pad}), "utf-8")
            self.assertTrue(negou(_bash("rm -rf /x", {"allow_reads": False}, cwd=str(self.repo))), pad)
        self.assertIsNone(_bash("echo hi", {"read_commands": ["echo *"]}))  # a literal first word still works

    def test_AE_padrao_ignorado_avisa(self):
        r = rodar("claude", SS, CLI, {"read_commands": ["git status", "[a-z]* *"]})
        self.assertIn("[a-z]* *", _ss_msg(r))

    def test_B_aspas_e_barra_nao_escondem_vetos(self):
        for c in ("tail '-f' small.txt", 'tail "-f" small.txt', "tail \\-f small.txt", "tail '--follow' small.txt",
                  "git log '--output=/tmp/pwn'", "git diff --stat '--output=/tmp/pwn'", 'git log "-o" x',
                  "cat ~/x", "cat *.txt", "cat small.tx?", "cat small.tx[t]", "ls {a,b}", "ls ~"):
            self.assertTrue(negou(_bash(c)), c)

    def test_C_so_arquivo_regular_pequeno(self):
        (SB / "dir1").mkdir(exist_ok=True)
        for c in ("cat /dev/zero", "head -c 1000000000 /dev/zero", "cat /dev/urandom", "cat nofile.txt", "cat dir1", "cat .",
                  "cat /c/Windows/nothing", "cat -", "head -n 5", "head -c 70000 small.txt", "head -c70000 small.txt",
                  "head --bytes=70000 small.txt", "head -c 1G small.txt", "cat small.txt nofile.txt", "cat"):
            self.assertTrue(negou(_bash(c, cwd=str(SB))), c)
        for c in ("cat small.txt", "head -n 5 small.txt", "head -c 100 small.txt", "tail -n 5 small.txt", "cat " + str(self.peq).replace(chr(92), "/")):  # a backslash path is refused by the structural rule
            self.assertIsNone(_bash(c, cwd=str(SB)), c)
        self.assertTrue(negou(_bash("cat small.txt", cwd=str(SB / "dir1"))))  # resolved from the hook's cwd, not elsewhere

    def test_C_link_para_dispositivo(self):
        ln = SB / "lnzero"
        try:
            if ln.is_symlink() or ln.exists():
                ln.unlink()
            os.symlink("/dev/zero", ln)
        except (OSError, NotImplementedError):
            self.skipTest("no symlink here")
        self.assertTrue(negou(_bash("cat lnzero", cwd=str(SB))))

    def test_D_startup_apaga_o_modo_do_mesmo_pid(self):
        P = {"CLAUDE_PID": "4242"}
        rodar("claude", {**UPS, "prompt": "relay off"}, {**CLI, **P})
        self.assertIsNone(rodar("claude", PRE, {**CLI, **P}))
        rodar("claude", {**SS, "source": "clear"}, {**CLI, **P})  # /clear keeps it
        self.assertIsNone(rodar("claude", PRE, {**CLI, **P}))
        rodar("claude", {**SS, "session_id": "new"}, {**CLI, **P})  # a new process with the same PID
        self.assertTrue(negou(rodar("claude", PRE, {**CLI, **P})))
        with tempfile.TemporaryDirectory() as t:  # Codex: keyed by the session id
            tui = rollout(t, "codex-tui")
            rodar("codex", {**UPS, "transcript_path": tui, "session_id": "cx-1", "prompt": "relay off"})
            rodar("codex", {**SS, "transcript_path": tui, "session_id": "cx-1"})
            self.assertTrue(negou(rodar("codex", {**PRE, "tool_name": "Bash", "transcript_path": tui, "session_id": "cx-1"})))

    def test_E_aviso_no_inicio_da_sessao(self):
        self.arq.write_text(json.dumps({"allowed_commands": ["cargo xtask ci", "make *"]}), "utf-8")
        P = {"CLAUDE_PID": "77"}
        r = rodar("claude", {**SS, "cwd": str(self.repo)}, {**CLI, **P})
        m = _ss_msg(r)
        self.assertIn("sync_relay.json", m)
        self.assertIn("cargo xtask ci", m)
        self.assertIn("make *", m)
        self.assertIsNone(rodar("claude", {**PRE, "tool_name": "Bash", "tool_input": {"command": "cargo xtask ci"}, "cwd": str(self.repo)}, {**CLI, **P}))  # already told
        outro = SB / "repo3"
        shutil.rmtree(outro, ignore_errors=True)
        (outro / ".git").mkdir(parents=True)
        (outro / ".claude").mkdir()
        (outro / ".claude" / "sync_relay.json").write_text(json.dumps({"allowed_commands": ["curl *"]}), "utf-8")
        r2 = rodar("claude", {**PRE, "tool_name": "Bash", "tool_input": {"command": "curl x"}, "cwd": str(outro)}, {**CLI, **P})
        self.assertIn("curl *", _ss_msg(r2))  # cwd moved to another repo with another file: told again
        self.assertNotIn("sync_relay.json", _ss_msg(rodar("claude", {**SS, "cwd": str(SB)}, CLI)))  # no file, no notice
        self.assertNotIn("sync_relay.json", _ss_msg(rodar("claude", {**SS, "cwd": str(self.repo)}, CLI, {"mode": "off"})))
        self.assertNotIn("sync_relay.json", _ss_msg(rodar("claude", {**SS, "cwd": str(self.repo), "agent_id": "a"}, CLI)))

    def test_F_dica_so_para_o_usuario(self):
        r = rodar("claude", PRE, CLI)
        self.assertTrue(negou(r))
        self.assertNotIn("off", json.dumps(r["hookSpecificOutput"]))
        ss = rodar("claude", SS, CLI)
        self.assertIn("/relay off", _ss_msg(ss))
        self.assertNotIn("/relay off", json.dumps(ss.get("hookSpecificOutput")))
        self.assertNotIn("/relay off", _ss_msg(rodar("claude", SS, CLI, {"mode": "off"})))


if __name__ == "__main__":
    unittest.main()

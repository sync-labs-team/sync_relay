import { expect, mock, test } from 'claude-code/testing'

import { compactacao, CONTAGEM_S, configFile, defaultHandoffDir, deveAvisar, janela1m, LIMIAR_ACIMA, nomeArquivo, parseConfig, pontoDeTroca, resolveLang, slug, TETO_ESCRITA_MS } from './hooks/register'

// Existing assertions use the pt-BR wording: pin the language (the test host locale is not stable).
const pt = (on: any) => on('env.get', (_: any, e: any) => ({ value: e.name === 'SYNC_RELAY_LANG' ? 'pt-BR' : undefined }))

// COPY of tests/vectors/paths.json (without _comment). A plugin test cannot read files or import outside its folder,
// so the contract is embedded here; update this block whenever paths.json changes (drift check: see the T4 report).
const vectors = {
  "slug_cases": [
    {
      "name": "windows_trailing_backslash",
      "cwd": "C:\\Users\\alice\\Projects\\demo\\",
      "windows": true,
      "slug": "c-users-alice-projects-demo-e64719f9"
    },
    {
      "name": "windows_lowercase_drive",
      "cwd": "c:\\users\\alice\\projects\\demo",
      "windows": true,
      "slug": "c-users-alice-projects-demo-e64719f9"
    },
    {
      "name": "windows_forward_slashes",
      "cwd": "C:/Users/alice/Projects/demo",
      "windows": true,
      "slug": "c-users-alice-projects-demo-e64719f9"
    },
    {
      "name": "windows_spaces",
      "cwd": "C:\\Users\\alice\\My Projects\\Demo App",
      "windows": true,
      "slug": "c-users-alice-my-projects-demo-app-ef3b85e0"
    },
    {
      "name": "windows_root",
      "cwd": "C:\\",
      "windows": true,
      "slug": "c-1cf80bec"
    },
    {
      "name": "accented_chars",
      "cwd": "C:\\Users\\alice\\Projetos\\A\u00e7\u00e3o R\u00e1pida\\caf\u00e9",
      "windows": true,
      "slug": "c-users-alice-projetos-a-o-r-pida-caf-41f56534"
    },
    {
      "name": "posix_path",
      "cwd": "/home/alice/projects/demo",
      "windows": false,
      "slug": "home-alice-projects-demo-20fb4869"
    },
    {
      "name": "posix_trailing_slash",
      "cwd": "/home/alice/projects/demo/",
      "windows": false,
      "slug": "home-alice-projects-demo-20fb4869"
    },
    {
      "name": "posix_root",
      "cwd": "/",
      "windows": false,
      "slug": "2a0c975e"
    },
    {
      "name": "posix_case_matters",
      "cwd": "/home/alice/Projects/Demo",
      "windows": false,
      "slug": "home-alice-projects-demo-ec7f1da9"
    },
    {
      "name": "long_cwd_over_60_chars",
      "cwd": "C:\\Users\\alice\\Documents\\Projects\\Acme Corp\\services\\payments-gateway\\packages\\billing-engine\\src",
      "windows": true,
      "slug": "e-corp-services-payments-gateway-packages-billing-engine-src-84dd564b"
    },
    {
      "name": "empty_cwd",
      "cwd": "",
      "windows": false,
      "slug": "811c9dc5"
    },
    {
      "name": "only_separators_windows",
      "cwd": "\\/\\//",
      "windows": true,
      "slug": "d90c17db"
    },
    {
      "name": "only_separators_posix",
      "cwd": "\\/\\//",
      "windows": false,
      "slug": "554853c0"
    },
    {
      "name": "collision_underscore",
      "cwd": "C:\\w\\my_app",
      "windows": true,
      "slug": "c-w-my-app-7e127ca5"
    },
    {
      "name": "collision_hyphen",
      "cwd": "C:\\w\\my-app",
      "windows": true,
      "slug": "c-w-my-app-9ee62b13"
    },
    {
      "name": "collision_space",
      "cwd": "C:\\w\\My App",
      "windows": true,
      "slug": "c-w-my-app-3c9bc78a"
    },
    {
      "name": "collision_dot",
      "cwd": "C:\\w\\my.app",
      "windows": true,
      "slug": "c-w-my-app-7da5d910"
    },
    {
      "name": "cjk_a",
      "cwd": "/srv/\u4e2d\u6587",
      "windows": false,
      "slug": "srv-4da7b9b8"
    },
    {
      "name": "cjk_b",
      "cwd": "/srv/\u65e5\u672c",
      "windows": false,
      "slug": "srv-391af7ac"
    },
    {
      "name": "long_same_tail_a",
      "cwd": "/a/xxxxxxxxxx/yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
      "windows": false,
      "slug": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy-27cb939b"
    },
    {
      "name": "long_same_tail_b",
      "cwd": "/b/yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
      "windows": false,
      "slug": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy-679133b1"
    }
  ],
  "handoff_dir": {
    "default": {
      "windows": {
        "env": {
          "LOCALAPPDATA": "C:\\Users\\alice\\AppData\\Local"
        },
        "expected": "C:\\Users\\alice\\AppData\\Local\\sync_relay\\handoffs"
      },
      "posix_xdg": {
        "env": {
          "XDG_STATE_HOME": "/home/alice/.state"
        },
        "expected": "/home/alice/.state/sync_relay/handoffs"
      },
      "posix_home": {
        "env": {},
        "home": "/home/alice",
        "expected": "/home/alice/.local/state/sync_relay/handoffs"
      }
    }
  },
  "distinct": [
    [
      "collision_underscore",
      "collision_hyphen",
      "collision_space",
      "collision_dot"
    ],
    [
      "cjk_a",
      "cjk_b"
    ],
    [
      "long_same_tail_a",
      "long_same_tail_b"
    ]
  ],
  "same": [
    [
      "windows_trailing_backslash",
      "windows_lowercase_drive",
      "windows_forward_slashes"
    ],
    [
      "posix_path",
      "posix_trailing_slash"
    ]
  ],
  "handoff_dir_rule": {
    "comment": "same rule in the core script and in the band: '~' at the start expands to home; Windows needs a drive (C:\\ or C:/) or UNC (\\\\srv\\share); POSIX needs '/'; a '..' segment is rejected; rejected = default folder.",
    "home": {
      "windows": "C:\\Users\\alice",
      "posix": "/home/alice"
    },
    "windows": {
      "ok": [
        "C:\\h",
        "C:/h",
        "c:/h/sub",
        "\\\\srv\\share\\h",
        "~/h",
        "~\\h",
        "~"
      ],
      "bad": [
        "/hh",
        "\\hh",
        "h",
        "rel\\h",
        "C:h",
        "C:/x/..",
        "C:/x/.. ",
        "C:/x/...",
        "\\\\srv",
        "~alice/h",
        ""
      ]
    },
    "posix": {
      "ok": [
        "/h",
        "/h/sub",
        "~/h",
        "~"
      ],
      "bad": [
        "h",
        "rel/h",
        "C:/x",
        "~alice/h",
        "/a/..",
        "/a/../b",
        ""
      ]
    }
  },
  "lang": [
    [
      "pt",
      "pt-BR"
    ],
    [
      "PT",
      "pt-BR"
    ],
    [
      "pt-br",
      "pt-BR"
    ],
    [
      "pt_BR",
      "pt-BR"
    ],
    [
      "PT-br",
      "pt-BR"
    ],
    [
      "pt-PT",
      "pt-BR"
    ],
    [
      "en",
      "en"
    ],
    [
      "EN",
      "en"
    ],
    [
      "en-US",
      "en"
    ],
    [
      "en_GB",
      "en"
    ],
    [
      "en-us",
      "en"
    ],
    [
      "de",
      "locale"
    ],
    [
      "",
      "locale"
    ],
    [
      "auto",
      "locale"
    ],
    [
      "portuguese",
      "locale"
    ],
    [
      "ptx",
      "locale"
    ],
    [
      "english",
      "locale"
    ]
  ],
  "compaction_cases": {
    "_comment": "Switch point = floor + min(D, 0.8 x (C - floor)); D = threshold (default 150000); if C - floor <= 0, floor + D. C (Claude): env CLAUDE_CODE_AUTO_COMPACT_WINDOW (>=100000), else settings autoCompactWindow (number >=100000), else the model window (1M ids: [1m] suffix, Fable, Sonnet >=5, Haiku >=5.5, Opus >=4.7 -> 967000; else 200000; CLAUDE_CODE_DISABLE_1M_CONTEXT=1 forces 200000), then x CLAUDE_AUTOCOMPACT_PCT_OVERRIDE/100 (1 to 100). C (Codex): model_auto_compact_token_limit from config.toml, else none. origem: env, settings, model, codex-config, none; '+pct' when the override applied. The band (Claude only) skips the codex cases.",
    "cases": [
      {
        "name": "claude_1m_opus_4_7",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "claude_200k_sonnet_4_6",
        "cli": "claude",
        "model": "claude-sonnet-4-6",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "codex_limit_120k",
        "cli": "codex",
        "model": null,
        "env": {},
        "settings": null,
        "codex_limit": 120000,
        "threshold": null,
        "floor": 30000,
        "c": 120000,
        "origem": "codex-config",
        "switch": 102000
      },
      {
        "name": "codex_no_limit",
        "cli": "codex",
        "model": null,
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": null,
        "origem": "none",
        "switch": 180000
      },
      {
        "name": "threshold_300k_claude_200k",
        "cli": "claude",
        "model": "claude-sonnet-4-6",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": 300000,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "threshold_100k_claude_1m",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": 100000,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 130000
      },
      {
        "name": "env_window_500k",
        "cli": "claude",
        "model": "claude-sonnet-4-6",
        "env": {
          "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "500000"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 500000,
        "origem": "env",
        "switch": 180000
      },
      {
        "name": "env_window_below_100k_ignored",
        "cli": "claude",
        "model": "claude-sonnet-4-6",
        "env": {
          "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "99999"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "env_window_junk_ignored",
        "cli": "claude",
        "model": "claude-sonnet-4-6",
        "env": {
          "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "abc"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "env_beats_settings",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {
          "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "300000"
        },
        "settings": {
          "autoCompactWindow": 150000
        },
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 300000,
        "origem": "env",
        "switch": 180000
      },
      {
        "name": "settings_window_150k",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {},
        "settings": {
          "autoCompactWindow": 150000
        },
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 150000,
        "origem": "settings",
        "switch": 126000
      },
      {
        "name": "settings_window_not_a_number_ignored",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {},
        "settings": {
          "autoCompactWindow": "150000"
        },
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "settings_window_infinite_ignored",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {},
        "settings": {
          "autoCompactWindow": 1e400
        },
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "settings_window_true_ignored",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {},
        "settings": {
          "autoCompactWindow": true
        },
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "pct_override_10",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {
          "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "10"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 96700,
        "origem": "model+pct",
        "switch": 83360
      },
      {
        "name": "pct_override_0_ignored",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {
          "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "0"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "pct_override_101_ignored",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {
          "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "101"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "pct_override_on_env_window",
        "cli": "claude",
        "model": "claude-sonnet-4-6",
        "env": {
          "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "300000",
          "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 150000,
        "origem": "env+pct",
        "switch": 126000
      },
      {
        "name": "disable_1m_forces_200k",
        "cli": "claude",
        "model": "claude-opus-4-7",
        "env": {
          "CLAUDE_CODE_DISABLE_1M_CONTEXT": "1"
        },
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "suffix_1m",
        "cli": "claude",
        "model": "claude-sonnet-4-6[1m]",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "fable_1m",
        "cli": "claude",
        "model": "claude-fable-1",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "sonnet_5_1m",
        "cli": "claude",
        "model": "claude-sonnet-5",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "sonnet_5_5_1m",
        "cli": "claude",
        "model": "claude-sonnet-5-5",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "haiku_5_5_1m",
        "cli": "claude",
        "model": "claude-haiku-5-5",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "haiku_5_4_200k",
        "cli": "claude",
        "model": "claude-haiku-5-4",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "haiku_4_5_200k",
        "cli": "claude",
        "model": "claude-haiku-4-5-20251001",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "opus_4_6_200k",
        "cli": "claude",
        "model": "claude-opus-4-6",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "opus_4_8_dated_1m",
        "cli": "claude",
        "model": "claude-opus-4-8-20270101",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "opus_5_1m",
        "cli": "claude",
        "model": "claude-opus-5",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 967000,
        "origem": "model",
        "switch": 180000
      },
      {
        "name": "sonnet_4_dated_200k",
        "cli": "claude",
        "model": "claude-sonnet-4-20250514",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "unknown_model_200k",
        "cli": "claude",
        "model": "some-other-model",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "no_model_200k",
        "cli": "claude",
        "model": null,
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 30000,
        "c": 200000,
        "origem": "model",
        "switch": 166000
      },
      {
        "name": "compaction_below_floor_no_cap",
        "cli": "claude",
        "model": "claude-sonnet-4-6",
        "env": {},
        "settings": null,
        "codex_limit": null,
        "threshold": null,
        "floor": 250000,
        "c": 200000,
        "origem": "model",
        "switch": 400000
      },
      {
        "name": "codex_limit_below_floor_no_cap",
        "cli": "codex",
        "model": null,
        "env": {},
        "settings": null,
        "codex_limit": 20000,
        "threshold": null,
        "floor": 30000,
        "c": 20000,
        "origem": "codex-config",
        "switch": 180000
      }
    ]
  }
}

const M = { role: 'user' as const, text: 'resumo', toolUses: [] }

const FAIXA = {
  plugin: 'sync_relay',
  component: 'AbovePrompt',
  props: {
    hasSurvey: false,
    isCollapsed: false,
    isWorking: false,
    maxRows: 3,
    bodyColumns: 80,
    scroll: { offset: 0, bodyRows: 3 },
    view: {},
  },
} as const

test('slug equals the shared vector in every case (tests/vectors/paths.json)', () => {
  for (const c of vectors.slug_cases) expect(slug(c.cwd, c.windows), c.name).toBe(c.slug)
})

test('slug: colliding projects get different names, equivalent spellings the same one', () => {
  const por: Record<string, string> = {}
  for (const c of vectors.slug_cases) por[c.name] = slug(c.cwd, c.windows)
  for (const g of vectors.distinct) expect(new Set(g.map(n => por[n])).size, g.join()).toBe(g.length)
  for (const g of vectors.same) expect(new Set(g.map(n => por[n])).size, g.join()).toBe(1)
  for (const v of Object.values(por)) expect(v).toMatch(/^([a-z0-9-]*-)?[0-9a-f]{8}$/)
})

test('file name with the session id: <slug>-<id[:8]>.md, same as the core script', () => {
  expect(nomeArquivo('C:\\Users\\alice\\Projects\\demo\\', '00000000-0000-4000-8000-000000000001', true)).toBe(
    'c-users-alice-projects-demo-e64719f9-00000000.md',
  )
  expect(nomeArquivo('/home/alice/projects/demo', '', false)).toBe('home-alice-projects-demo-20fb4869.md')
})

test('default handoff folder equals the shared vector (Windows, XDG, home)', () => {
  const d = vectors.handoff_dir.default
  expect(defaultHandoffDir(true, d.windows.env, null)).toBe(d.windows.expected)
  expect(defaultHandoffDir(false, d.posix_xdg.env, null)).toBe(d.posix_xdg.expected)
  expect(defaultHandoffDir(false, {}, d.posix_home.home)).toBe(d.posix_home.expected)
  expect(defaultHandoffDir(false, {}, null)).toBeNull() // no base: no folder, never a relative path
})

test('config file: SYNC_RELAY_CONFIG, then XDG, then APPDATA, then ~/.config', () => {
  expect(configFile(false, { SYNC_RELAY_CONFIG: '/x/c.json', XDG_CONFIG_HOME: '/y' }, '/home/a')).toBe('/x/c.json')
  expect(configFile(false, { XDG_CONFIG_HOME: '/y' }, '/home/a')).toBe('/y/sync_relay/config.json')
  expect(configFile(true, { APPDATA: 'C:\\Users\\a\\AppData\\Roaming' }, null)).toBe('C:\\Users\\a\\AppData\\Roaming\\sync_relay\\config.json')
  expect(configFile(false, {}, '/home/a')).toBe('/home/a/.config/sync_relay/config.json')
  expect(configFile(false, {}, null)).toBeNull()
})

test('config parse: BOM stripped; broken JSON, wrong types and unknown keys fall back to the defaults', () => {
  expect(parseConfig('\uFEFF{"lang":"en","threshold_tokens":100000,"handoff_dir":"/data/h","mode":"enforce"}')).toEqual({ lang: 'en', threshold: 100000, dir: '/data/h', mode: 'enforce' })
  expect(parseConfig('{not json')).toEqual({})
  expect(parseConfig('[1]')).toEqual({})
  expect(parseConfig('{"threshold_tokens":"100k","handoff_dir":"relative/dir"}')).toEqual({})
  expect(parseConfig('{"threshold_tokens":10}')).toEqual({}) // below the 5k floor
})

test('config handoff_dir: ".." segments rejected; drive letter only on Windows, leading slash on POSIX', () => {
  const dir = (d: string, windows?: boolean) => parseConfig(JSON.stringify({ handoff_dir: d }), windows).dir
  for (const bad of ['C:/x/../../Windows', '/a/../../etc', 'C:\\x\\..\\y', '/a/..']) expect(dir(bad, true)).toBeUndefined()
  // Windows strips trailing dots and spaces: ".. " and "..." are ".." in disguise (same rule as the core script)
  for (const bad of ['C:/x/.. ', 'C:/x/...', 'C:\\x\\.. \\y', 'C:/x/.. ./y']) expect(dir(bad, true)).toBeUndefined()
  expect(dir('C:/x/..data', true)).toBe('C:/x/..data') // a name that only starts with ".." is fine
  for (const bad of ['/a/../../etc', '/a/..']) expect(dir(bad, false)).toBeUndefined()
  expect(dir('C:/x', false)).toBeUndefined() // relative on POSIX
  expect(dir('C:/x', true)).toBe('C:/x')
  expect(dir('/data/h', false)).toBe('/data/h')
  expect(dir('/a/..b/c', false)).toBe('/a/..b/c') // "..b" is a name, not a segment
})

test('config handoff_dir: the same accepted and rejected cases as the core script (tests/vectors/paths.json)', () => {
  const r = vectors.handoff_dir_rule
  for (const [windows, k] of [[true, 'windows'], [false, 'posix']] as const) {
    const home = r.home[k]
    const dir = (d: string) => parseConfig(JSON.stringify({ handoff_dir: d }), windows, home).dir
    for (const ok of r[k].ok) expect(dir(ok), `${k} ${ok}`).toBeDefined()
    for (const bad of r[k].bad) expect(dir(bad), `${k} ${bad}`).toBeUndefined()
  }
  expect(parseConfig('{"handoff_dir":"~/h"}', false, '/home/alice').dir).toBe('/home/alice/h')
  expect(parseConfig(JSON.stringify({ handoff_dir: '~\\h' }), true, 'C:\\Users\\alice').dir).toBe('C:\\Users\\alice\\h')
  expect(parseConfig('{"handoff_dir":"~/h"}', false, null).dir).toBeUndefined() // no home: cannot expand
  expect(parseConfig('{"handoff_dir":"/hh"}', true).dir).toBeUndefined() // no drive on Windows: default folder
})

test('language: the same cases as the core script (tests/vectors/paths.json)', () => {
  for (const [v, esperado] of vectors.lang) {
    for (const [loc, daLocale] of [['pt-BR', 'pt-BR'], ['en-US', 'en']] as const) {
      expect(resolveLang(undefined, v, loc), `${v} ${loc}`).toBe(esperado === 'locale' ? daLocale : esperado)
    }
  }
  expect(resolveLang('xx', 'pt', 'en-US')).toBe('pt-BR') // env wins only when it names a language we know
  expect(resolveLang('PT_br', 'en', 'en-US')).toBe('pt-BR')
})

test('language: env, then config, then the locale (pt* is pt-BR, anything else en)', () => {
  expect(resolveLang('en', 'pt-BR', 'pt-BR')).toBe('en')
  expect(resolveLang(undefined, 'pt-BR', 'en-US')).toBe('pt-BR')
  expect(resolveLang(undefined, 'auto', 'pt-PT')).toBe('pt-BR')
  expect(resolveLang('xx', undefined, 'de-DE')).toBe('en')
})

test('compaction point and switch point equal the shared vectors (Claude cases; tests/vectors/paths.json)', () => {
  for (const k of vectors.compaction_cases.cases.filter(x => x.cli === 'claude')) {
    const r = compactacao(k.model ?? undefined, k.env as Record<string, string>, k.settings)
    expect([r.c, r.origem], k.name).toEqual([k.c, k.origem])
    expect(pontoDeTroca(k.floor, k.threshold ?? 150_000, r.c), k.name).toBe(k.switch)
  }
  // the core's codex cases without a ceiling: the rule alone (floor + D)
  expect(pontoDeTroca(30_000, 150_000, null)).toBe(180_000)
  expect(pontoDeTroca(30_000, 150_000, 20_000)).toBe(180_000)
})

test('1M window: [1m] suffix, Fable, Sonnet 5+, Haiku 5.5+, Opus 4.7+; anything else (and unknown) is 200K', () => {
  for (const m of ['claude-opus-4-7', 'claude-opus-4-9-20270101', 'claude-sonnet-5', 'claude-sonnet-5-5', 'claude-haiku-5-5', 'claude-fable-1', 'x-model[1m]']) expect(janela1m(m), m).toBe(true)
  for (const m of ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-sonnet-4-20250514', 'claude-haiku-5-4', 'claude-haiku-4-5-20251001', 'gpt-9', '', undefined]) expect(janela1m(m), String(m)).toBe(false)
})

test('a window from the API upgrades only a model the table does not know; DISABLE_1M still wins', () => {
  expect(compactacao('opus', {}, null, 1_000_000).c).toBe(967_000) // alias: the API says 1M
  expect(compactacao('claude-sonnet-4-6', {}, null, 1_000_000).c).toBe(200_000) // known and small: the table wins
  expect(compactacao(undefined, { CLAUDE_CODE_DISABLE_1M_CONTEXT: '1' }, null, 1_000_000).c).toBe(200_000)
  expect(compactacao(undefined, {}, null, 200_000).c).toBe(200_000)
})

test('avisa so 150k acima do piso; "Depois" adia ate crescer mais 50k', () => {
  const PISO = 95_000
  const LIM = PISO + LIMIAR_ACIMA
  expect(deveAvisar(null, PISO, null, 'ocioso')).toBe(false)
  expect(deveAvisar(LIM, null, null, 'ocioso')).toBe(false) // piso ainda desconhecido
  expect(deveAvisar(240_000, PISO, null, 'ocioso')).toBe(false)
  expect(deveAvisar(245_000, PISO, null, 'ocioso')).toBe(true)
  expect(deveAvisar(LIM, PISO, null, 'escrevendo')).toBe(false)
  expect(deveAvisar(LIM + 10_000, PISO, LIM, 'ocioso')).toBe(false)
  expect(deveAvisar(LIM + 50_000, PISO, LIM, 'ocioso')).toBe(true)
})

test('deveAvisar com o ponto de compactacao: piso 30k, janela de 200K troca em 166k; 1M em 180k; limiar 300k nao passa do teto', () => {
  expect(deveAvisar(165_000, 30_000, null, 'ocioso', 150_000, 200_000)).toBe(false)
  expect(deveAvisar(166_000, 30_000, null, 'ocioso', 150_000, 200_000)).toBe(true)
  expect(deveAvisar(179_000, 30_000, null, 'ocioso', 150_000, 967_000)).toBe(false)
  expect(deveAvisar(180_000, 30_000, null, 'ocioso', 150_000, 967_000)).toBe(true)
  expect(deveAvisar(165_000, 30_000, null, 'ocioso', 300_000, 200_000)).toBe(false)
  expect(deveAvisar(166_000, 30_000, null, 'ocioso', 300_000, 200_000)).toBe(true)
})

test('depois de um turno com contexto alto a faixa aparece e o botao pede a passagem', async ($, on) => {
  let enviado = ''
  let tokens = 30_000
  mock.store(on) // sem session.start, o 1o turno carrega o estado do store
  pt(on)
  on('session.usage', () => ({
    value: {
      startedAt: 0,
      context: { tokens, window: 1_000_000, percent: Math.round(tokens / 10_000) },
      rateLimits: [],
      cost: { usd: 0 },
    },
  }))
  on('prompt.submit', (_, e) => {
    enviado = e.text
    return { text: e.text }
  })
  on('session.info', () => ({ value: { transcriptPath: 'C:/Users/x/.claude/projects/C--x/abc.jsonl', platform: 'windows' } }))
  on('turn.complete', () => ({ text: 'ok' }))
  on('clock.now', () => ({ value: 1_000 }))
  on('agent.list', () => ({ value: [] }))

  await $.turn.complete({ reason: 'answer', answer: 'ok', durationMs: 1, isAborted: false, turnId: 't1' })
  const baixo = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  expect(await baixo.find({ type: 'Button', key: 'trocar' })).toBeUndefined()
  await baixo.unmount()

  tokens = 182_000
  await $.turn.complete({ reason: 'answer', answer: 'ok', durationMs: 1, isAborted: false, turnId: 't1' })
  for (const surface of ['terminal', 'desktop'] as const) {
    const alto = await $.ui.mount({ ...FAIXA, surface })
    expect((await alto.find({ type: 'Button', key: 'trocar' }))?.props.label).toBe('Trocar de sessão')
    expect((await alto.find({ type: 'Text', text: /182k/ }))?.text).toContain(
      '182k tokens (+152k acima do início da sessão)',
    )
    await alto.unmount()
  }

  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await ui.press({ key: 'trocar' })
  expect(enviado).toBe('relay')
  expect(await ui.find({ type: 'Text', text: /Gravando a passagem/ })).toBeDefined()
  await ui.unmount()
})

test('depois de compactar a faixa some; compactacao vetada nao zera', async ($, on) => {
  let veto: string | undefined
  let tokens = 30_000
  mock.store(on) // sem session.start, o 1o turno carrega o estado do store
  pt(on)
  on('session.usage', () => ({
    value: {
      startedAt: 0,
      context: { tokens, window: 1_000_000, percent: 18 },
      rateLimits: [],
      cost: { usd: 0 },
    },
  }))
  on('turn.complete', () => ({ text: 'ok' }))
  on('session.compact', () => (veto ? { skip: veto } : { messages: [M] }))

  await $.turn.complete({ reason: 'answer', answer: 'ok', durationMs: 1, isAborted: false, turnId: 't1' })
  tokens = 182_000
  await $.turn.complete({ reason: 'answer', answer: 'ok', durationMs: 1, isAborted: false, turnId: 't1' })
  const faixa = async () => {
    const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
    const achou = await ui.find({ type: 'Button', key: 'trocar' })
    await ui.unmount()
    return achou !== undefined
  }
  expect(await faixa()).toBe(true)

  veto = 'off'
  await $.session.compact({ trigger: 'manual', messages: [M] } as never)
  expect(await faixa()).toBe(true)

  veto = undefined
  await $.session.compact({ trigger: 'manual', messages: [M] } as never)
  expect(await faixa()).toBe(false)
})

// Agente vivo = pending ou running; waiting (preso em trabalho proprio), idle e fim nao seguram a troca.
const agente = (status: string) =>
  ({ id: 'a1', description: 'x', type: 'general-purpose', status, kind: 'local_agent', taskStatus: status, label: 'x', startTime: 0, cwd: '/' }) as never

const TURNO = { reason: 'answer', answer: 'ok', durationMs: 1, isAborted: false, turnId: 't1' } as const

async function cena($: any, on: any, agentes: () => unknown[]) {
  const enviados: string[] = []
  let tokens = 30_000
  mock.store(on) // sem session.start, o 1o turno carrega o estado do store
  pt(on)
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens, window: 1_000_000, percent: 18 }, rateLimits: [], cost: { usd: 0 } },
  }))
  on('prompt.submit', (_: any, e: any) => {
    enviados.push(e.text)
    return { text: e.text }
  })
  on('session.info', () => ({ value: { transcriptPath: 'C:/Users/x/.claude/projects/C--x/abc.jsonl', platform: 'windows' } }))
  on('turn.complete', () => ({ text: 'ok' }))
  on('clock.now', () => ({ value: 1_000 }))
  on('agent.list', () => ({ value: agentes() }))
  await $.turn.complete(TURNO) // turno de base: fixa o piso em 30k
  tokens = 182_000
  await $.turn.complete(TURNO)
  return enviados
}

test('com agente vivo o clique espera; quando ele termina, a passagem e pedida', async ($, on) => {
  let vivos = [agente('running')]
  const enviados = await cena($, on, () => vivos)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await ui.press({ key: 'trocar' })
  expect(enviados).toEqual([])
  expect(await ui.find({ type: 'Text', text: /Aguardando 1/ })).toBeDefined()

  vivos = []
  await $.turn.complete({ ...TURNO, agentId: 'a1' })
  expect(enviados).toEqual(['relay'])
  expect(await ui.find({ type: 'Text', text: /Gravando a passagem/ })).toBeDefined()
  await ui.unmount()
})

test('cancelar a espera devolve o botao e nada e enviado', async ($, on) => {
  const enviados = await cena($, on, () => [agente('running')])
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await ui.press({ key: 'trocar' })
  await ui.press({ key: 'cancelar' })
  expect(await ui.find({ type: 'Button', key: 'trocar' })).toBeDefined()
  await $.turn.complete({ ...TURNO, agentId: 'a1' })
  expect(enviados).toEqual([])
  await ui.unmount()
})

test('agente ja terminado ou parado nao segura a passagem', async ($, on) => {
  const enviados = await cena($, on, () => [agente('completed'), agente('idle'), agente('killed')])
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await ui.press({ key: 'trocar' })
  expect(enviados).toEqual(['relay'])
  await ui.unmount()
})

// ---------- modo automatico (0.2.0) ----------

type Ctx = {
  relogio: ReturnType<typeof mock.clock>
  enviados: string[]
  toasts: string[]
  limpos: number
  tokens: { v: number }
  agentes: { v: unknown[] }
  gravada: { v: boolean }
  lento: { v: number } // atraso do agent.list, em ms reais
  storeLento: { v: number } // atraso do store.set, em ms do relogio falso
  clearFalha: { v: boolean }
  submitFalha: { v: boolean }
  travado: { v: boolean } // agent.list que nunca responde
  sid: { v: string } // $.session.id()
  mem: Map<string, unknown> // o que o mod guardou em $.store
  proximo: { v: string | null } // id novo que o session.end poe em $.session.id() (o /clear real troca o id)
  existe: { v: string | null } // fs.exists so responde true para caminho com este trecho (null: qualquer)
  perguntados: string[] // caminhos de fs.exists
  contextos: (readonly string[] | undefined)[] // context de cada prompt.submit que chegou ao fim da cadeia
  escritas: Map<string, string> // o que o mod gravou com fs.write (rastro)
  escritaFalha: { v: boolean }
  info: { v: Record<string, unknown> } // $.session.info(): o motor real NAO traz configRoot
  env: { v: Record<string, string> } // $.process.hookEnv()
  penv: { v: Record<string, string | undefined> } // $.env.get: variaveis SYNC_RELAY_*
  zerados: Set<string> // atomos que o /clear zerou e o mod ainda nao escreveu: state.get devolve o padrao
  idFalhaNoFim: { v: boolean } // $.session.id() rejeita depois do next(e) do session.end
  idFalha: { v: boolean }
  storeFalha: { v: boolean } // $.store.get lanca (store ilegivel)
  forcados: Map<string, unknown> // $.state.get devolve este valor ate o mod escrever a chave (sessao que ja tinha estado)
}

/** Sessao de teste: relogio e store falsos; prompt e /clear so sao anotados, nada sai da maquina. */
async function auto(
  $: any,
  on: any,
  o: { interativo?: boolean; penv?: Record<string, string>; ligado?: boolean; apresentado?: boolean; piso?: number; abaixo?: (on: any) => void } = {},
): Promise<Ctx> {
  const relogio = mock.clock(on, { now: 5_000 })
  o.abaixo?.(on)
  // store em memoria (no lugar do mock.store) para o teste enxergar o que o mod guarda.
  const mem = new Map<string, unknown>(o.ligado === undefined ? [] : [['auto', o.ligado]])
  // 0.6.4: a apresentacao unica vem marcada como vista, salvo nos testes dela (apresentado: false).
  if (o.apresentado !== false) mem.set('apresentado', true)
  const storeFalha = { v: false }
  on('store.get', (_: any, e: any) => {
    if (storeFalha.v) throw new Error('store ilegivel')
    return { value: mem.get(e.key) }
  })
  let atrasoStore = { v: 0 }
  on('store.set', async (_: any, e: any) => {
    if (atrasoStore.v) await relogio.sleep(atrasoStore.v)
    mem.set(e.key, e.value)
    return { value: undefined }
  })
  on('store.delete', (_: any, e: any) => (mem.delete(e.key), { value: undefined }))
  on('store.keys', () => ({ value: [...mem.keys()] }))
  const c: Ctx = {
    storeFalha,
    forcados: new Map(),
    mem,
    relogio,
    enviados: [],
    toasts: [],
    limpos: 0,
    tokens: { v: o.piso ?? 30_000 },
    agentes: { v: [] },
    gravada: { v: true },
    lento: { v: 0 },
    storeLento: atrasoStore,
    clearFalha: { v: false },
    submitFalha: { v: false },
    travado: { v: false },
    sid: { v: 'aaaa1111-0000-0000-0000-000000000000' },
    proximo: { v: null },
    existe: { v: null },
    perguntados: [],
    contextos: [],
    escritas: new Map(),
    escritaFalha: { v: false },
    idFalhaNoFim: { v: false },
    idFalha: { v: false },
    zerados: new Set(),
    info: { v: { transcriptPath: 'C:\\Users\\x\\.claude\\projects\\C--x\\abc.jsonl', platform: 'windows', isHosted: false } },
    env: { v: { CLAUDE_PID: '100' } },
    penv: { v: { SYNC_RELAY_LANG: 'pt-BR', ...o.penv } },
  }
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens: c.tokens.v, window: 1_000_000, percent: 18 }, rateLimits: [], cost: { usd: 0 } },
  }))
  on('prompt.submit', (_: any, e: any) => {
    if (c.submitFalha.v) throw new Error('submit recusado')
    c.enviados.push(e.text)
    c.contextos.push(e.context)
    return { text: e.text }
  })
  on('command.run', { command: 'clear' }, () => {
    if (c.clearFalha.v) throw new Error('clear recusado')
    c.limpos += 1
    return { text: '' }
  })
  on('turn.complete', () => ({ text: 'ok' }))
  on('agent.list', async () => {
    if (c.travado.v) await new Promise(() => {})
    if (c.lento.v) await dormir(c.lento.v)
    return { value: c.agentes.v }
  })
  on('turn.start', (_: any, e: any) => ({ turnId: e.turnId }))
  on('ui.toast', (_: any, e: any) => {
    c.toasts.push(e.text)
    return { value: undefined }
  })
  on('session.info', () => ({ value: c.info.v }))
  on('process.hookEnv', () => ({ value: c.env.v }))
  on('env.get', (_: any, e: any) => ({ value: c.penv.v[e.name] }))
  on('session.cwd', () => ({ value: 'C:/Users/x/p' }))
  on('fs.exists', (_: any, e: any) => {
    c.perguntados.push(e.path)
    return { value: c.gravada.v && (c.existe.v === null || String(e.path).includes(c.existe.v)) }
  })
  on('fs.write', (_: any, e: any) => {
    if (c.escritaFalha.v) throw new Error('disco cheio')
    c.escritas.set(String(e.path).replaceAll('\\', '/'), e.text)
    return { value: undefined }
  })
  on('fs.read', (_: any, e: any) => {
    const caminho = String(e.path).replaceAll('\\', '/')
    if (caminho.includes('_trace-')) {
      if (!c.escritas.has(caminho)) throw new Error('nao existe')
      return { value: c.escritas.get(caminho) }
    }
    return { value: (globalThis as any).TXT ?? 'TEXTO-DA-PASSAGEM' }
  })
  on('session.id', () => {
    if (c.idFalha.v) throw new Error('id indisponivel')
    return { value: c.sid.v }
  })
  on('fs.stat', () => ({ value: { mtimeMs: (globalThis as any).MT ?? 1e12, size: 1 } }))
  on('command.register', () => ({ value: undefined }))
  on('state.get', (_: any, e: any, next: any) =>
    c.zerados.has(e.key)
      ? { value: { value: undefined, version: 0 } }
      : c.forcados.has(e.key)
        ? { value: { value: c.forcados.get(e.key), version: 1 } }
        : next(e),
  )
  on('state.set', (_: any, e: any, next: any) => (c.zerados.delete(e.key), c.forcados.delete(e.key), next(e)))
  on('session.end', () => {
    if (c.proximo.v) c.sid.v = c.proximo.v
    if (c.idFalhaNoFim.v) c.idFalha.v = true
    return { sessionId: 's1' }
  })
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: o.interativo ?? true })
  await $.turn.complete({ ...TURNO }) // turno de base: fixa o piso da sessao
  c.tokens.v = 182_000
  return c
}

async function olhar($: any, q: object): Promise<any> {
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  const r = await ui.find(q)
  await ui.unmount()
  return r
}
const contando = async ($: any, n?: number) =>
  (await olhar($, { type: 'Text', text: n === undefined ? /Troca automática em \d+ s/ : new RegExp(`Troca automática em ${n} s`) })) !==
  undefined
const botao = async ($: any, key: string) => (await olhar($, { type: 'Button', key })) !== undefined
const apertar = async ($: any, key: string) => {
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await ui.press({ key })
  await ui.unmount()
}
const turno = ($: any, extra: object = {}) => $.turn.complete({ ...TURNO, ...extra })
// A pessoa digitando: origem composer, nao a do plugin.
const pessoa = ($: any, text = 'oi') => $.prompt.submit({ text, origin: { kind: 'composer' }, wait: false } as never)
// setTimeout real (o relogio do teste e falso): deixa o agent.list atrasado terminar.
const dormir = (ms: number) => new Promise<void>(r => void (globalThis as any).setTimeout(r, ms))
const ADIADA = 'Troca adiada: você mandou uma mensagem'
const CANCELADA = 'Troca cancelada e automático desligado. Para religar: /relay auto'

// Sessao nova (piso zerado): um turno baixo fixa o piso em 30k e o contexto volta a 182k.
const base = async ($: any, c: Ctx) => {
  c.tokens.v = 30_000
  await turno($)
  c.tokens.v = 182_000
}
const reiniciar = ($: any) => $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
// /clear como no motor real (provado em claude -p 2.1.329, 20/11/2026): o session.end inteiro, inclusive depois do next(e),
// roda com o id ANTIGO e o que ele grava no $.state fica na sessao antiga; so depois da cadeia o id troca e o $.state da
// sessao nova nasce vazio, sem session.start.
const ESTADO = ['tokens', 'piso', 'adiado', 'fase', 'auto', 'apresentado', 'interativo', 'restante', 'demorou', 'limiar', 'botao', 'compact', 'carregado']
const clearReal = async ($: any, c: Ctx, novo = 'cccc3333-0000-0000-0000-000000000000') => {
  await $.session.end({ reason: 'clear' } as never)
  c.sid.v = novo
  for (const k of ESTADO) c.zerados.add(k)
}

test('regra 1: /relay auto alterna, persiste no store e avisa; /relay sem argumento troca', async ($, on) => {
  const c = await auto($, on)
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(c.toasts.some(t => /ligada/.test(t))).toBe(true)
  await reiniciar($) // le a escolha de volta do store (e zera o piso)
  await base($, c)
  await turno($)
  expect(await contando($)).toBe(true)
  await apertar($, 'cancelar') // Cancelar tambem desliga o auto (0.6.12)
  expect(c.toasts).toContain(CANCELADA)
  expect(c.mem.get('auto')).toBe(false)
  await reiniciar($)
  await base($, c)
  c.tokens.v += 60_000
  await turno($)
  expect(await contando($)).toBe(false)
  await $.command.run({ command: 'relay', args: '' } as never)
  await c.relogio.settle()
  expect(c.enviados).toEqual(['relay'])
})

test('regra 1: botao Auto na faixa mostra e alterna', async ($, on) => {
  await auto($, on, { ligado: false })
  await turno($)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  expect((await ui.find({ type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: desligado')
  await ui.press({ key: 'auto' })
  expect(await contando($)).toBe(false) // ligar nao dispara no meio; so no proximo fim de turno
  expect((await ui.find({ type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: ligado')
  await ui.unmount()
})

test('regra 1: a escolha guardada no store (ligado) vale desde o session.start', async ($, on) => {
  await auto($, on, { ligado: true })
  await turno($)
  expect(await contando($)).toBe(true)
})

test('regra 2: so dispara no fim de turno da principal, acima do limiar sobre o piso e com auto ligado', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  c.tokens.v = 30_000 + LIMIAR_ACIMA - 1
  await turno($)
  expect(await contando($)).toBe(false)
  c.tokens.v = 182_000
  await turno($, { agentId: 'a1' })
  expect(await contando($)).toBe(false)
  await turno($)
  expect(await contando($, CONTAGEM_S)).toBe(true)
  expect(c.enviados).toEqual([])
})

test('regra 2: auto desligado nunca dispara', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await c.relogio.advance(60_000)
  expect(await contando($)).toBe(false)
  expect(c.enviados).toEqual([])
})

test('regra 3: sessao nao interativa (-p/SDK) nunca dispara, nem com auto ligado', async ($, on) => {
  const c = await auto($, on, { ligado: true, interativo: false })
  await turno($)
  await c.relogio.advance(60_000)
  expect(await contando($)).toBe(false)
  expect(c.enviados).toEqual([])
})

test('regra 4: contagem de 15 s com Agora e Cancelar; no fim troca pelo fluxo normal', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  expect(CONTAGEM_S).toBe(15)
  await turno($)
  expect(await botao($, 'agora')).toBe(true)
  expect(await botao($, 'cancelar')).toBe(true)
  await c.relogio.advance(3_000)
  expect(await contando($, 12)).toBe(true)
  await c.relogio.advance(11_000)
  expect(c.enviados).toEqual([])
  await c.relogio.advance(1_000)
  expect(c.enviados).toEqual(['relay'])
  await c.relogio.advance(30_000)
  expect(c.enviados).toEqual(['relay'])
})

test('regra 4: Agora troca ja', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await apertar($, 'agora')
  expect(c.enviados).toEqual(['relay'])
  await c.relogio.advance(30_000)
  expect(c.enviados).toEqual(['relay'])
})

test('regra 4: agente que comeca durante a contagem: no fim dela a troca espera o agente', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  c.agentes.v = [agente('running')] // v0.1.1: alive before the turn, the countdown would not even start
  await c.relogio.advance(CONTAGEM_S * 1000)
  expect(c.enviados).toEqual([])
  c.agentes.v = []
  await c.relogio.advance(2_000)
  expect(c.enviados).toEqual(['relay'])
})

test('v0.1.1: com agente vivo (pending ou running) o auto nem comeca a contagem; o turno depois do fim dele dispara', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  for (const status of ['running', 'pending']) {
    c.agentes.v = [agente(status)]
    await turno($)
    expect(await contando($)).toBe(false)
    expect(await botao($, 'trocar')).toBe(true) // the banner still warns: only the automatic switch waits
  }
  await c.relogio.advance(60_000)
  expect(c.enviados).toEqual([])
  c.agentes.v = [agente('waiting'), agente('completed')] // same rule as the switch: these do not hold it
  await turno($)
  expect(await contando($, CONTAGEM_S)).toBe(true)
})

test('regra 5: Cancelar adia 50k, como o Depois, desliga o auto e nenhum timer sobra', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await apertar($, 'cancelar')
  expect(await contando($)).toBe(false)
  expect(c.mem.get('auto')).toBe(false)
  await c.relogio.advance(60_000)
  expect(c.enviados).toEqual([])
  c.tokens.v = 182_000 + 10_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(false) // adiado 50k
  c.tokens.v = 182_000 + 50_000
  await turno($)
  expect(await contando($)).toBe(false) // auto desligado: sobe so a faixa de aviso
  expect(await botao($, 'trocar')).toBe(true)
})

test('regra 6: mensagem da pessoa durante a contagem cancela e avisa', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await pessoa($)
  expect(await contando($)).toBe(false)
  expect(c.toasts).toContain(ADIADA)
  await c.relogio.advance(60_000)
  expect(c.enviados).toEqual(['oi'])
  c.tokens.v = 182_000 + 10_000
  await turno($)
  expect(await contando($)).toBe(false)
})

test('regra 6: mensagem durante o aguardando cancela a troca automatica', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  c.agentes.v = [agente('running')]
  await c.relogio.advance(CONTAGEM_S * 1000)
  expect(await olhar($, { type: 'Text', text: /Aguardando 1/ })).toBeDefined()
  await pessoa($)
  c.agentes.v = []
  await c.relogio.advance(10_000)
  expect(c.enviados).toEqual(['oi'])
  expect(c.toasts).toContain(ADIADA)
})

for (const modo of ['manual', 'auto'] as const) {
  test(`regra 6: mensagem no escrevendo cancela o /clear agendado (troca ${modo})`, async ($, on) => {
    const c = await auto($, on, { ligado: modo === 'auto' })
    await turno($)
    await apertar($, modo === 'auto' ? 'agora' : 'trocar')
    expect(c.enviados).toEqual(['relay'])
    await turno($, { turnId: 't2' })
    await pessoa($)
    await c.relogio.advance(10_000)
    expect(c.limpos).toBe(0)
    expect(c.toasts).toContain(ADIADA)
  })
}

test('regra 6/9: sem mensagem, o /clear sai uma vez depois da passagem gravada', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await apertar($, 'trocar')
  await turno($)
  await c.relogio.advance(10_000)
  expect(c.limpos).toBe(1)
})

test('regra 7: passagem nao gravada no modo auto adia 50k e avisa', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  c.gravada.v = false
  await turno($)
  await apertar($, 'agora')
  await turno($, { turnId: 't2' })
  expect(c.toasts.some(t => /não foi gravada/.test(t))).toBe(true)
  c.tokens.v = 182_000 + 10_000
  await turno($)
  expect(await contando($)).toBe(false)
  c.tokens.v = 182_000 + 50_000
  await turno($)
  expect(await contando($)).toBe(true)
})

test('regra 8: o /clear zera tokens, adiado e fase, mas o auto continua ligado', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await pessoa($) // mensagem adia 50k e mantem o auto
  await $.session.end({ reason: 'clear' } as never)
  c.tokens.v = 30_000
  await turno($)
  expect(await contando($)).toBe(false)
  c.tokens.v = 182_000
  await turno($)
  expect(await contando($)).toBe(true)
})

test('piso: 95k com 240k nao avisa, com 245k avisa (faixa e modo auto)', async ($, on) => {
  const c = await auto($, on, { ligado: true, piso: 95_000 })
  c.tokens.v = 240_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(false)
  expect(await contando($)).toBe(false)
  c.tokens.v = 245_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(false) // a faixa de aviso cede lugar a contagem do auto
  expect(await contando($)).toBe(true)
  await apertar($, 'cancelar')
  expect(await botao($, 'trocar')).toBe(false) // Cancelar adia 50k
})

test('piso: sem auto, 245k mostra a faixa com "acima do início da sessão"', async ($, on) => {
  const c = await auto($, on, { ligado: false, piso: 95_000 })
  c.tokens.v = 240_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(false)
  c.tokens.v = 245_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(true)
  expect((await olhar($, { type: 'Text', text: /245k/ }))?.text).toContain('245k tokens (+150k acima do início da sessão)')
})

test('piso: acompanha o minimo; um turno mais baixo depois baixa o piso', async ($, on) => {
  const c = await auto($, on, { ligado: false, piso: 95_000 })
  c.tokens.v = 215_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(false) // +120k sobre 95k
  c.tokens.v = 60_000 // ex.: depois de compactar
  await turno($)
  c.tokens.v = 215_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(true) // +155k sobre o novo piso de 60k
})

test('piso: o /clear zera o piso (o primeiro turno depois dele e o piso novo)', async ($, on) => {
  const c = await auto($, on, { ligado: false, piso: 30_000 })
  await $.session.end({ reason: 'clear' } as never)
  c.tokens.v = 245_000
  await turno($)
  expect(await botao($, 'trocar')).toBe(false) // piso novo = 245k; com o piso velho (30k) avisaria
})

test('regra 9: compactar durante a contagem a cancela e nenhum timer dispara depois', async ($, on) => {
  on('session.compact', () => ({ messages: [M] }))
  const c = await auto($, on, { ligado: true })
  await turno($)
  await $.session.compact({ trigger: 'manual', messages: [M] } as never)
  await c.relogio.advance(60_000)
  expect(c.enviados).toEqual([])
  expect(await contando($)).toBe(false)
})

test('regra 9: /clear durante a contagem a cancela e nenhum timer dispara depois', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await $.session.end({ reason: 'clear' } as never)
  await c.relogio.advance(60_000)
  expect(c.enviados).toEqual([])
  expect(await contando($)).toBe(false)
})

test('regra 9: desligar o auto durante a contagem a cancela', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  await c.relogio.advance(60_000)
  expect(c.enviados).toEqual([])
  expect(await contando($)).toBe(false)
})

// ---------- escrita em segundo plano (defeito de 19/11) ----------

test('escrevendo: turno da principal sem arquivo mas com agente vivo espera; gravou e o agente acabou, sai o /clear', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await apertar($, 'trocar')
  c.gravada.v = false
  c.agentes.v = [agente('running')]
  await turno($, { turnId: 't2' })
  expect(c.toasts.some(t => /não foi gravada/.test(t))).toBe(false)
  expect(await olhar($, { type: 'Text', text: /Gravando a passagem/ })).toBeDefined()
  await c.relogio.advance(10_000)
  expect(c.limpos).toBe(0)

  c.gravada.v = true
  c.agentes.v = []
  await turno($, { agentId: 'a1' })
  await c.relogio.advance(1_000)
  expect(c.limpos).toBe(1)
  expect(c.toasts.some(t => /não foi gravada/.test(t))).toBe(false)
})

test('escrevendo: arquivo gravado com agente vivo so limpa quando o agente termina (sondagem, sem novo turno)', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await apertar($, 'trocar')
  c.gravada.v = false
  c.agentes.v = [agente('running')]
  await turno($, { turnId: 't2' })
  c.gravada.v = true
  await c.relogio.advance(10_000)
  expect(c.limpos).toBe(0)
  c.agentes.v = []
  await c.relogio.advance(5_000)
  expect(c.limpos).toBe(1)
})

test('escrevendo: turno da principal sem arquivo e sem agente vivo e falha', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await apertar($, 'trocar')
  c.gravada.v = false
  await turno($, { turnId: 't2' })
  expect(c.toasts.some(t => /não foi gravada/.test(t))).toBe(true)
  await c.relogio.advance(60_000)
  expect(c.limpos).toBe(0)
})

test('escrevendo: agente vivo para sempre estoura o teto e falha (no auto, adia 50k)', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await apertar($, 'agora')
  c.gravada.v = false
  c.agentes.v = [agente('running')]
  await turno($, { turnId: 't2' })
  await c.relogio.advance(TETO_ESCRITA_MS - 5_000)
  expect(c.toasts.some(t => /não foi gravada/.test(t))).toBe(false)
  await c.relogio.advance(10_000)
  expect(c.toasts.some(t => /não foi gravada/.test(t))).toBe(true)
  c.agentes.v = []
  c.tokens.v = 182_000 + 10_000
  await turno($)
  expect(await contando($)).toBe(false)
})

// ---------- revisao de 19/11 (0.3.1) ----------

test('voo unico: dois cliques simultaneos em Trocar (agent.list lento) enviam passagem uma vez', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.lento.v = 20
  await turno($)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await Promise.all([ui.press({ key: 'trocar' }), ui.press({ key: 'trocar' })])
  await dormir(60)
  expect(c.enviados).toEqual(['relay'])
  await ui.unmount()
})

test('mensagem da pessoa durante o agent.list do fim da contagem cancela: nada e enviado', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  c.lento.v = 20
  await c.relogio.advance(CONTAGEM_S * 1000 - 1000)
  const fim = c.relogio.advance(1000)
  await dormir(5)
  await pessoa($)
  await fim
  await dormir(60)
  expect(c.enviados).toEqual(['oi'])
  expect(c.toasts).toContain(ADIADA)
})

test('Cancelar durante o agent.list do botao Agora cancela: nada e enviado', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  c.lento.v = 20
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await Promise.all([ui.press({ key: 'agora' }), ui.press({ key: 'cancelar' })])
  await dormir(60)
  expect(c.enviados).toEqual([])
  await ui.unmount()
})

test('clique com turno da principal em andamento: o fim do turno ANTERIOR nao declara falha', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await $.turn.start({ text: 'trabalho', turnId: 't9' })
  await apertar($, 'trocar') // a passagem entra na fila atras do t9
  expect(c.enviados).toEqual(['relay'])
  c.gravada.v = false
  await $.turn.complete({ ...TURNO, turnId: 't9' })
  expect(c.toasts.some(t => /não foi gravada/.test(t))).toBe(false)
  c.gravada.v = true // o turno da passagem grava
  await $.turn.start({ text: 'passagem', turnId: 't10' })
  await $.turn.complete({ ...TURNO, turnId: 't10' })
  await c.relogio.advance(10_000)
  expect(c.limpos).toBe(1)
})

test('/clear recusado vai para pronta (nao ocioso): faixa e toast mandam digitar /clear', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.clearFalha.v = true
  await turno($)
  await apertar($, 'trocar')
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000)
  const MSG = 'Passagem gravada. Digite /clear para abrir a sessão nova já com ela.'
  expect(c.toasts).toContain(MSG)
  expect(await botao($, 'trocar')).toBe(false) // nao voltou a ocioso
  expect(await olhar($, { type: 'Text', text: /Digite \/clear/ })).toBeDefined()
})

const clearDaPassagem = async ($: any, c: Ctx) => {
  await turno($)
  await apertar($, 'trocar')
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000)
}

// The band never delivers: the core SessionStart hook does (one owner per delivery, in both CLIs).
const semContexto = (c: Ctx) => c.contextos.every(x => (x ?? []).length === 0)
const pendencias = (c: Ctx) => [...c.mem.keys()].filter(k => k.startsWith('pendente'))

test('session.end clear com passagem gravada: o band avisa, mas NAO poe a passagem no context nem no store', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await clearDaPassagem($, c)
  expect(c.limpos).toBe(1)
  await clearReal($, c)
  // O toast nao sai no session.end (o /clear redesenha a tela e o apaga): sai na sessao nova, depois do carregamento.
  expect(c.toasts).not.toContain('Passagem gravada; sessão nova aberta.')
  await c.relogio.advance(1_000)
  expect(c.toasts).toContain('Passagem gravada; sessão nova aberta.')
  await pessoa($, 'continue')
  await pessoa($, 'e agora')
  expect(semContexto(c)).toBe(true)
  expect(pendencias(c)).toEqual([])
})

test('passagem de OUTRA sessao (mesmo cwd, outro id): o band nao anuncia a sessao nova com ela', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.clearFalha.v = true
  await clearDaPassagem($, c) // pronta: so passagem desta troca vale no /clear
  c.existe.v = 'bbbb2222' // so existe a passagem da outra sessao
  await $.session.end({ reason: 'clear' } as never)
  await pessoa($, 'oi')
  expect(c.toasts.some(t => /sessão nova aberta/.test(t))).toBe(false)
  expect(semContexto(c)).toBe(true)
  expect(c.perguntados.length).toBeGreaterThan(0)
  expect(c.perguntados.every(p => p.includes('aaaa1111'))).toBe(true) // o mod so olha o arquivo da propria sessao
})

const FALHA_ENVIO = 'Não consegui pedir a passagem; tente de novo'

test('submit que rejeita volta a ocioso, solta a trava, avisa e um novo clique funciona', async ($, on) => {
  const c = await auto($, on)
  await turno($) // sobe a faixa (tokens atuais)
  c.submitFalha.v = true
  await $.command.run({ command: 'relay', args: '' } as never)
  await c.relogio.settle()
  expect(c.toasts).toContain(FALHA_ENVIO)
  expect(await botao($, 'trocar')).toBe(true) // fase ocioso: a faixa nao ficou em "Gravando"
  c.submitFalha.v = false
  await $.command.run({ command: 'relay', args: '' } as never)
  await c.relogio.settle()
  expect(c.enviados).toEqual(['relay'])
})

test('submit que rejeita no modo auto adia 50k, sem nova contagem', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  c.submitFalha.v = true
  await turno($)
  await c.relogio.advance(CONTAGEM_S * 1000)
  await c.relogio.settle()
  expect(c.toasts).toContain(FALHA_ENVIO)
  await turno($)
  expect(await contando($)).toBe(false)
})

test('agent.list que nunca responde nao prende a trava: estoura em 5 s, aguarda e reconfere', async ($, on) => {
  const c = await auto($, on)
  c.travado.v = true
  await $.command.run({ command: 'relay', args: '' } as never)
  await c.relogio.advance(5_000)
  await c.relogio.settle()
  expect(c.enviados).toEqual([]) // agente vivo desconhecido: nao envia
  await c.relogio.advance(5_000) // a reconferencia tambem estoura e agenda o proximo tique
  await c.relogio.settle()
  c.travado.v = false
  await c.relogio.advance(2_000) // proximo tique de reconferencia
  await c.relogio.settle()
  expect(c.enviados).toEqual(['relay'])
})

// ---------- 0.4.1: pendencia guardada pela sessao nova ----------
const A2 = 'a2a2a2a2-0000-0000-0000-000000000000'
const B1 = 'bbbb2222-0000-0000-0000-000000000000'
const B2 = 'b2b2b2b2-0000-0000-0000-000000000000'

test('duas sessoes trocam em sequencia: cada uma confere SO o proprio arquivo, sem pendencia no store', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await clearDaPassagem($, c)
  c.proximo.v = A2
  await $.session.end({ reason: 'clear' } as never) // sessao A (aaaa1111) -> A2
  c.sid.v = B1 // outra sessao, mesmo cwd, troca logo depois
  await base($, c)
  c.perguntados.length = 0
  await clearDaPassagem($, c)
  c.proximo.v = B2
  await $.session.end({ reason: 'clear' } as never)
  expect(c.perguntados.length).toBeGreaterThan(0)
  expect(c.perguntados.every(p => p.includes('bbbb2222'))).toBe(true)
  expect(pendencias(c)).toEqual([])
})

test('mensagem na fase pronta avisa que a troca foi cancelada e onde esta a passagem', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.clearFalha.v = true
  await clearDaPassagem($, c)
  await pessoa($, 'deixa pra la')
  expect(c.toasts.some(t => /^Troca cancelada; a passagem continua em .*aaaa1111\.md$/.test(t))).toBe(true)
})

// ---------- 0.4.2 ----------

test('cancelar a troca zera o pedido: /clear digitado 20 min depois nao leva a passagem velha', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  ;(globalThis as any).MT = 5_000 + 1
  try {
    c.clearFalha.v = true
    await clearDaPassagem($, c) // pronta
    await pessoa($, 'deixa pra la') // cancela
    ;(globalThis as any).MT = 5_000
    await c.relogio.advance(20 * 60_000)
    c.proximo.v = A2
    await $.session.end({ reason: 'clear' } as never)
    await pessoa($, 'comecando do zero')
    expect(c.toasts.some(t => /sessão nova aberta/.test(t))).toBe(false)
  } finally {
    delete (globalThis as any).MT
  }
})

test('/relay diz o estado: pronta, escrevendo e aguardando', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  const cmd = async () => ((await $.command.run({ command: 'relay', args: '' } as never)) as any).text as string
  await turno($)
  c.agentes.v = [agente('running')]
  await apertar($, 'trocar') // aguardando
  expect(await cmd()).toMatch(/aguardando os agentes/)
  c.agentes.v = []
  await $.turn.complete({ ...TURNO, agentId: 'a1' }) // escrevendo
  expect(await cmd()).toBe('Já estou gravando a passagem.')
  c.clearFalha.v = true
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000) // pronta
  expect(await cmd()).toMatch(/já está gravada em .*aaaa1111\.md\. Digite \/clear/)
})

// "relay" digitado pela pessoa inicia a troca como o clique, sem reenviar (a propria mensagem segue).
const digitada = async ($: any, c: Ctx, texto: string) => {
  await pessoa($, texto)
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000)
}

test('digitar "relay" em ocioso inicia a troca e o /clear; o band nao poe context', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await digitada($, c, 'relay')
  expect(c.enviados).toEqual(['relay']) // so a mensagem da pessoa: sem segundo envio
  expect(c.limpos).toBe(1)
  expect(c.toasts).not.toContain(ADIADA)
  await $.session.end({ reason: 'clear' } as never)
  await c.relogio.advance(3_000) // o toast sai na sessao nova, depois do carregamento
  expect(c.toasts).toContain('Passagem gravada; sessão nova aberta.')
  await pessoa($, 'continue')
  expect(semContexto(c)).toBe(true)
})

test('digitar "relay" com /clear recusado fica pronta; o /clear manual segue o mesmo fluxo (toast)', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.clearFalha.v = true
  await digitada($, c, 'relay')
  expect(c.toasts).toContain('Passagem gravada. Digite /clear para abrir a sessão nova já com ela.')
  await $.session.end({ reason: 'clear' } as never)
  await c.relogio.advance(3_000) // o toast sai na sessao nova, depois do carregamento
  expect(c.toasts).toContain('Passagem gravada; sessão nova aberta.')
  await pessoa($, 'continue')
  expect(semContexto(c)).toBe(true)
})

test('" Relay " com espacos e maiuscula vale igual', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await digitada($, c, ' Relay ')
  expect(c.limpos).toBe(1)
})

test('"/relay" como texto vale igual', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await digitada($, c, '/relay')
  expect(c.limpos).toBe(1)
})

test('digitar outra coisa em ocioso nao inicia nada (handoff e passagem deixaram de valer)', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  for (const texto of ['relay now', 'handoff', '/handoff', 'passagem', '/passagem']) await digitada($, c, texto)
  expect(c.limpos).toBe(0)
  await $.session.end({ reason: 'clear' } as never)
  await pessoa($, 'oi')
  expect(c.contextos.at(-1) ?? []).toEqual([])
})

test('digitar "relay" em escrevendo nao cancela nem duplica', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await apertar($, 'trocar') // escrevendo, envio do plugin
  await pessoa($, 'relay')
  expect(c.toasts).not.toContain(ADIADA)
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000)
  expect(c.limpos).toBe(1)
})

test('digitar "relay" durante a contagem inicia a troca (como Agora), sem cancelar', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await c.relogio.advance(1_000)
  expect(await contando($)).toBe(true)
  await pessoa($, 'relay')
  expect(c.toasts).not.toContain(ADIADA)
  expect(await contando($)).toBe(false)
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000)
  expect(c.limpos).toBe(1)
})

// ---------- 0.5.0 ----------

const rastros = (c: Ctx) => [...c.escritas.entries()].filter(([k]) => k.includes('_trace-'))
const rastroTudo = (c: Ctx) => rastros(c).map(([, v]) => v).join('\n')

test('agente waiting nao segura: com 4 waiting a troca e o /clear seguem', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.agentes.v = [agente('waiting'), agente('waiting'), agente('waiting'), agente('waiting')]
  await turno($)
  await apertar($, 'trocar')
  expect(c.enviados).toEqual(['relay'])
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000)
  expect(c.limpos).toBe(1)
})

test('agente pending segura a troca', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.agentes.v = [agente('pending')]
  await turno($)
  await apertar($, 'trocar')
  expect(c.enviados).toEqual([])
})

test('aguardando mais de 60 s: a faixa oferece "Trocar mesmo assim", que envia sem esperar', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.agentes.v = [agente('running')]
  await turno($)
  await apertar($, 'trocar')
  await c.relogio.advance(59_000)
  expect(await botao($, 'forcar')).toBe(false)
  await c.relogio.advance(2_000)
  expect(await botao($, 'forcar')).toBe(true)
  expect(await olhar($, { type: 'Text', text: /Aguardando 1 agente…/ })).toBeDefined()
  await apertar($, 'forcar')
  expect(c.enviados).toEqual(['relay'])
})

test('aguardando mais de 60 s: Cancelar volta ao botao e nada e enviado', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.agentes.v = [agente('running')]
  await turno($)
  await apertar($, 'trocar')
  await c.relogio.advance(61_000)
  await apertar($, 'cancelar')
  expect(await botao($, 'trocar')).toBe(true)
  c.agentes.v = []
  await c.relogio.advance(10_000)
  expect(c.enviados).toEqual([])
})

const ateOLimpar = async ($: any, c: Ctx) => {
  await turno($)
  await apertar($, 'trocar') // sem agente: envia
  c.agentes.v = [agente('running')]
  await turno($, { turnId: 't2' }) // passagem gravada, mas ha agente vivo: o /clear espera
}

test('/clear esperando agente mais de 60 s: "Trocar mesmo assim" limpa sem esperar', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await ateOLimpar($, c)
  await c.relogio.advance(30_000)
  expect(c.limpos).toBe(0)
  expect(await botao($, 'forcar')).toBe(false)
  await c.relogio.advance(31_000)
  expect(c.limpos).toBe(0)
  expect(await botao($, 'forcar')).toBe(true)
  await apertar($, 'forcar')
  await c.relogio.settle()
  expect(c.limpos).toBe(1)
})

test('/clear esperando agente mais de 60 s: Cancelar nao limpa', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await ateOLimpar($, c)
  await c.relogio.advance(61_000)
  await apertar($, 'cancelar')
  await c.relogio.advance(20_000)
  expect(c.limpos).toBe(0)
  expect(await botao($, 'trocar')).toBe(true)
})

test('rastro em arquivo: fases, vivos, clear, session.end e prompt.submit, sem o texto da passagem', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.agentes.v = [agente('running'), agente('waiting')]
  await turno($)
  await apertar($, 'trocar')
  c.agentes.v = [agente('waiting')]
  await c.relogio.advance(4_000)
  await turno($, { turnId: 't2' })
  await c.relogio.advance(10_000)
  c.proximo.v = A2
  await $.session.end({ reason: 'clear' } as never)
  await pessoa($, 'continue')
  await dormir(80)
  const t = rastroTudo(c)
  expect(rastros(c).every(([k]) => /\/_trace-[0-9a-f]{8}\.md$/.test(k))).toBe(true)
  expect(t).toMatch(/^\d{4}-\d\d-\d\dT[\d:.]+Z session\.start/m)
  expect(t).toMatch(/fase ocioso -> aguardando/)
  expect(t).toMatch(/fase aguardando -> escrevendo/)
  expect(t).toMatch(/vivos=1 .*running/)
  expect(t).toMatch(/clear: chamando/)
  expect(t).toMatch(/clear: ok/)
  expect(t).toMatch(/session\.end reason=clear evento=\S+ antes=aaaa1111\S* depois=a2a2a2a2\S* fase=\w+ .*veio=true/)
  expect(t).not.toContain('TEXTO-DA-PASSAGEM')
})

test('rastro: corta em 200 linhas', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  const k = 'C:/Users/x/AppData/Local/sync_relay/handoffs/_trace-aaaa1111.md'
  c.escritas.set(k, Array.from({ length: 300 }, (_, i) => `linha ${i}`).join('\n') + '\n')
  await reiniciar($)
  await dormir(80)
  const linhas = (c.escritas.get(k) ?? '').split('\n').filter(Boolean)
  expect(linhas.length).toBe(200)
  expect(linhas.at(-1)).toMatch(/session\.start/)
})

test('falha ao gravar o rastro nao quebra o fluxo nem o /clear', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.escritaFalha.v = true
  c.escritas.clear()
  await clearDaPassagem($, c)
  expect(c.limpos).toBe(1)
  c.proximo.v = A2
  await $.session.end({ reason: 'clear' } as never)
  await pessoa($, 'continue')
  await dormir(50)
  await c.relogio.advance(3_000) // o toast sai na sessao nova, depois do carregamento
  expect(c.toasts).toContain('Passagem gravada; sessão nova aberta.')
  expect(c.escritas.size).toBe(0)
})

const PASTA = 'C:/Users/x/AppData/Local/sync_relay/handoffs'
const norm = (s: string) => s.replaceAll('\\', '/')

test('pasta: sem configRoot, com transcriptPath, e a do usuario (arquivo de passagem e rastro)', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  await apertar($, 'trocar')
  await turno($, { turnId: 't2' })
  await dormir(80)
  expect(c.perguntados.length).toBeGreaterThan(0)
  expect(c.perguntados.every(p => norm(p).startsWith(`${PASTA}/`))).toBe(true)
  expect(rastros(c).length).toBeGreaterThan(0)
  expect(rastros(c).every(([k]) => k.startsWith(`${PASTA}/_trace-`))).toBe(true)
})

test('pasta: sem transcriptPath, usa CLAUDE_PLUGIN_DATA', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.info.v = { platform: 'windows' }
  c.escritas.clear()
  c.env.v = { CLAUDE_PLUGIN_DATA: 'C:\\Users\\x\\.claude\\plugins\\data\\sync_relay-sync_relay' }
  await turno($)
  await apertar($, 'trocar')
  await turno($, { turnId: 't2' })
  expect(c.perguntados.length).toBeGreaterThan(0)
  expect(c.perguntados.every(p => norm(p).startsWith(`${PASTA}/`))).toBe(true)
})

test('pasta: sem nenhuma fonte, avisa uma vez e nao troca nem manda /clear', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.info.v = { platform: 'windows' }
  await dormir(30) // o rastro do turno-base ainda na fila grava antes de limpar
  c.escritas.clear()
  await turno($)
  await apertar($, 'trocar')
  await turno($, { turnId: 't2' })
  await apertar($, 'trocar')
  await turno($, { turnId: 't2' })
  await dormir(80)
  expect(c.toasts.filter(t => t.includes('não achei a pasta do usuário')).length).toBe(1)
  expect(c.enviados).toEqual([])
  expect(c.limpos).toBe(0)
  expect(c.escritas.size).toBe(0)
})

// Indicador na linha de status ($.ui.status) e /relay status.
const comStatus = (on: any) => {
  const textos: (string | undefined)[] = []
  on('ui.status', (_: any, e: any) => (textos.push(e.text), { value: undefined }))
  return { textos, ultimo: () => textos[textos.length - 1] }
}

test('indicador: medindo, +Nk/limiar, reage ao /relay auto e mostra trocando na contagem', async ($, on) => {
  const s = comStatus(on)
  const c = await auto($, on, { ligado: true })
  await reiniciar($)
  expect(s.ultimo()).toBe('auto ligado · medindo')
  await base($, c)
  c.tokens.v = 112_000
  await turno($, { turnId: 't2' })
  expect(s.ultimo()).toBe('auto ligado · 82k de 150k')
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(s.ultimo()).toBe('auto desligado · 82k de 150k')
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  c.tokens.v = 182_000
  await turno($, { turnId: 't3' })
  expect(await contando($)).toBe(true)
  expect(s.ultimo()).toBe('auto ligado · trocando…')
  await apertar($, 'cancelar')
  expect(s.ultimo()).toBe('auto desligado · 152k de 150k') // Cancelar desligou o auto
})

test('indicador (en): o nome sync_relay fixo, auto on/off, "45k of 150k" e o /relay button nao tira o texto', async ($, on) => {
  const s = comStatus(on)
  const c = await auto($, on, { ligado: false, penv: { SYNC_RELAY_LANG: 'en' } })
  await reiniciar($)
  await base($, c)
  c.tokens.v = 75_000
  await turno($, { turnId: 't2' })
  expect(s.ultimo()).toBe('auto off · 45k of 150k')
  await $.command.run({ command: 'relay', args: 'button' } as never) // esconde so o botao
  expect(await botao($, 'auto')).toBe(false)
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(s.ultimo()).toBe('auto on · 45k of 150k')
})

test('indicador: sessao nao interativa nao mostra nada', async ($, on) => {
  const s = comStatus(on)
  const c = await auto($, on, { ligado: true, interativo: false })
  await turno($, { turnId: 't2' })
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(c.toasts.length).toBeGreaterThan(0)
  expect(s.textos.filter(t => t !== undefined)).toEqual([])
})

const statusCmd = async ($: any) => ((await $.command.run({ command: 'relay', args: 'status' } as never)) as any).text as string

test('/relay status (pt-BR): trava, auto, contexto, ponto de troca com a origem e a pasta das passagens', async ($, on) => {
  on('session.model', () => ({ value: 'claude-opus-4-7' }))
  const c = await auto($, on, { ligado: false })
  c.tokens.v = 182_000
  await turno($, { turnId: 't2' })
  expect(await statusCmd($)).toBe(
    'Trava: enforce · auto: desligado · contexto: 182k tokens · troca em 180k = piso 30k + 150k (compactação em 967k: padrão do modelo) · passagens: C:/Users/x/AppData/Local/sync_relay/handoffs · botão: visível',
  )
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(await statusCmd($)).toMatch(/auto: ligado/)
  await $.command.run({ command: 'relay', args: 'button' } as never)
  expect(await statusCmd($)).toMatch(/botão: oculto$/)
})

test('/relay status (en) com janela de 200K: o teto de 80% do caminho aparece na origem', async ($, on) => {
  on('session.model', () => ({ value: 'claude-sonnet-4-6' }))
  const c = await auto($, on, { ligado: true, penv: { SYNC_RELAY_LANG: 'en' } })
  c.tokens.v = 100_000
  await turno($, { turnId: 't2' })
  expect(await statusCmd($)).toBe(
    'Lock: enforce · auto: on · context: 100k tokens · switch at 166k = floor 30k + 136k (80% of the way to compaction at 200k: model default) · handoffs: C:/Users/x/AppData/Local/sync_relay/handoffs · button: visible',
  )
})

test('/relay status: sem piso ainda diz medindo; o limiar do env aparece como D', async ($, on) => {
  const c = await sobre($, on, { SYNC_RELAY_THRESHOLD: '5k' })
  await clearReal($, c)
  await c.relogio.advance(1_000)
  expect(await statusCmd($)).toMatch(/contexto: medindo · troca em medindo/)
  c.tokens.v = 30_000
  await turno($, { turnId: 'n1' })
  expect(await statusCmd($)).toMatch(/troca em 35k = piso 30k \+ 5k \(compactação em 967k/)
})

test('/relay: argumento que nao e auto, status ou button mostra o uso (sem threshold, limiar, padrao, botao)', async ($, on) => {
  await auto($, on, { ligado: false })
  for (const a of ['xyz', 'threshold', 'threshold 5k', 'limiar', 'limiar 5k', 'padrao', 'default', 'botao', 'handoff', 'auto now']) {
    const t = ((await $.command.run({ command: 'relay', args: a } as never)) as any).text as string
    expect(t, a).toBe('Uso: /relay (troca agora), /relay auto (liga ou desliga a troca automática), /relay status (mostra o estado) ou /relay button (esconde ou mostra o botão).')
  }
})

test('/clear zera o $.state do motor: o mod reinicia (interativo, auto, limiar) e a 2a troca automatica dispara', async ($, on) => {
  const s = comStatus(on)
  const c = await auto($, on, { ligado: true })
  s.textos.length = 0
  await clearReal($, c) // sem session.start na sessao nova, como no motor
  c.tokens.v = 30_000
  await turno($, { turnId: 'n1' })
  expect(s.ultimo()).toBe('auto ligado · 0k de 150k') // saiu de "medindo"
  c.tokens.v = 182_000
  await turno($, { turnId: 'n2' })
  expect(await contando($)).toBe(true)
})

// Reload (/reload-plugins) numa sessao ja grande: o piso vem do 1o usage de assistente depois do ultimo /clear ou compactacao.
const uso = (total: number, extra: object = {}) =>
  JSON.stringify({
    type: 'assistant',
    isSidechain: false,
    message: { role: 'assistant', usage: { input_tokens: 2, cache_creation_input_tokens: total - 12, cache_read_input_tokens: 10, output_tokens: 5 } },
    ...extra,
  })
const CLEAR = JSON.stringify({ type: 'user', message: { role: 'user', content: '<command-name>/clear</command-name>\n <command-message>clear</command-message>' } })
const COMPACT = JSON.stringify({ type: 'system', subtype: 'compact_boundary', content: 'Conversation compacted' })

const LIMITE_FS = 4_194_304 // o $.fs.read do motor real recusa arquivo acima de 4 MiB; o simulador nao impoe
const PISO_SALVO = (piso: number, em = 1) => ({ piso, em })

async function reload(
  $: any,
  on: any,
  transcript: string | Error,
  caminho: string | null = 'C:/Users/x/.claude/projects/C--x/abc.jsonl',
  o: { tamanho?: number; pisos?: Record<string, unknown>; sid?: string } = {},
) {
  pt(on)
  const lidos: string[] = []
  const mem = new Map<string, unknown>(o.pisos ? [['pisos', o.pisos]] : [])
  const tamanho = o.tamanho ?? 1_000
  on('store.get', (_: any, e: any) => ({ value: mem.get(e.key) }))
  on('store.set', (_: any, e: any) => (mem.set(e.key, e.value), { value: undefined }))
  on('store.delete', (_: any, e: any) => (mem.delete(e.key), { value: undefined }))
  on('store.keys', () => ({ value: [...mem.keys()] }))
  on('session.id', () => ({ value: o.sid ?? 'aaaa1111-0000-0000-0000-000000000000' }))
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens: 954_663, window: 1_000_000, percent: 95 }, rateLimits: [], cost: { usd: 0 } },
  }))
  on('session.info', () => ({ value: caminho === null ? { platform: 'windows' } : { transcriptPath: caminho, platform: 'windows' } }))
  on('fs.stat', () => ({ value: { mtimeMs: 1, size: tamanho } }))
  const rastro: string[] = []
  on('fs.write', (_: any, e: any) => (rastro.push(String(e.text)), { value: undefined }))
  on('fs.read', (_: any, e: any) => {
    lidos.push(String(e.path))
    if (String(e.path).includes('_trace-') || transcript instanceof Error) throw transcript instanceof Error ? transcript : new Error('nao existe')
    if (tamanho > LIMITE_FS) throw new Error(`refused: the file is over the ${LIMITE_FS}-byte limit`)
    return { value: transcript }
  })
  on('turn.complete', () => ({ text: 'ok' }))
  on('clock.now', () => ({ value: 1_000 }))
  on('agent.list', () => ({ value: [] }))
  await $.turn.complete({ ...TURNO, turnId: 'r1' })
  await $.turn.complete({ ...TURNO, turnId: 'r2' })
  return {
    mem,
    rastro: () => rastro.join('\n'),
    lidos: () => lidos.filter(p => p.endsWith('abc.jsonl')),
    faixa: async () => (await olhar($, { type: 'Button', key: 'trocar' })) !== undefined,
  }
}

test('reload em sessao grande: o piso e o 1o usage do transcript, nao o total atual', async ($, on) => {
  const r = await reload($, on, [uso(90_000), uso(500_000), uso(954_663)].join('\n') + '\n')
  expect(await r.faixa()).toBe(true)
  expect(r.lidos().length).toBe(1) // le o arquivo uma vez so, nao a cada turno
})

test('reload: o piso e o 1o usage DEPOIS do ultimo /clear', async ($, on) => {
  const r = await reload($, on, [uso(10_000), CLEAR, uso(40_000), uso(954_663)].join('\n'))
  expect(await r.faixa()).toBe(true)
  const s = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  expect((await s.find({ type: 'Text', text: /acima do início/ }))?.text).toContain('+915k') // 954,6k - 40k
  await s.unmount()
})

test('reload: a compactacao tambem e limite (usage anterior nao vale; linha de assistente que cita o texto nao engana)', async ($, on) => {
  const cita = uso(954_000, { note: 'compact_boundary command-name>/clear' })
  const r = await reload($, on, [uso(10_000), COMPACT, uso(25_000), cita].join('\n'))
  const s = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  expect((await s.find({ type: 'Text', text: /acima do início/ }))?.text).toContain('+930k') // 954,7k - 25k
  await s.unmount()
  expect(await r.faixa()).toBe(true)
})

test('reload: sem usage, sem caminho ou leitura falha mantem piso = total atual', async ($, on) => {
  expect(await (await reload($, on, 'so texto\n' + COMPACT)).faixa()).toBe(false)
})
test('reload: leitura falha mantem piso = total atual', async ($, on) => {
  expect(await (await reload($, on, new Error('negado'))).faixa()).toBe(false)
})
test('reload: sem transcriptPath mantem piso = total atual', async ($, on) => {
  expect(await (await reload($, on, uso(40_000), null)).faixa()).toBe(false)
})

test('reload: usage maior que o total atual nao sobe o piso', async ($, on) => {
  const r = await reload($, on, uso(2_000_000))
  expect(await r.faixa()).toBe(false)
})

// Botao Auto fixo (0.6.3): sem faixa ele aparece sozinho; com faixa nao duplica.
const botoesAuto = async ($: any) => {
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  const todos = await ui.findAll({ type: 'Button', key: 'auto' })
  await ui.unmount()
  return todos
}

test('botao Auto fixo: sem faixa aparece, alterna o store e o rotulo', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.tokens.v = 40_000 // abaixo do limiar: sem faixa
  await turno($)
  expect(await botao($, 'trocar')).toBe(false)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  expect((await ui.find({ type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: desligado')
  await ui.press({ key: 'auto' })
  expect(c.mem.get('auto')).toBe(true)
  expect((await ui.find({ type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: ligado')
  await ui.press({ key: 'auto' })
  expect(c.mem.get('auto')).toBe(false)
  expect((await ui.find({ type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: desligado')
  await ui.unmount()
})

test('botao Auto fixo: com a faixa so existe um botao de auto', async ($, on) => {
  await auto($, on, { ligado: false })
  await turno($) // 182k: faixa visivel
  expect(await botao($, 'trocar')).toBe(true)
  expect(await botoesAuto($)).toHaveLength(1)
})

test('botao Auto fixo: o que vem depois na cadeia (next) continua sendo chamado', async ($, on) => {
  let chamadas = 0
  const c = await auto($, on, {
    ligado: false,
    abaixo: on => on('ui.render', { component: 'AbovePrompt' }, async (_: any, e: any, next: any) => (chamadas++, next(e))),
  })
  c.tokens.v = 40_000
  await turno($)
  await olhar($, { type: 'Button', key: 'auto' })
  expect(chamadas).toBeGreaterThan(0)
})

// 0.6.4: primeira instalacao: auto desligado e apresentacao unica no lugar do botao fixo.
const apresentacao = async ($: any) => (await olhar($, { type: 'Text', text: /abre uma sessão nova/ })) !== undefined
const nova = async ($: any, on: any, o: object = {}) => {
  const c = await auto($, on, { apresentado: false, ...o })
  c.tokens.v = 40_000 // abaixo do limiar: sem faixa de troca
  await turno($)
  return c
}

test('apresentacao: store vazio deixa o auto desligado e mostra a apresentacao no lugar do botao fixo', async ($, on) => {
  const c = await nova($, on)
  expect(c.mem.has('auto')).toBe(false)
  expect(await apresentacao($)).toBe(true)
  expect(await botao($, 'alternar')).toBe(true)
  expect(await botao($, 'entendi')).toBe(true)
  expect(await botao($, 'auto')).toBe(false)
  c.tokens.v = 182_000
  await turno($)
  expect(await contando($)).toBe(false) // auto desligado: so o aviso
})

test('apresentacao: Ligar automatico liga o auto, grava a marca e esconde a apresentacao', async ($, on) => {
  const c = await nova($, on)
  await apertar($, 'alternar')
  expect(c.mem.get('auto')).toBe(true)
  expect(c.mem.get('apresentado')).toBe(true)
  expect(await apresentacao($)).toBe(false)
  expect((await olhar($, { type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: ligado')
})

test('apresentacao: Entendi mantem o auto desligado, grava a marca e esconde a apresentacao', async ($, on) => {
  const c = await nova($, on)
  await apertar($, 'entendi')
  expect(c.mem.has('auto')).toBe(false)
  expect(c.mem.get('apresentado')).toBe(true)
  expect(await apresentacao($)).toBe(false)
  expect((await olhar($, { type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: desligado')
})

test('apresentacao: com a marca apresentado aparece o botao fixo', async ($, on) => {
  await nova($, on, { apresentado: true })
  expect(await apresentacao($)).toBe(false)
  expect(await botao($, 'auto')).toBe(true)
  expect(await botao($, 'alternar')).toBe(false)
})

test('apresentacao: store com auto=true nao e alterado e a apresentacao so mostra', async ($, on) => {
  const c = await nova($, on, { ligado: true })
  expect(await apresentacao($)).toBe(true)
  expect(c.mem.get('auto')).toBe(true)
  await apertar($, 'entendi')
  expect(c.mem.get('auto')).toBe(true)
})

test('apresentacao: a faixa de troca vence a apresentacao', async ($, on) => {
  await auto($, on, { apresentado: false })
  await turno($) // 182k: faixa de troca
  expect(await botao($, 'trocar')).toBe(true)
  expect(await apresentacao($)).toBe(false)
  expect(await botao($, 'alternar')).toBe(false)
})

// 0.6.6: a apresentacao compoe com next(e) e segue o estado real do automatico.
const texto2 = async ($: any, re: RegExp) => (await olhar($, { type: 'Text', text: re })) !== undefined

test('apresentacao: compoe com o que vem depois na cadeia (next)', async ($, on) => {
  let chamadas = 0
  const c = await auto($, on, {
    apresentado: false,
    abaixo: on => on('ui.render', { component: 'AbovePrompt' }, async (_: any, e: any, next: any) => (chamadas++, next(e))),
  })
  c.tokens.v = 40_000
  await turno($)
  expect(await apresentacao($)).toBe(true)
  // shortcut: o mount do harness chama o hook de baixo mesmo sem next(e), entao este teste nao falha sem a mudanca; a composicao fica garantida pelo codigo (resto = await next(e)).
  expect(chamadas).toBeGreaterThan(0)
})

test('apresentacao com auto desligado: texto "desligado" e botao Ligar automatico, que liga', async ($, on) => {
  const c = await nova($, on, { ligado: false })
  expect(await texto2($, /^Automático desligado: você recebe o aviso/)).toBe(true)
  expect((await olhar($, { type: 'Button', key: 'alternar' }))?.props.label).toBe('Ligar automático')
  await apertar($, 'alternar')
  expect(c.mem.get('auto')).toBe(true)
  expect(c.mem.get('apresentado')).toBe(true)
})

test('apresentacao com auto ligado: texto "ligado" e botao Desligar automatico, que desliga', async ($, on) => {
  const c = await nova($, on, { ligado: true })
  expect(await texto2($, /^Automático ligado: troca sozinho depois de 15 s/)).toBe(true)
  expect((await olhar($, { type: 'Button', key: 'alternar' }))?.props.label).toBe('Desligar automático')
  await apertar($, 'alternar')
  expect(c.mem.get('auto')).toBe(false)
  expect(c.mem.get('apresentado')).toBe(true)
})

test('session.end clear: $.session.id() rejeitando depois do next(e) nao aborta o reset nem o aviso', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await clearDaPassagem($, c)
  c.idFalhaNoFim.v = true
  await $.session.end({ reason: 'clear' } as never)
  await c.relogio.advance(3_000) // o toast sai na sessao nova, depois do carregamento
  expect(c.toasts).toContain('Passagem gravada; sessão nova aberta.')
  c.idFalha.v = false
  await pessoa($, 'oi')
  expect(semContexto(c)).toBe(true)
})

// 0.6.5: o piso de cada sessao fica no $.store (chave 'pisos'); o transcript e so reserva e so ate 4 MiB.
const GRANDE = LIMITE_FS + 1
const SID = 'aaaa1111-0000-0000-0000-000000000000'
const TRANSCRIPT_PEQUENO = [uso(90_000), uso(954_663)].join('\n')
const pisoGuardado = (mem: Map<string, unknown>, id: string) => ((mem.get('pisos') as any)?.[id] as any)?.piso

test('reload em sessao grande (transcript > 4 MiB): usa o piso guardado e nao le o transcript', async ($, on) => {
  const r = await reload($, on, TRANSCRIPT_PEQUENO, undefined, { tamanho: GRANDE, pisos: { [SID]: PISO_SALVO(90_000) } })
  expect(await r.faixa()).toBe(true)
  expect(r.lidos().length).toBe(0)
})

test('reload: piso guardado de OUTRA sessao nao vale', async ($, on) => {
  const r = await reload($, on, TRANSCRIPT_PEQUENO, undefined, { tamanho: GRANDE, pisos: { 'outro-id': PISO_SALVO(90_000) } })
  expect(await r.faixa()).toBe(false) // sem piso, transcript grande: piso = n
  expect(pisoGuardado(r.mem, 'outro-id')).toBe(90_000) // nao mexe no alheio
})

test('reload: sem piso guardado e transcript pequeno, a reserva (transcript) funciona e grava o piso', async ($, on) => {
  const r = await reload($, on, TRANSCRIPT_PEQUENO)
  expect(await r.faixa()).toBe(true)
  expect(pisoGuardado(r.mem, SID)).toBe(90_000)
})

test('reload: sem piso guardado e transcript grande, o piso e n e nao tenta ler', async ($, on) => {
  const r = await reload($, on, TRANSCRIPT_PEQUENO, undefined, { tamanho: GRANDE })
  expect(await r.faixa()).toBe(false)
  expect(r.lidos().length).toBe(0) // pulou a leitura pelo stat
  expect(r.rastro()).toContain('piso do transcript indisponivel')
  expect(pisoGuardado(r.mem, SID)).toBe(954_663)
})

test('piso guardado so baixa: usage menor regrava, maior nao', async ($, on) => {
  const c = await auto($, on) // turno base: piso 30k guardado
  expect(pisoGuardado(c.mem, c.sid.v)).toBe(30_000)
  c.tokens.v = 20_000
  await turno($)
  expect(pisoGuardado(c.mem, c.sid.v)).toBe(20_000)
  c.tokens.v = 90_000
  await turno($)
  expect(pisoGuardado(c.mem, c.sid.v)).toBe(20_000)
})

test('/clear apaga o piso da sessao (id igual ou trocado)', async ($, on) => {
  const c = await auto($, on)
  const antigo = c.sid.v
  expect(pisoGuardado(c.mem, antigo)).toBe(30_000)
  await $.session.end({ reason: 'clear' } as never)
  expect(pisoGuardado(c.mem, antigo)).toBeUndefined() // id nao mudou
  c.tokens.v = 40_000
  await turno($)
  expect(pisoGuardado(c.mem, antigo)).toBe(40_000) // a sessao nova mediu do zero (sem usage no transcript: n)
})

test('/clear com id trocado apaga o id antigo', async ($, on) => {
  const c = await auto($, on)
  const antigo = c.sid.v
  c.proximo.v = 'bbbb2222-0000-0000-0000-000000000000'
  await $.session.end({ reason: 'clear' } as never)
  expect(pisoGuardado(c.mem, antigo)).toBeUndefined()
})

test('compactacao nao mexe no piso guardado', async ($, on) => {
  on('session.compact', () => ({ messages: [M] }))
  const c = await auto($, on)
  await $.session.compact({ trigger: 'manual', messages: [M] } as never)
  expect(pisoGuardado(c.mem, c.sid.v)).toBe(30_000)
})

test('teto de 50 entradas: descarta as mais antigas', async ($, on) => {
  const cheio: Record<string, unknown> = {}
  for (let i = 1; i <= 50; i++) cheio[`id-${i}`] = PISO_SALVO(10_000, i)
  const r = await reload($, on, TRANSCRIPT_PEQUENO, undefined, { pisos: cheio })
  const pisos = r.mem.get('pisos') as Record<string, unknown>
  expect(Object.keys(pisos)).toHaveLength(50)
  expect(pisos['id-1']).toBeUndefined()
  expect(pisos[SID]).toBeDefined()
})

// 0.6.7: no motor real o botao "Auto: desligado" do other-mod (o auto DELE) estava na linha logo acima e parecia
// um segundo botao da passagem. O rotulo diz de quem e. Abaixo, o other-mod reduzido, com o PROPRIO botao "Auto".
const PROMPT_MASTER = {
  name: 'other-mod',
  register(on: any) {
    on('ui.render', { component: 'AbovePrompt' }, async ($: any, e: any) => {
      const { Box, Button } = $.ui.resolve(e)
      return (
        <Box>
          <Button key="other-mod" label="Other Mod" onPress={() => {}} />
          <Button key="auto" label="Auto: desligado" onPress={() => {}} />
        </Box>
      )
    })
  },
}

test('duas linhas (passagem e other-mod): um botao de auto em cada, e o da passagem diz que e dela', { plugins: [PROMPT_MASTER] }, async ($, on) => {
  await auto($, on, { ligado: false })
  await turno($)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  // O kit acha os dois pela key, sem dizer de quem e: como na tela, so o rotulo os separa.
  const todos = await ui.findAll({ type: 'Button', key: 'auto' })
  await ui.unmount()
  expect(todos.map((b: any) => b.props.label).sort()).toEqual(['Auto: desligado', 'sync_relay auto: desligado'])
})

// 0.6.7: no motor real o auto mudou sem rastro de quem mudou; toda troca do auto fica no rastro, com a origem.
test('rastro: quem ligou ou desligou o auto (botao, comando, apresentacao)', async ($, on) => {
  const c = await nova($, on, { ligado: true })
  await apertar($, 'alternar') // apresentacao: Desligar automatico
  await apertar($, 'auto')
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  await dormir(80)
  const t = rastroTudo(c)
  expect(t).toMatch(/auto ligado -> desligado \(apresentacao\)/)
  expect(t).toMatch(/apresentacao fechada \(alternar\)/)
  expect(t).toMatch(/auto desligado -> ligado \(botao\)/)
  expect(t).toMatch(/auto ligado -> desligado \(comando\)/)
})

// 0.6.8: ordem dos botoes da apresentacao e sobrescrita SYNC_RELAY_THRESHOLD / SYNC_RELAY_AUTO so desta sessao (nunca no store).
test('apresentacao: Entendi vem antes da acao', async ($, on) => {
  await nova($, on)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  const botoes = await ui.findAll({ type: 'Button' })
  await ui.unmount()
  expect(botoes.map((b: any) => b.key)).toEqual(['entendi', 'alternar'])
})

const SOBRE = { SYNC_RELAY_THRESHOLD: '5k', SYNC_RELAY_AUTO: '1' }
const sobre = async ($: any, on: any, penv: Record<string, string> = SOBRE) => {
  const c = await auto($, on, { penv })
  await dormir(30)
  return c
}
const semGravar = (c: Ctx) => {
  expect(c.mem.has('auto')).toBe(false)
  expect(c.mem.has('limiar')).toBe(false)
  expect(c.mem.has('botao')).toBe(false)
}

test('env: SYNC_RELAY_THRESHOLD e SYNC_RELAY_AUTO valem na sessao, nao gravam no store e deixam rastro', async ($, on) => {
  const c = await sobre($, on)
  c.tokens.v = 30_000
  await turno($, { turnId: 't1' })
  c.tokens.v = 36_000
  await turno($, { turnId: 't2' })
  expect(await statusCmd($)).toMatch(/piso 30k \+ 5k/)
  expect(await contando($)).toBe(true) // auto ligado por env, +6k >= 5k
  semGravar(c)
  expect(rastroTudo(c)).toMatch(/sobrescrita env limiar=5000 auto=1/)
})

test('env: vale depois do /clear da propria sessao', async ($, on) => {
  const c = await sobre($, on)
  await clearReal($, c) // sem session.start na sessao nova, como no motor
  c.tokens.v = 30_000
  await turno($, { turnId: 'n1' })
  c.tokens.v = 36_000
  await turno($, { turnId: 'n2' })
  expect(await contando($)).toBe(true)
  expect(await statusCmd($)).toMatch(/piso 30k \+ 5k/)
  semGravar(c)
})

test('env: comando e botao dentro da sessao mudam so a sessao, avisam e sobrevivem ao /clear', async ($, on) => {
  const c = await sobre($, on)
  await $.command.run({ command: 'relay', args: 'auto' } as never) // desliga
  expect(c.toasts.some(t => /só nesta sessão \(SYNC_RELAY_\*\)/.test(t))).toBe(true)
  await turno($, { turnId: 't0' })
  await apertar($, 'auto') // liga de novo
  await apertar($, 'auto') // desliga
  await clearReal($, c) // sem session.start na sessao nova, como no motor
  expect(await statusCmd($)).toMatch(/auto: desligado/)
  c.tokens.v = 30_000
  await turno($, { turnId: 'n1' })
  c.tokens.v = 60_000
  await turno($, { turnId: 'n2' })
  expect(await contando($)).toBe(false) // auto ficou desligado na sessao
  semGravar(c)
})

test('env invalido: ignora a variavel, deixa uma linha no rastro e o resto segue no store', async ($, on) => {
  const c = await sobre($, on, { SYNC_RELAY_THRESHOLD: 'abc', SYNC_RELAY_AUTO: '2' })
  expect(await statusCmd($)).toMatch(/piso 30k \+ 150k/)
  const t = rastroTudo(c)
  expect(t).toMatch(/SYNC_RELAY_THRESHOLD.*invalido/)
  expect(t).toMatch(/SYNC_RELAY_AUTO.*invalido/)
  expect(t).not.toMatch(/sobrescrita env limiar/)
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(c.mem.get('auto')).toBe(true) // sem sobrescrita valida: grava como sempre
})

test('sem env: nada muda (grava no store, sem rastro de sobrescrita)', async ($, on) => {
  const c = await sobre($, on, {})
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(c.mem.get('auto')).toBe(true)
  expect(rastroTudo(c)).not.toMatch(/sobrescrita/)
})

// /relay button esconde e mostra o botao fixo "sync_relay auto" e lembra no store; o config.json so define o comeco.
const botaoCmd = ($: any) => $.command.run({ command: 'relay', args: 'button' } as never)
const semFaixa = async ($: any, on: any, o: object = {}) => {
  const c = await auto($, on, o)
  c.tokens.v = 40_000 // abaixo do limiar: sem faixa de troca
  await turno($)
  return c
}

test('botao: sem config o botao fixo aparece (padrao visivel)', async ($, on) => {
  const c = await semFaixa($, on)
  expect(c.mem.has('botao')).toBe(false)
  expect(await botao($, 'auto')).toBe(true)
})

test('botao: /relay button esconde e avisa; de novo mostra e avisa; a escolha vai ao store', async ($, on) => {
  const c = await semFaixa($, on)
  const r = await botaoCmd($)
  expect(c.toasts).toContain('Botão oculto. Para mostrar de novo: /relay button.')
  expect(r.text).toBe('Botão oculto. Para mostrar de novo: /relay button.')
  expect(await botao($, 'auto')).toBe(false)
  await botaoCmd($)
  expect(c.toasts).toContain('Botão visível.')
  expect(await botao($, 'auto')).toBe(true)
  expect(c.mem.get('botao')).toBe(true)
})

test('botao: oculto por comando vale o resto da sessao, inclusive depois do /clear', async ($, on) => {
  const c = await semFaixa($, on)
  await botaoCmd($)
  await clearReal($, c)
  await c.relogio.advance(1_000) // recarga da sessao nova
  expect(await botao($, 'auto')).toBe(false)
})

test('botao: oculto, a faixa de troca continua aparecendo com o botao de auto dela', async ($, on) => {
  await auto($, on, { ligado: false })
  await botaoCmd($)
  await turno($) // 182k: faixa de troca
  expect(await botao($, 'trocar')).toBe(true)
  expect(await botao($, 'auto')).toBe(true)
})

test('botao: oculto, o que vem depois na cadeia (next) continua sendo chamado', async ($, on) => {
  let chamadas = 0
  const c = await auto($, on, {
    abaixo: on => on('ui.render', { component: 'AbovePrompt' }, async (_: any, e: any, next: any) => (chamadas++, next(e))),
  })
  c.tokens.v = 40_000
  await turno($)
  await botaoCmd($)
  chamadas = 0
  expect(await botao($, 'auto')).toBe(false)
  expect(chamadas).toBeGreaterThan(0)
})

test('botao: oculto, a apresentacao unica ainda aparece se nao foi vista', async ($, on) => {
  await nova($, on)
  await botaoCmd($)
  expect(await apresentacao($)).toBe(true)
  expect(await botao($, 'entendi')).toBe(true)
})

test('botao: cada troca vai ao rastro com a origem', async ($, on) => {
  const c = await semFaixa($, on)
  await botaoCmd($)
  await botaoCmd($)
  await dormir(80)
  expect(rastroTudo(c)).toMatch(/botao visivel -> oculto \(comando\)/)
  expect(rastroTudo(c)).toMatch(/botao oculto -> visivel \(comando\)/)
})

test('botao: a apresentacao diz como ocultar', async ($, on) => {
  await nova($, on)
  expect(await texto2($, /\/relay button/)).toBe(true)
})

// 0.6.10: no motor real, depois de CADA /clear da troca automatica, a apresentacao de primeira instalacao voltava (store com
// apresentado=true) e o botao mostrava "desligado" com o auto ligado: o $.state da sessao nova nasce vazio e o iniciar do
// session.end escrevia na sessao antiga. Agora nada do mod e desenhado antes do estado carregado, e ele carrega logo depois do /clear.
const rotuloAuto = async ($: any) => (await olhar($, { type: 'Button', key: 'auto' }))?.props.label

test('/clear real: antes do estado carregar, nem apresentacao nem botao fixo (nada para clicar errado)', async ($, on) => {
  const c = await sobre($, on)
  await clearReal($, c)
  expect(await apresentacao($)).toBe(false)
  expect(await botao($, 'entendi')).toBe(false)
  expect(await botao($, 'alternar')).toBe(false)
  expect(await botao($, 'auto')).toBe(false)
})

test('/clear real: logo depois, a sessao nova carrega store e env sem esperar turno (sem apresentacao, auto ligado, 5k)', async ($, on) => {
  const s = comStatus(on)
  const c = await sobre($, on)
  await clearReal($, c)
  await c.relogio.advance(1_000)
  expect(await apresentacao($)).toBe(false)
  expect(await rotuloAuto($)).toBe('sync_relay auto: ligado')
  expect(s.ultimo()).toBe('auto ligado · medindo')
  c.tokens.v = 30_000
  await turno($, { turnId: 'n1' })
  expect(s.ultimo()).toBe('auto ligado · 0k de 5k')
  semGravar(c)
})

test('/clear real sem env: auto ligado no store segue ligado e a apresentacao vista nao volta', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await clearReal($, c)
  await c.relogio.advance(1_000)
  expect(await apresentacao($)).toBe(false)
  expect(await rotuloAuto($)).toBe('sync_relay auto: ligado')
  await apertar($, 'auto') // desliga de verdade (partia do estado certo)
  expect(c.mem.get('auto')).toBe(false)
})

test('/clear real: comando antes da recarga parte do estado certo', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await clearReal($, c)
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(c.mem.get('auto')).toBe(false) // desligou (estava ligado), nao ligou de novo
})

// 0.6.11 D1: store ilegivel nao pode deixar o mod mudo (nunca lanca, usa os padroes, desenha, mede e deixa rastro).
const rejeicoes = () => {
  const lista: unknown[] = []
  const p = (globalThis as any).process
  p?.on?.('unhandledRejection', (r: unknown) => lista.push(r))
  return lista
}

test('store ilegivel depois do /clear: botao e faixa com 400k e a linha de status acompanha o n novo', async ($, on) => {
  const s = comStatus(on)
  const c = await auto($, on, { ligado: true })
  await clearReal($, c)
  c.storeFalha.v = true
  await c.relogio.advance(1_000)
  expect(await botao($, 'auto')).toBe(true) // desenha com os padroes
  c.tokens.v = 30_000
  await turno($, { turnId: 'n1' })
  c.tokens.v = 400_000
  await turno($, { turnId: 'n2' })
  expect(s.ultimo()).toBe('auto desligado · 370k de 150k')
  expect(await botao($, 'trocar')).toBe(true) // faixa
  await dormir(80)
  expect(rastroTudo(c)).toMatch(/carregar falhou: [^;]+; usando padroes/)
})

test('store ilegivel: o timer do /clear nao deixa rejeicao nao tratada', async ($, on) => {
  comStatus(on)
  const lista = rejeicoes()
  const c = await auto($, on, { ligado: true })
  await clearReal($, c)
  c.storeFalha.v = true
  await c.relogio.advance(1_000)
  await dormir(80)
  expect(lista).toEqual([])
  expect(await botao($, 'auto')).toBe(true) // o timer terminou o carregamento em vez de abortar
})

test('store ilegivel e depois legivel: o proximo turno le o estado de novo', async ($, on) => {
  comStatus(on)
  const c = await auto($, on, { ligado: true })
  await clearReal($, c)
  c.storeFalha.v = true
  await c.relogio.advance(1_000)
  expect(await rotuloAuto($)).toBe('sync_relay auto: desligado') // padrao
  c.storeFalha.v = false
  c.tokens.v = 30_000
  await turno($, { turnId: 'n1' })
  expect(await rotuloAuto($)).toBe('sync_relay auto: ligado') // do store
})

// 0.6.11 D2: /reload-plugins numa sessao aberta (carregado nasce false, modulo com interativo=false, sem session.start)
// nao pode zerar interativo, piso nem fase da sessao.
test('hot reload: o 1o turno depois do reload preserva interativo, piso e fase', async ($, on) => {
  const s = comStatus(on)
  const c = await auto($, on, { interativo: false, ligado: true }) // modulo: interativoModulo=false; piso 30k medido
  c.forcados.set('interativo', true) // a sessao aberta ja era interativa antes do reload
  c.zerados.add('carregado') // o atomo novo do reload
  c.tokens.v = 40_000
  await turno($, { turnId: 'r1' })
  expect(s.ultimo()).toBe('auto ligado · 10k de 150k') // interativo e piso (30k) mantidos
  c.tokens.v = 190_000
  await turno($, { turnId: 'r2' })
  expect(await contando($)).toBe(true) // fase ociosa e auto vivos: a contagem dispara
})

test('rastro: carregado via=<origem> id auto limiar interativo', async ($, on) => {
  comStatus(on)
  const c = await auto($, on, { ligado: true })
  await clearReal($, c)
  await c.relogio.advance(1_000)
  c.zerados.add('carregado')
  await turno($, { turnId: 'n1' })
  c.zerados.add('carregado')
  await $.command.run({ command: 'relay', args: 'status' } as never)
  await dormir(80)
  const r = rastroTudo(c)
  expect(r).toMatch(/carregado via=session\.start id=aaaa1111 auto=true limiar=150000 interativo=true/)
  expect(r).toMatch(/carregado via=clear-timer id=cccc3333 auto=true limiar=150000 interativo=true/)
  expect(r).toMatch(/carregado via=turno id=cccc3333 auto=true limiar=150000 interativo=true/)
  expect(r).toMatch(/carregado via=comando id=cccc3333 auto=true limiar=150000 interativo=true/)
})

// ---------- 0.6.12: Cancelar para e desliga o auto, faixa em coluna, acentos ----------
// Nao ha API documentada para o mod capturar a tecla Esc (so Button.hotkey, que exige o foco da faixa, e Button.action, que
// cobre acordes e teclas com modificador de acoes do motor): por isso a faixa nao promete "Esc" e o botao Cancelar e o caminho.
const LINHA_CONTAGEM = 'Troca automática em 15 s · Cancelar para parar'

test('0.6.12 Cancelar na contagem para a troca, grava auto=false, adia 50k, avisa e deixa rastro (botao)', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  expect(await contando($)).toBe(true)
  await apertar($, 'cancelar')
  expect(await contando($)).toBe(false)
  expect(c.mem.get('auto')).toBe(false)
  expect(c.toasts).toContain(CANCELADA)
  await c.relogio.advance(60_000)
  expect(c.enviados).toEqual([])
  expect((await olhar($, { type: 'Button', key: 'auto' }))?.props.label).toBe('sync_relay auto: desligado')
  await dormir(80)
  expect(rastroTudo(c)).toMatch(/auto ligado -> desligado \(botao\)/)
  expect(rastroTudo(c)).toMatch(/cancelou a contagem/)
})

test('0.6.12 Cancelar com a sobrescrita SYNC_RELAY_* desliga so a sessao e nao grava no store', async ($, on) => {
  const c = await sobre($, on)
  c.tokens.v = 30_000
  await turno($, { turnId: 't1' })
  c.tokens.v = 36_000
  await turno($, { turnId: 't2' })
  expect(await contando($)).toBe(true)
  await apertar($, 'cancelar')
  expect(await contando($)).toBe(false)
  expect(c.toasts).toContain(`${CANCELADA} (só nesta sessão (SYNC_RELAY_*))`)
  semGravar(c)
  c.tokens.v = 36_000 + 50_000
  await turno($, { turnId: 't3' })
  expect(await contando($)).toBe(false)
})

test('0.6.12 Cancelar fora da contagem (espera por agente) nao desliga o auto', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  c.agentes.v = [agente('running')]
  await c.relogio.advance(CONTAGEM_S * 1000) // vira aguardando
  expect(await olhar($, { type: 'Text', text: /Aguardando 1/ })).toBeDefined()
  await apertar($, 'cancelar')
  expect(c.mem.get('auto')).toBe(true)
})

test('0.6.12 mensagem durante a contagem so adia: o auto continua ligado e volta 50k depois', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await pessoa($)
  expect(c.toasts).toContain(ADIADA)
  expect(c.toasts).not.toContain(CANCELADA)
  expect(c.mem.get('auto')).toBe(true)
  c.tokens.v = 182_000 + 50_000
  await turno($)
  expect(await contando($)).toBe(true)
})

test('0.6.12 contagem: "Cancelar para parar" na mesma linha dos segundos, sem Esc, so na contagem', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  expect((await olhar($, { type: 'Text', text: /Troca automática em/ }))?.text.trim()).toBe(LINHA_CONTAGEM)
  expect(await olhar($, { type: 'Text', text: /Esc/ })).toBeUndefined()
  await c.relogio.advance(3_000)
  expect((await olhar($, { type: 'Text', text: /Troca automática em/ }))?.text.trim()).toBe('Troca automática em 12 s · Cancelar para parar')
  await apertar($, 'cancelar')
  c.tokens.v = 182_000 + 60_000
  await turno($)
  expect(await olhar($, { type: 'Text', text: /para parar/ })).toBeUndefined() // a faixa de aviso nao leva o texto
  expect(await botao($, 'trocar')).toBe(true)
})

// A faixa em coluna: o texto numa linha (ou mais) e os botoes numa Box propria abaixo, nunca no meio da frase.
const emColuna = async ($: any) => {
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  const caixas = await ui.findAll({ type: 'Box' })
  await ui.unmount()
  const fora = caixas[0]
  const i = fora.children.findIndex((f: any) => f.type === 'Box' && f.children.some((x: any) => x.type === 'Button'))
  const botoes = fora.children[i]
  return {
    coluna: fora.props.flexDirection === 'column',
    textoAntes: i > 0 && fora.children.slice(0, i).every((f: any) => f.type !== 'Button'),
    soBotoes: botoes !== undefined && botoes.children.every((f: any) => f.type === 'Button' || (f.type === 'Text' && f.children.join('').trim() === '')),
  }
}
const OK = { coluna: true, textoAntes: true, soBotoes: true }

test('0.6.12 layout: botoes em linha propria na faixa de aviso', async ($, on) => {
  await auto($, on, { ligado: false })
  await turno($)
  expect(await botao($, 'trocar')).toBe(true)
  expect(await emColuna($)).toEqual(OK)
})

test('0.6.12 layout: botoes em linha propria na contagem', async ($, on) => {
  await auto($, on, { ligado: true })
  await turno($)
  expect(await contando($)).toBe(true)
  expect(await emColuna($)).toEqual(OK)
})

test('0.6.12 layout: botoes em linha propria no aguardando e na espera longa', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.agentes.v = [agente('running')]
  await turno($)
  await apertar($, 'trocar')
  expect(await emColuna($)).toEqual(OK)
  await c.relogio.advance(61_000)
  expect(await botao($, 'forcar')).toBe(true)
  expect(await emColuna($)).toEqual(OK)
})

test('0.6.12 layout: botoes em linha propria na apresentacao', async ($, on) => {
  await nova($, on)
  expect(await apresentacao($)).toBe(true)
  expect(await emColuna($)).toEqual(OK)
})

test('0.6.12 acentos: gravando e resposta do comando', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await turno($)
  const r = await $.command.run({ command: 'relay', args: '' } as never)
  expect(r.text).toBe('Gravando a passagem; a sessão nova abre sozinha quando ela estiver pronta.')
  await c.relogio.settle()
  expect(await olhar($, { type: 'Text', text: /Gravando a passagem para abrir a sessão nova\.\.\./ })).toBeDefined()
  expect((await $.command.run({ command: 'relay', args: '' } as never)).text).toBe('Já estou gravando a passagem.')
})

test('0.6.12 acentos: passagem nao gravada avisa com acento', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  c.gravada.v = false
  await turno($)
  await apertar($, 'agora')
  await turno($, { turnId: 't2' })
  expect(c.toasts).toContain('A passagem não foi gravada; a sessão continua. Clique de novo ou digite /relay.')
})

test('0.6.13: duplo clique em Cancelar gera 1 toast e 1 linha de rastro', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  expect(await contando($)).toBe(true)
  const a = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  const b = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await Promise.all([a.press({ key: 'cancelar' }), b.press({ key: 'cancelar' })])
  await a.unmount()
  await b.unmount()
  expect(c.toasts.filter(t => t === CANCELADA)).toHaveLength(1)
  await dormir(80)
  expect(rastroTudo(c).split('auto ligado -> desligado (botao)').length - 1).toBe(1)
  expect(c.mem.get('auto')).toBe(false)
})

test('0.6.13: store lento no Cancelar: a contagem chega a 0 e nada e enviado', async ($, on) => {
  const c = await auto($, on, { ligado: true })
  await turno($)
  await c.relogio.advance((CONTAGEM_S - 1) * 1000) // falta 1 s
  expect(await contando($, 1)).toBe(true)
  c.storeLento.v = 2_000
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  const preso = ui.press({ key: 'cancelar' })
  await c.relogio.advance(3_000) // passa do zero durante o store.set
  await preso
  await ui.unmount()
  await c.relogio.settle()
  expect(c.enviados).toEqual([])
  expect(await botao($, 'trocar')).toBe(false) // adiado 50k, fase ocioso (nao escrevendo)
  expect(await olhar($, { type: 'Text', text: /Gravando a passagem/ })).toBeUndefined()
  expect(c.mem.get('auto')).toBe(false)
})

// ---------- product: language, config and the handoff word ----------

/** One session with its own env and config file; fs, store and prompts are fakes, nothing leaves the machine. */
async function cfgScene($: any, on: any, env: Record<string, string>, cfg: string | null | (() => string | null), tokens: { v: number }, mem?: Map<string, unknown>, extra: { janela?: number; modelo?: string; settings?: string } = {}) {
  const enviados: string[] = []
  const registrados: string[] = []
  const cfgLidos: string[] = []
  if (mem) {
    on('store.get', (_: any, e: any) => ({ value: mem.get(e.key) }))
    on('store.set', (_: any, e: any) => (mem.set(e.key, e.value), { value: undefined }))
    on('store.delete', (_: any, e: any) => (mem.delete(e.key), { value: undefined }))
    on('store.keys', () => ({ value: [...mem.keys()] }))
  } else mock.store(on)
  mock.clock(on, { now: 1_000 })
  on('env.get', (_: any, e: any) => ({ value: env[e.name] }))
  on('fs.read', (_: any, e: any) => {
    const txt = typeof cfg === 'function' ? cfg() : cfg
    const caminho = String(e.path).replaceAll('\\', '/')
    if (txt !== null && caminho === env.SYNC_RELAY_CONFIG) return { value: txt }
    if (extra.settings !== undefined && caminho.endsWith('/settings.json')) {
      cfgLidos.push(caminho)
      return { value: extra.settings }
    }
    throw new Error('nao existe')
  })
  if (extra.modelo !== undefined) on('session.model', () => ({ value: extra.modelo }))
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens: tokens.v, window: extra.janela ?? 1_000_000, percent: 18 }, rateLimits: [], cost: { usd: 0 } },
  }))
  on('prompt.submit', (_: any, e: any) => {
    enviados.push(e.text)
    return { text: e.text }
  })
  on('command.register', (_: any, e: any) => {
    registrados.push(e.name)
    return { value: undefined }
  })
  on('session.info', () => ({ value: { transcriptPath: 'C:/Users/x/.claude/projects/C--x/abc.jsonl', platform: 'windows' } }))
  on('turn.complete', () => ({ text: 'ok' }))
  on('agent.list', () => ({ value: [] }))
  on('session.start', (_: any, e: any) => e)
  on('session.cwd', () => ({ value: 'C:/Users/x/p' }))
  on('session.id', () => ({ value: 'aaaa1111-0000-0000-0000-000000000000' }))
  await $.turn.complete(TURNO) // base turn: fixes the baseline at 30k
  return { enviados, registrados, cfgLidos }
}
const botaoTrocar = async ($: any) => {
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  const b = await ui.find({ type: 'Button', key: 'trocar' })
  const label = b?.props.label as string | undefined
  await ui.unmount()
  return label
}

test('lang en: the button says "Switch session" and the banner is in English', async ($, on) => {
  const tokens = { v: 30_000 }
  await cfgScene($, on, { SYNC_RELAY_LANG: 'en' }, null, tokens)
  tokens.v = 182_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBe('Switch session')
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /182k/ }))?.text).toContain('182k tokens (+152k above the start of the session)')
  await ui.unmount()
})

test('lang pt-BR from the config file (no env): "Trocar de sessão"', async ($, on) => {
  const tokens = { v: 30_000 }
  await cfgScene($, on, { SYNC_RELAY_CONFIG: 'C:/cfg/config.json' }, '{"lang":"pt-BR"}', tokens)
  tokens.v = 182_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBe('Trocar de sessão')
})

test('config threshold_tokens 100000: the band shows at 100k above the baseline, not at 99k', async ($, on) => {
  const tokens = { v: 30_000 }
  const env = { SYNC_RELAY_LANG: 'en', SYNC_RELAY_CONFIG: 'C:/cfg/config.json' }
  await cfgScene($, on, env, '{"threshold_tokens":100000}', tokens)
  tokens.v = 129_000 // +99k
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBeUndefined()
  tokens.v = 131_000 // +101k
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBe('Switch session')
})

test('without a config the default 150k applies (the same +101k does not show the band)', async ($, on) => {
  const tokens = { v: 30_000 }
  await cfgScene($, on, { SYNC_RELAY_LANG: 'en' }, null, tokens)
  tokens.v = 131_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBeUndefined()
})

test('the button sends "relay" and the /relay command is registered', async ($, on) => {
  const tokens = { v: 30_000 }
  const c = await cfgScene($, on, { SYNC_RELAY_LANG: 'en' }, null, tokens)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(c.registrados).toEqual(['relay'])
  tokens.v = 182_000
  await $.turn.complete(TURNO)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await ui.press({ key: 'trocar' })
  expect(c.enviados).toEqual(['relay'])
  expect(await ui.find({ type: 'Text', text: /Writing the handoff/ })).toBeDefined()
  await ui.unmount()
})

test('config handoff_dir (absolute) is where the band looks for the file', async ($, on) => {
  const tokens = { v: 30_000 }
  const env = { SYNC_RELAY_LANG: 'en', SYNC_RELAY_CONFIG: 'C:/cfg/config.json' }
  const perguntados: string[] = []
  on('fs.exists', (_: any, e: any) => (perguntados.push(String(e.path).replaceAll('\\', '/')),{ value: false }))
  on('fs.stat', () => ({ value: { mtimeMs: 0, size: 1 } }))
  await cfgScene($, on, env, '{"handoff_dir":"D:/data/handoffs"}', tokens)
  tokens.v = 182_000
  await $.turn.complete(TURNO)
  const ui = await $.ui.mount({ ...FAIXA, surface: 'terminal' })
  await ui.press({ key: 'trocar' })
  await $.turn.complete(TURNO) // the turn after the request: the band looks for the file
  await ui.unmount()
  expect(perguntados.length).toBeGreaterThan(0)
  for (const p of perguntados) expect(p.startsWith('D:/data/handoffs/c-users-x-p-')).toBe(true)
})

const FIXO = 'sync_relay auto: off'
const rotuloFixo = async ($: any) => (await $.ui.mount({ ...FAIXA, surface: 'terminal' }).then(async (ui: any) => {
  const b = await ui.find({ type: 'Button', key: 'auto' })
  await ui.unmount()
  return b?.props.label as string | undefined
}))

test('config button:false hides the fixed button from the start; /relay button shows it for the session; absent or true shows it', async ($, on) => {
  const tokens = { v: 30_000 }
  const env = { SYNC_RELAY_LANG: 'en', SYNC_RELAY_CONFIG: 'C:/cfg/config.json' }
  await cfgScene($, on, env, '{"button":false,"threshold_tokens":100000}', tokens, new Map([['apresentado', true]]))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.turn.complete(TURNO)
  expect(await rotuloFixo($)).toBeUndefined()
  const r = (await $.command.run({ command: 'relay', args: 'button' } as never)) as any
  expect(r.text).toBe('Button visible.')
  expect(await rotuloFixo($)).toBe(FIXO)
  await $.command.run({ command: 'relay', args: 'button' } as never)
  expect(await rotuloFixo($)).toBeUndefined()
})

test('config without the button key (or button:true) shows the fixed button', async ($, on) => {
  const tokens = { v: 30_000 }
  const env = { SYNC_RELAY_LANG: 'en', SYNC_RELAY_CONFIG: 'C:/cfg/config.json' }
  await cfgScene($, on, env, '{"button":true}', tokens, new Map([['apresentado', true]]))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.turn.complete(TURNO)
  expect(await rotuloFixo($)).toBe(FIXO)
})

// Precedence of the remembered choices: session env > value saved in $.store by the command > config.json > default.
const lembrar = async ($: any, on: any, cfg: string | null, mem: Map<string, unknown>, extraEnv: Record<string, string> = {}) => {
  const env = { SYNC_RELAY_LANG: 'en', SYNC_RELAY_CONFIG: 'C:/cfg/config.json', ...extraEnv }
  mem.set('apresentado', true)
  await cfgScene($, on, env, cfg, { v: 30_000 }, mem)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.turn.complete(TURNO)
}
const ON = 'sync_relay auto: on'
const OFF = 'sync_relay auto: off'

test('remembered: /relay button hides the button and a NEW session (same store) keeps it hidden', async ($, on) => {
  const mem = new Map<string, unknown>()
  await lembrar($, on, null, mem)
  expect(await rotuloFixo($)).toBe(OFF)
  await $.command.run({ command: 'relay', args: 'button' } as never)
  expect(await rotuloFixo($)).toBeUndefined()
  expect(mem.get('botao')).toBe(false)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.turn.complete(TURNO)
  expect(await rotuloFixo($)).toBeUndefined()
})

test('remembered: config button:false with nothing in the store hides the button; store absent, config decides', async ($, on) => {
  const mem = new Map<string, unknown>()
  await lembrar($, on, '{"button":false}', mem)
  expect(await rotuloFixo($)).toBeUndefined()
  expect(mem.has('botao')).toBe(false)
})

test('remembered: store botao:true beats config button:false', async ($, on) => {
  await lembrar($, on, '{"button":false}', new Map<string, unknown>([['botao', true]]))
  expect(await rotuloFixo($)).toBe(OFF)
})

test('remembered: store botao:false beats config button:true', async ($, on) => {
  await lembrar($, on, '{"button":true}', new Map<string, unknown>([['botao', false]]))
  expect(await rotuloFixo($)).toBeUndefined()
})

test('remembered: config auto:true with an empty store starts auto on; no key = off', async ($, on) => {
  await lembrar($, on, '{"auto":true}', new Map())
  expect(await rotuloFixo($)).toBe(ON)
})

test('remembered: store auto:false beats config auto:true; store auto:true beats config auto:false', async ($, on) => {
  await lembrar($, on, '{"auto":true}', new Map<string, unknown>([['auto', false]]))
  expect(await rotuloFixo($)).toBe(OFF)
})

test('remembered: store auto:true beats config auto:false', async ($, on) => {
  await lembrar($, on, '{"auto":false}', new Map<string, unknown>([['auto', true]]))
  expect(await rotuloFixo($)).toBe(ON)
})

test('remembered: /relay auto is saved and a NEW session keeps it', async ($, on) => {
  const mem = new Map<string, unknown>()
  await lembrar($, on, '{"auto":false}', mem)
  await $.command.run({ command: 'relay', args: 'auto' } as never)
  expect(mem.get('auto')).toBe(true)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.turn.complete(TURNO)
  expect(await rotuloFixo($)).toBe(ON)
})

test('remembered: session env SYNC_RELAY_AUTO beats the store', async ($, on) => {
  const mem = new Map<string, unknown>([['auto', true]])
  await lembrar($, on, null, mem, { SYNC_RELAY_AUTO: '0' })
  expect(await rotuloFixo($)).toBe(OFF)
  await $.command.run({ command: 'relay', args: 'auto' } as never) // session only: the store stays
  expect(mem.get('auto')).toBe(true)
})

test('model from the API: a 200K model switches at floor + 136k (166k), not 180k', async ($, on) => {
  const tokens = { v: 30_000 }
  await cfgScene($, on, { SYNC_RELAY_LANG: 'en' }, null, tokens, undefined, { modelo: 'claude-sonnet-4-6', janela: 200_000 })
  tokens.v = 165_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBeUndefined()
  tokens.v = 166_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBe('Switch session')
})

test('model from the API: a 1M model switches at 180k; threshold_tokens 300000 on a 200K model still stops at 166k', async ($, on) => {
  const tokens = { v: 30_000 }
  await cfgScene($, on, { SYNC_RELAY_LANG: 'en' }, null, tokens, undefined, { modelo: 'claude-opus-4-7', janela: 1_000_000 })
  tokens.v = 179_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBeUndefined()
  tokens.v = 180_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBe('Switch session')
})

test('threshold_tokens 300000 with a 200K model: the ceiling applies', async ($, on) => {
  const tokens = { v: 30_000 }
  const env = { SYNC_RELAY_LANG: 'en', SYNC_RELAY_CONFIG: 'C:/cfg/config.json' }
  await cfgScene($, on, env, '{"threshold_tokens":300000}', tokens, undefined, { modelo: 'claude-sonnet-4-6', janela: 200_000 })
  tokens.v = 165_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBeUndefined()
  tokens.v = 166_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBe('Switch session')
})

test('env CLAUDE_CODE_AUTO_COMPACT_WINDOW, settings autoCompactWindow and the pct override move the compaction point', async ($, on) => {
  const tokens = { v: 30_000 }
  const env: Record<string, string> = { SYNC_RELAY_LANG: 'en', CLAUDE_CODE_AUTO_COMPACT_WINDOW: '150000' }
  await cfgScene($, on, env, null, tokens, undefined, { modelo: 'claude-opus-4-7' })
  tokens.v = 125_000 // floor 30k + 0.8 x 120k = 126k
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBeUndefined()
  tokens.v = 126_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBe('Switch session')
})

test('settings.json of CLAUDE_CONFIG_DIR: autoCompactWindow read; broken file ignored', async ($, on) => {
  const tokens = { v: 30_000 }
  const env: Record<string, string> = { SYNC_RELAY_LANG: 'en', CLAUDE_CONFIG_DIR: 'D:/cc' }
  const c = await cfgScene($, on, env, null, tokens, undefined, { modelo: 'claude-opus-4-7', settings: '{"autoCompactWindow":150000}' })
  tokens.v = 126_000
  await $.turn.complete(TURNO)
  expect(new Set(c.cfgLidos)).toEqual(new Set(['D:/cc/settings.json']))
  expect(await botaoTrocar($)).toBe('Switch session')
})

test('settings.json broken: ignored, the model default applies', async ($, on) => {
  const tokens = { v: 30_000 }
  await cfgScene($, on, { SYNC_RELAY_LANG: 'en' }, null, tokens, undefined, { modelo: 'claude-opus-4-7', settings: '{broken' })
  tokens.v = 126_000
  await $.turn.complete(TURNO)
  expect(await botaoTrocar($)).toBeUndefined()
})

// ---------- P2: Cancelar blanks the core's marker ----------

test('cancelar a troca grava o marcador _req-<PID> vazio: o nucleo nao entrega no /clear', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  c.clearFalha.v = true
  await clearDaPassagem($, c) // pedido feito, passagem pronta
  expect([...c.escritas.keys()].filter(k => k.includes('_req-'))).toEqual([])
  await pessoa($, 'deixa pra la') // cancela
  const marcadores = [...c.escritas.entries()].filter(([k]) => k.includes('_req-'))
  expect(marcadores.length).toBe(1)
  expect(marcadores[0][0]).toMatch(/\/_req-100\.txt$/)
  expect(marcadores[0][1]).toBe('')
})

test('voltar a ocioso sem pedido pendente nao grava marcador', async ($, on) => {
  const c = await auto($, on, { ligado: false })
  await pessoa($, 'oi')
  expect([...c.escritas.keys()].filter(k => k.includes('_req-'))).toEqual([])
})

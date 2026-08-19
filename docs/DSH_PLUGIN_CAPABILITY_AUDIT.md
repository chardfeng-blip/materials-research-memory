# DSH_PLUGIN_CAPABILITY_AUDIT.md

**Audit date:** 2026 (this session)
**Audit target:** the running DeepSeek Harness (DSH) at `$DSH_HOME` (a local DSH install) and its source tree (`<DSH_SOURCE>`).
**Purpose:** establish, from actual inspection, which DSH mechanisms exist for `plugin / skill / hook / memory / extension`, so `materials-research-memory` integrates with reality and never assumes a fake API.

---

## 1. Plugin mechanism (verified)

DSH's plugin system is **Cordis function/class plugins written in TypeScript/JavaScript** (Node), composed declaratively in `cordis.patch.yml` files:

- Function plugin shape: named exports `name`, `inject`, `Config` (Schemastery schema), `apply(ctx, config)`; class plugins are `Service` subclasses (default export).
- Composition: bundle patches (`packages/bundle/base/cordis.patch.yml`, `packages/bundle/web-app/cordis.patch.yml`) insert rows; the user layer is `$DSH_HOME/cordis.patch.yml` (contents are machine-specific — see INSTALLATION.md for the generic example); profile roots under `$DSH_HOME/profiles/web` ship their own `node_modules`.
- Loader: `@deepseek-ai/cordis-plugin-loader` mounts each row as a fiber; `plugin-inventory` exposes the live tree.
- **No Python plugin runtime exists.** A Python-based memory system cannot be a first-class Cordis plugin by itself; it must be a *service* (Python CLI/daemon) wrapped by a thin DSH-side bridge.

## 2. Skill mechanism (verified)

DSH has a real skill system:

- `@deepseek-ai/dsh-skill` (registry), `@deepseek-ai/dsh-skill-filesystem` (provider), `@deepseek-ai/dsh-tool-skill` (model-facing `skill` tool), `@deepseek-ai/dsh-skill-badge`.
- Skills are **markdown files** (`.md`), discovered from workspace roots by `skill-filesystem`; each skill carries a name + description (frontmatter-style metadata) and an instruction body; the model invokes them through the `skill` tool.
- Implications: `materials-research-memory/skills/*.md` can be authored to be **both** our internal skill schema (Purpose / When to use / Inputs / Definitions / Procedure / QA / Common failures / Blocking conditions / Outputs / Provenance requirements) **and** DSH-loadable skills (add DSH-compatible name+description metadata). No app rebuild needed to *load* them from a workspace root.

## 3. Hook mechanism (verified)

- DSH has `packages/hooks/hooks-claude-code` and `packages/hooks/hooks-codex`: wire-protocol bridges that connect the DSH host to external CLI agents (Claude Code / Codex). They are **not** a general per-session "on task start / on task end" hook API for arbitrary third-party plugins.
- No native `on_session_start` / `on_task_end` extension point is exposed to user plugins today. Therefore session-bound behavior must be implemented as a **wrapper**: either (a) a small Cordis host plugin that subscribes to session events and shells out to the Python CLI, or (b) agent-level instruction injection (a DSH skill / workspace instruction that tells the agent to call the CLI at session start and after tasks). Both are provided by this plugin; the interface (`materials-memory ...` CLI) stays identical regardless of which wrapper is used.

## 4. Memory mechanism (verified)

- Session persistence: JSONL session logs (`$DSH_HOME/sessions`), session projections (per-session computed read models: `tokenUsage`, `sessionStats`, `goal`, etc.), SQLite session-query.
- **There is no built-in cross-session long-term scientific memory store.** Sessions are isolated logs; projections are per-session and replay-derived. Nothing remembers a materials project across new sessions unless we build it.
- Conclusion: a durable cross-session memory must be **file-based state we own** (`memory/*` under the plugin directory) with an explicit retrieval layer. This is exactly what `materials-research-memory` implements.

## 5. Extension mechanism (verified)

- `packages/extensions/tool-cordis` + `cordis-host-runner` / `cordis-client-runner`: a dynamic-package runtime that lets the *agent itself* define and mount Cordis plugins at runtime (in a sandboxed VM for host halves). It is for model-written plugins, not a user-facing install path for a persistent Python service.
- `ui-cordis`: browser surfaces for that dynamic toolset.
- Not a suitable host for a long-lived materials memory service.

## 6. Where user-level configuration lives (verified)

- `$DSH_HOME/cordis.patch.yml` — user patch layer over the bundles (currently: `subagent-codex` row only).
- `$DSH_HOME/profiles/web/` — the web profile's own dependency closure (its `node_modules`).
- `$DSH_HOME/.agent-presets/` — per-session agent compositions.
- `$DSH_HOME/settings.yaml`, `$DSH_HOME/storages/` — settings and non-session storage domains.
- **No `$DSH_HOME/plugins/` directory exists yet.** Per project convention we create `$DSH_HOME/plugins/materials-research-memory/` and document wiring it via `$DSH_HOME/cordis.patch.yml` (host-plugin bridge) and/or DSH skill registration.

## 7. Audit verdict

| Capability | Native? | Used by this plugin |
|---|---|---|
| Plugin (Cordis/TS) | Yes | Thin **wrapper bridge** (optional host plugin) — source provided in `dsh/` |
| Skill (markdown) | Yes | `skills/*.md` authored dual-format (our schema + DSH metadata) |
| Hook (session events) | No general API | Implemented as wrapper/service + session hooks via CLI + optional Cordis bridge |
| Memory (cross-session) | No | File-based memory store under `memory/` owned by this plugin |
| Extension (dynamic packages) | Yes | Not used (not a fit for long-lived service) |

**Conclusion:** no native plugin hook exists for arbitrary Python services or for session-start/task-end memory injection. `materials-research-memory` is therefore implemented as a **wrapper/service + session hooks** with a **unified CLI interface** (`materials-memory <verb> ...`), which is exactly the fallback the project specification prescribes. The same interface is consumed by the DSH-side bridge, the DSH skill, and the agent directly, so nothing downstream depends on which wrapper is active.

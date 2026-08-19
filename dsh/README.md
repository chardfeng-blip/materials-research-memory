# DSH integration

DSH has **no native Python plugin runtime and no general session-hook API**
(verified — see `docs/DSH_PLUGIN_CAPABILITY_AUDIT.md`). This plugin therefore
integrates as a **wrapper/service + session hooks** with a single unified
interface (`materials-memory <verb> ...`).

## Layer 1 — DSH skill (works immediately, no rebuild)

`skills/core/materials_research_memory.md` is a DSH-loadable skill (name +
description frontmatter + instruction body). It teaches the agent the
session protocol:

- session start → `materials-memory brief` → read `outputs/PROJECT_BRIEF.md`
- task start → `materials-memory retrieve "<task>"`
- task end → `materials-memory reflect ...` (nine questions, gated auto-commit)

To register: place the plugin directory (or a copy of `skills/core/`) under a
DSH skill root (`dsh-skill-filesystem` scans workspace roots), or load the
skill manually via the `skill` tool. Project-specific skills live in
`profiles/<id>/skills/` and are indexed only for the ACTIVE profile (P0-9).

## Layer 2 — optional Cordis host-plugin bridge

`dsh-session-bridge.ts` is a small Cordis function plugin that shells out to
the Python CLI on `agent/session-start` (regenerate brief) and session close
(refresh skill proposals). Build/install steps are documented in the file
header: add it to the DSH source tree, `pnpm run build:lib:host`, add a row
to `$DSH_HOME/cordis.patch.yml`, restart the host. `expandHome()` normalizes
`~/`, `~`, and `~\` paths so the `--root` used by runCli and the warning
message always agree (P1-10).

## Unified interface (same verbs everywhere)

```
materials-memory init                # create memory layout (idempotent)
materials-memory brief               # PROJECT_BRIEF.md (session start, <=8000 tokens)
materials-memory retrieve "<q>" -k N # top-k memories for a task
materials-memory reflect ...         # MEMORY_UPDATE_PROPOSAL.md (task end)
materials-memory accept-change <change_id> --reviewer human  # claim supersede approval (P0-3)
materials-memory accept-decision <id> --reviewer human       # decision supersede approval
materials-memory propose-skills      # SKILL_PROMOTION_PROPOSAL.md
materials-memory promote-skill ...   # write a real skill (approval path)
materials-memory snapshot --milestone m
materials-memory rollback <dir>      # snapshots inside snapshots/ only
materials-memory status              # shows "project initialized: YES/NO"
materials-memory metrics | test-retrieval
```

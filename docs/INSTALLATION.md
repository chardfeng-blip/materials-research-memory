# INSTALLATION

## Requirements

- Python >= 3.10 with `PyYAML` (and pytest for tests).
- A DSH install at `$DSH_HOME` (e.g. `%USERPROFILE%\.dsh` on Windows).

## 1. Place the plugin

Install to `$DSH_HOME/plugins/materials-research-memory` (replace
`$DSH_HOME` with your DSH install directory):

```powershell
# copy the plugin directory (core/, memory/, skills/, bin/, dsh/, docs/, tests/)
Copy-Item -Path <plugin-source> -Destination "$env:USERPROFILE\.dsh\plugins\materials-research-memory" -Recurse
```

Verify:

```powershell
python "$env:USERPROFILE\.dsh\plugins\materials-research-memory\bin\materials-memory.py" --root "$env:USERPROFILE\.dsh\plugins\materials-research-memory" status
```

## 2. Initialize the memory layout (if not already seeded)

```powershell
python bin\materials-memory.py --root <plugin-root> init   # idempotent; seeds valid empty-state files
```

The distributable ships an UNINITIALIZED project — the shipped `memory/`
skeleton: empty buckets, empty JSONL, `meta.initialized: false`, no fake
records (P0-1). `status` reports `project initialized: NO` until real content
is accepted through reflection/acceptance. The memory layout is
project-profile aware: set `.active_profile` (or pass `--profile <id>`) to
decide which profile's skills are indexed (P0-9).

Other verbs: `brief`, `retrieve "<q>" -k N`, `reflect ...`,
`accept-change <change_id> --reviewer human` (claim supersede approval),
`accept-decision <id> --reviewer human` (decision supersede approval),
`propose-skills`, `promote-skill ...`, `snapshot --milestone m`,
`rollback <dir>` (snapshots inside `snapshots/` only), `status`, `metrics`,
`test-retrieval`.

## 3. Wire the session hooks

DSH has no native hook API (see `DSH_PLUGIN_CAPABILITY_AUDIT.md`), so the
session protocol is wired through the **DSH skill** (works immediately):

1. Register `skills/core/materials_research_memory.md` as a DSH skill (place a
   copy under a `dsh-skill-filesystem` workspace root, or load it via the
   `skill` tool). It instructs the agent to run `brief` at session start,
   `retrieve` before tasks, and `reflect` after tasks.

For true automation, optionally build the Cordis host-plugin bridge
(`dsh/dsh-session-bridge.ts`):

1. Add it as a small function-plugin package in the DSH source checkout.
2. `pnpm run build:lib:host`.
3. Add a row to `$DSH_HOME/cordis.patch.yml`:
   ```yaml
   - id: materials-memory-bridge
     name: '@deepseek-ai/dsh-materials-memory-bridge'
     config:
       pluginRoot: '<DSH_HOME>/plugins/materials-research-memory'
       python: 'python'
   ```
4. Restart the DSH host.

## 4. Regenerate the project brief

```powershell
python bin\materials-memory.py --root <plugin-root> brief
# -> outputs\PROJECT_BRIEF.md (<= 8000 tokens)
```

## 5. Tests

```powershell
python bin\materials-memory.py --root <plugin-root> test-retrieval   # §32 questions
python tests\test_lesson_lifecycle.py ; python tests\test_contradiction.py
python tests\test_snapshot.py ; python tests\test_retrieval.py ; python tests\test_gate.py
```

(pytest also works with a writable `--basetemp`; the built-in `tmp_path`
fixture is unusable under the DSH file sandbox — the test suite uses
sandbox-safe `tests/tmpdir.py` instead.)

## Safety notes

- The plugin never auto-modifies long-term scientific truth: accepted
  conclusions require canonical source + HIGH confidence + no conflict.
- All raw research data under the project (`<PROJECT_ROOT>`) is
  READ-ONLY to this plugin; it only writes its own `memory/`, `skills/`,
  `reflections/`, `snapshots/`, `outputs/` directories.

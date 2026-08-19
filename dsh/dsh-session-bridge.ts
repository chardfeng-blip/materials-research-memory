/**
 * dsh-session-bridge — optional DSH (Cordis) host plugin that shells out to
 * the materials-research-memory Python CLI at session boundaries.
 *
 * This is the "wrapper/service + session hooks" integration (DSH has no
 * native hook API for arbitrary services; see DSH_PLUGIN_CAPABILITY_AUDIT.md).
 * The interface is identical to what the DSH skill / the agent itself uses:
 *   python <plugin>/bin/materials-memory.py --root <plugin> <verb>
 *
 * It is OPTIONAL: the DSH skill `materials_research_memory` already gives the
 * agent the same protocol. Install this bridge for true automation.
 *
 * Build/install (from the DSH source checkout):
 *   1. copy this file into packages/<group>/<pkg>/src/index.ts of a small
 *      function plugin package (name: dsh-materials-memory-bridge),
 *   2. build: pnpm run build:lib:host
 *   3. add a row to $DSH_HOME/cordis.patch.yml:
 *        - id: materials-memory-bridge
 *          name: '@deepseek-ai/dsh-materials-memory-bridge'
 *          config:
 *            pluginRoot: '~/.dsh/plugins/materials-research-memory'
 *            python: 'python'
 *   4. restart the DSH host.
 *
 * P1-10: `expandHome()` normalizes `~/`, `~`, and `~\` so the exact root
 * passed to runCli (`--root`) and any warning message always agree.
 */
import { execFile } from 'node:child_process'
import { homedir } from 'node:os'
import { resolve } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'

export const name = 'materials-memory-bridge'

export interface Config {
  /** materials-research-memory plugin root (default ~/.dsh/plugins/...). */
  pluginRoot?: string
  /** python executable (default 'python'). */
  python?: string
  /** emit brief/proposal file paths as session logs. */
  verbose?: boolean
}

/** Expand a leading `~`, `~/`, or `~\` to the user's home directory (P1-10). */
export function expandHome(p: string): string {
  if (!p) return p
  if (p === '~') return homedir()
  if (p.startsWith('~/') || p.startsWith('~\\')) {
    return resolve(homedir(), p.slice(2))
  }
  return p
}

/** The single normalized plugin root used by runCli AND by any message. */
export function pluginRootOf(config: Config): string {
  return expandHome(config.pluginRoot ?? '~/.dsh/plugins/materials-research-memory')
}

/** Run one CLI verb; resolves with combined stdout/stderr text. */
function runCli(root: string, cfg: Config, ...args: string[]): Promise<string> {
  return new Promise((resolvePromise, reject) => {
    execFile(
      cfg.python ?? 'python',
      [resolve(root, 'bin', 'materials-memory.py'), '--root', root, ...args],
      { timeout: 120_000, windowsHide: true, env: process.env },
      (error, stdout, stderr) => {
        if (error) reject(new Error(`materials-memory ${args[0]} failed: ${stderr || error.message}`))
        else resolvePromise(stdout)
      },
    )
  })
}

export function apply(ctx: Context, config: Config): void {
  const root = pluginRootOf(config)

  // Session start: regenerate PROJECT_BRIEF.md (spec §12).
  ctx.on('agent/session-start', async () => {
    try {
      const out = await runCli(root, config, 'brief')
      if (config.verbose) ctx.logger.info(out.trim())
    } catch (error) {
      ctx.logger.warn('materials-memory brief failed:', error)
    }
  })

  // Task end: the agent writes reflections via the CLI itself (the skill
  // protocol). This bridge also provides a ready-made reflect trigger so a
  // future explicit hook can call it with a task id.
  ctx.on('session/close', async () => {
    try {
      const out = await runCli(root, config, 'propose-skills')
      if (config.verbose) ctx.logger.info(out.trim())
    } catch (error) {
      ctx.logger.warn('materials-memory propose-skills failed:', error)
    }
  })
}

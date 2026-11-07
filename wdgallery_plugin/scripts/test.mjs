// Runs the main-process tests on Electron's own Node (it has node:sqlite and runs .ts files
// directly), so they test the SQLite the plugin ships with.

import { spawnSync } from 'node:child_process'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import electron from 'electron'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const result = spawnSync(electron, ['--test', '--disable-warning=ExperimentalWarning', join(root, 'src', 'main', 'store.test.mts')], {
  cwd: root,
  stdio: 'inherit',
  env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' }
})
process.exit(result.status ?? 1)

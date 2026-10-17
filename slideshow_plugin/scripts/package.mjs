// Builds the plugin and packs the distributable zip: ../dist/Slideshow-<version>.zip, holding
// slideshow/{plugin.json, LICENSE, README.md, bin/win-unpacked/...}. The version is the one in
// plugin.json, the only place it is kept; the exe's version resource is stamped with it too.

import { execFileSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const { version } = JSON.parse(readFileSync(join(root, 'plugin.json'), 'utf8'))
const zip = resolve(root, '..', 'dist', `Slideshow-${version}.zip`)

const run = (command, args) => execFileSync(command, args, { cwd: root, stdio: 'inherit', shell: true })

run('npx', ['electron-vite', 'build'])
rmSync(join(root, 'bin'), { recursive: true, force: true })
run('npx', ['electron-builder', '--dir', `-c.extraMetadata.version=${version}`])

mkdirSync(dirname(zip), { recursive: true })
if (existsSync(zip)) rmSync(zip)
// The zip starts with one folder, slideshow/, so it is staged under that name first (Windows'
// bsdtar has no -s to rename entries while archiving).
const stage = join(dirname(zip), '.slideshow-stage')
const folder = join(stage, 'slideshow')
rmSync(stage, { recursive: true, force: true })
for (const file of ['plugin.json', 'LICENSE', 'README.md']) cpSync(join(root, file), join(folder, file))
cpSync(join(root, 'bin', 'win-unpacked'), join(folder, 'bin', 'win-unpacked'), { recursive: true })
// Windows' own bsdtar, by full path: the tar first on PATH in Git Bash is GNU tar, which cannot
// write zip.
const tar = join(process.env.SystemRoot ?? 'C:\\Windows', 'System32', 'tar.exe')
execFileSync(tar, ['-a', '-c', '-f', zip, '-C', stage, 'slideshow'], { stdio: 'inherit' })
rmSync(stage, { recursive: true, force: true })
console.log(`\n${zip}`)

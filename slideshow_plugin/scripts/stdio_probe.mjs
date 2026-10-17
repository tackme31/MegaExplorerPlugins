// Spawns the plugin with piped stdio, as MEGA Explorer's QProcess does, and runs one
// initialize -> command.execute -> shutdown exchange. Usage: node scripts/stdio_probe.mjs <exe> [args...]
import { spawn } from 'node:child_process'
import { createInterface } from 'node:readline'
const [exe, ...args] = process.argv.slice(2)
const p = spawn(exe, args, { stdio: ['pipe', 'pipe', 'pipe'] })
p.stderr.on('data', (d) => process.stderr.write(`[stderr] ${d}`))
const send = (m) => p.stdin.write(JSON.stringify({ jsonrpc: '2.0', ...m }) + '\n')
createInterface({ input: p.stdout }).on('line', (line) => {
  console.log('<-', JSON.stringify(line))
  let m
  try { m = JSON.parse(line) } catch { return }
  if (m.id === 1) send({ id: 2, method: 'command.execute', params: { invocationId: 1, commandId: 'x', context: { site: 'folder', items: [] } } })
  else if (m.id === 2) send({ id: 3, method: 'shutdown' })
  else if (m.id === 3) p.stdin.end()
})
p.on('exit', (c) => console.log('exit', c))
send({ id: 1, method: 'initialize', params: { apiVersion: 1, app: {}, plugin: {} } })
setTimeout(() => { console.log('TIMEOUT'); p.kill() }, 20000)

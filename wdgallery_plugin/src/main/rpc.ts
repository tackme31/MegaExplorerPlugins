// JSON-RPC 2.0 over stdin/stdout, one message per line: MEGA Explorer's plugin transport
// (its PLUGINS.md, "Protocol"). Answers the app's requests through handlers and sends our
// own requests to it.

import { Socket } from 'node:net'
import { createInterface } from 'node:readline'

export class RpcError extends Error {
  constructor(
    readonly code: number,
    message: string
  ) {
    super(message)
  }
}

type Handler = (params: unknown) => unknown | Promise<unknown>

interface Pending {
  resolve: (value: unknown) => void
  reject: (error: Error) => void
}

export class Rpc {
  private handlers = new Map<string, Handler>()
  private pending = new Map<string, Pending>()
  private nextId = 1

  constructor(private readonly onEnd: () => void) {}

  start(): void {
    // Not process.stdin: in Electron's main process on Windows it never delivers data from a
    // pipe (the app starts us through QProcess with piped stdio). Nor fs.createReadStream on
    // fd 0: that reads, but its blocking read keeps the process alive after exit is called.
    // A socket over fd 0 does both.
    const lines = createInterface({ input: new Socket({ fd: 0, readable: true, writable: false }) })
    lines.on('line', (line) => this.receive(line))
    lines.on('close', () => this.onEnd())
  }

  // Requests and notifications from the app; a notification's return value is dropped.
  on(method: string, handler: Handler): void {
    this.handlers.set(method, handler)
  }

  call<T>(method: string, params: object): Promise<T> {
    const id = `p${this.nextId++}`
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject })
      this.write({ jsonrpc: '2.0', id, method, params })
    })
  }

  private write(message: object): void {
    process.stdout.write(JSON.stringify(message) + '\n')
  }

  private receive(line: string): void {
    let message: { id?: string | number; method?: string; params?: unknown; result?: unknown; error?: { code: number; message: string } }
    try {
      message = JSON.parse(line)
    } catch {
      return
    }
    if (message.method === undefined) {
      const pending = this.pending.get(String(message.id))
      if (!pending) return
      this.pending.delete(String(message.id))
      if (message.error) pending.reject(new RpcError(message.error.code, message.error.message))
      else pending.resolve(message.result)
      return
    }
    const handler = this.handlers.get(message.method)
    const id = message.id
    if (id === undefined) {
      if (handler) void Promise.resolve().then(() => handler(message.params))
      return
    }
    if (!handler) {
      this.write({ jsonrpc: '2.0', id, error: { code: -32601, message: `Method not found: ${message.method}` } })
      return
    }
    Promise.resolve()
      .then(() => handler(message.params))
      .then(
        (result) => this.write({ jsonrpc: '2.0', id, result: result ?? {} }),
        (error: unknown) => {
          const text = error instanceof Error ? error.message : String(error)
          this.write({ jsonrpc: '2.0', id, error: { code: -32000, message: text } })
        }
      )
  }
}

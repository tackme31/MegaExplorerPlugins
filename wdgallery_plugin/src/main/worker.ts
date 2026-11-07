// The index's own thread: building and searching run synchronous SQLite calls that can take
// seconds, which on the main thread would freeze the window. Requests are answered in order.

import { existsSync } from 'node:fs'
import { parentPort } from 'node:worker_threads'
import { Builder, type RawItem, SCHEMA_VERSION, Searcher } from './store.ts'

export type WorkerRequest =
  | { op: 'open'; path: string }
  | { op: 'build-start' }
  | { op: 'build-add'; items: RawItem[] }
  | { op: 'build-finish'; path: string; meta: Record<string, string> }
  | { op: 'search'; request: Parameters<Searcher['search']>[0] }
  | { op: 'suggest'; kind: 'tag' | 'character'; text: string }
  | { op: 'detail'; handle: string }

let searcher: Searcher | null = null
let builder: Builder | null = null

// Opens the index at path; null when there is none, or it was written by another version.
function open(path: string): Record<string, string> | null {
  searcher?.close()
  searcher = null
  if (!existsSync(path)) return null
  const s = new Searcher(path)
  const meta = s.meta()
  if (meta.schema !== SCHEMA_VERSION) {
    s.close()
    return null
  }
  searcher = s
  return meta
}

function ready(): Searcher {
  if (!searcher) throw new Error('The index is not ready')
  return searcher
}

function handle(message: WorkerRequest): unknown {
  switch (message.op) {
    case 'open':
      return open(message.path)
    case 'build-start':
      builder = new Builder()
      return null
    case 'build-add':
      builder!.add(message.items)
      return builder!.count
    case 'build-finish': {
      searcher?.close()
      searcher = null
      builder!.finish(message.path, message.meta)
      builder = null
      return open(message.path)
    }
    case 'search':
      return ready().search(message.request)
    case 'suggest':
      return ready().suggest(message.kind, message.text)
    case 'detail':
      return ready().detail(message.handle)
  }
}

parentPort!.on('message', ({ id, message }: { id: number; message: WorkerRequest }) => {
  try {
    parentPort!.postMessage({ id, result: handle(message) })
  } catch (error) {
    if (message.op === 'build-finish' || message.op === 'build-add') builder = null
    parentPort!.postMessage({ id, error: error instanceof Error ? error.message : String(error) })
  }
})

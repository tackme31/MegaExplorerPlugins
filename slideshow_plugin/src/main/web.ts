// Serves the renderer and a small JSON API over the LAN, so a phone's browser can run the
// slideshow. Images are proxied: the app's stream server listens on 127.0.0.1 only, and
// opening that to the LAN would expose every file, not just this folder's.
//
// Access needs the per-run token. It arrives as ?t= on the first page load and is kept in a
// cookie after that, so the page's relative asset URLs need not carry it.

import { createServer, get, IncomingMessage, Server, ServerResponse } from 'node:http'
import { randomBytes } from 'node:crypto'
import { createReadStream, statSync } from 'node:fs'
import { networkInterfaces } from 'node:os'
import { extname, join, normalize, sep } from 'node:path'

export interface WebHandlers {
  session(): Promise<unknown>
  streamUrl(handle: string): Promise<string>
  reveal(handle: string): Promise<void>
  saveSettings(settings: unknown): void
}

export interface WebServer {
  urls: string[]
  close(): void
}

const PREFERRED_PORT = 8765

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
  '.png': 'image/png'
}

function lanAddresses(): string[] {
  const out: string[] = []
  for (const list of Object.values(networkInterfaces())) {
    for (const a of list ?? []) if (a.family === 'IPv4' && !a.internal) out.push(a.address)
  }
  // Home routers hand out 192.168.x.x; virtual adapters (WSL, Hyper-V) tend to be 172.x.
  const rank = (ip: string): number => (ip.startsWith('192.168.') ? 0 : ip.startsWith('10.') ? 1 : 2)
  return out.sort((a, b) => rank(a) - rank(b))
}

function readBody(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let data = ''
    req.setEncoding('utf8')
    req.on('data', (chunk: string) => (data += chunk))
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : null)
      } catch (e) {
        reject(e)
      }
    })
    req.on('error', reject)
  })
}

function json(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify(body))
}

function hasToken(req: IncomingMessage, url: URL, token: string): boolean {
  if (url.searchParams.get('t') === token) return true
  return (req.headers.cookie ?? '').split(/;\s*/).includes(`t=${token}`)
}

function serveStatic(rendererDir: string, pathname: string, res: ServerResponse): void {
  const relative = pathname === '/' ? 'index.html' : decodeURIComponent(pathname.slice(1))
  const file = normalize(join(rendererDir, relative))
  if (!file.startsWith(rendererDir + sep)) {
    res.writeHead(403).end()
    return
  }
  try {
    if (!statSync(file).isFile()) throw new Error()
  } catch {
    res.writeHead(404).end()
    return
  }
  res.writeHead(200, { 'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream' })
  createReadStream(file).pipe(res)
}

async function proxyImage(handlers: WebHandlers, handle: string, req: IncomingMessage, res: ServerResponse): Promise<void> {
  const upstreamUrl = await handlers.streamUrl(handle)
  const upstream = get(upstreamUrl, (up) => {
    const headers: Record<string, string> = { 'Cache-Control': 'private, max-age=3600' }
    for (const h of ['content-type', 'content-length']) {
      const v = up.headers[h]
      if (typeof v === 'string') headers[h] = v
    }
    res.writeHead(up.statusCode ?? 502, headers)
    up.pipe(res)
  })
  upstream.on('error', () => {
    if (!res.headersSent) res.writeHead(502)
    res.end()
  })
  // The phone moving on aborts the read from MEGA too.
  req.on('close', () => upstream.destroy())
}

export function startWebServer(rendererDir: string, handlers: WebHandlers): Promise<WebServer> {
  const token = randomBytes(12).toString('hex')

  const server: Server = createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost')
    if (!hasToken(req, url, token)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Open the URL shown on the PC.')
      return
    }
    if (url.searchParams.get('t') === token) {
      res.setHeader('Set-Cookie', `t=${token}; Path=/; HttpOnly; SameSite=Strict`)
    }
    const path = url.pathname
    void (async () => {
      try {
        if (path === '/api/session' && req.method === 'GET') {
          json(res, 200, await handlers.session())
        } else if (path === '/api/settings' && req.method === 'POST') {
          handlers.saveSettings(await readBody(req))
          json(res, 200, {})
        } else if (path.startsWith('/api/reveal/') && req.method === 'POST') {
          await handlers.reveal(decodeURIComponent(path.slice('/api/reveal/'.length)))
          json(res, 200, {})
        } else if (path.startsWith('/img/')) {
          await proxyImage(handlers, decodeURIComponent(path.slice('/img/'.length)), req, res)
        } else {
          serveStatic(rendererDir, path, res)
        }
      } catch (e) {
        if (!res.headersSent) json(res, 500, { message: e instanceof Error ? e.message : String(e) })
        else res.end()
      }
    })()
  })

  const listen = (port: number): Promise<number> =>
    new Promise((resolve, reject) => {
      server.once('error', reject)
      server.listen(port, '0.0.0.0', () => {
        server.off('error', reject)
        const address = server.address()
        resolve(typeof address === 'object' && address ? address.port : port)
      })
    })

  return listen(PREFERRED_PORT)
    .catch(() => listen(0))
    .then((port) => ({
      urls: lanAddresses().map((ip) => `http://${ip}:${port}/?t=${token}`),
      close: () => {
        server.closeAllConnections()
        server.close()
      }
    }))
}

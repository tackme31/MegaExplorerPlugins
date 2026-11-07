// The index: an SQLite file of the drive's image and video files, their WD Tagger words as an
// inverted index (postings), and per-word IDF and per-file norms for similarity. Built whole by
// Builder (into a temp file, renamed over the old one), read by Searcher.
//
// The similarity score is WD Similar's: cosine over the wd: and chara: words, each weighted by
// (log((n+1)/(df+1)) + 1)^2 times its level in hundredths on both sides.

import { renameSync, rmSync } from 'node:fs'
import { DatabaseSync } from 'node:sqlite'
import {
  type Condition,
  type Detail,
  type Hit,
  type Rating,
  RATINGS,
  type SearchRequest,
  type SearchResult,
  type Sort,
  type Suggestion,
  extensionOf,
  VIDEO_EXTENSIONS
} from '../shared/types.ts'
import { CHARACTER, GENERAL, USER, ratingName, splitTags } from './tags.ts'

export const SCHEMA_VERSION = '1'

export interface RawItem {
  handle: string
  name: string
  size: number
  mtime: number
  tags: string[] | null
  hasThumbnail: boolean
  crc: string | null
}

const SCHEMA = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE items (
  id INTEGER PRIMARY KEY,
  handle TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime INTEGER NOT NULL,
  crc TEXT,
  has_thumbnail INTEGER NOT NULL,
  video INTEGER NOT NULL,
  rating INTEGER,
  tags TEXT NOT NULL,
  norm REAL NOT NULL
);
CREATE TABLE words (
  id INTEGER PRIMARY KEY,
  kind INTEGER NOT NULL,
  word TEXT NOT NULL,
  files INTEGER NOT NULL,
  w2 REAL NOT NULL,
  UNIQUE (kind, word)
);
CREATE TABLE postings (
  word_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  level INTEGER NOT NULL,
  PRIMARY KEY (word_id, item_id)
) WITHOUT ROWID;
`

// Built after the rows are in: indexing a filled table once is faster than row by row.
const SORT_INDEXES = `
CREATE INDEX items_mtime ON items (mtime);
CREATE INDEX items_size ON items (size);
CREATE INDEX items_name ON items (name COLLATE NOCASE);
`

const VIDEO = new Set(VIDEO_EXTENSIONS)
// Packed into one small integer per posting while building: item id * 256 + level.
const LEVEL_BITS = 256
const POSTINGS_CHUNK = 50_000

export class Builder {
  private readonly rows: (string | number | null)[][] = []
  private readonly wordIds = new Map<string, number>()
  private readonly wordKinds: number[] = []
  private readonly wordTexts: string[] = []
  private readonly postings: number[][] = []
  private tagged = 0

  get count(): number {
    return this.rows.length
  }

  add(items: RawItem[]): void {
    for (const item of items) {
      const id = this.rows.length + 1
      const { words, rating } = splitTags(item.tags)
      let similar = false
      for (const w of words) {
        const key = `${w.kind}\t${w.word}`
        let index = this.wordIds.get(key)
        if (index === undefined) {
          index = this.wordKinds.length
          this.wordIds.set(key, index)
          this.wordKinds.push(w.kind)
          this.wordTexts.push(w.word)
          this.postings.push([])
        }
        this.postings[index].push(id * LEVEL_BITS + w.level)
        if (w.kind !== USER) similar = true
      }
      if (similar) this.tagged++
      this.rows.push([
        id,
        item.handle,
        item.name,
        item.size,
        item.mtime,
        item.crc,
        item.hasThumbnail ? 1 : 0,
        VIDEO.has(extensionOf(item.name)) ? 1 : 0,
        rating,
        JSON.stringify(item.tags ?? [])
      ])
    }
  }

  // Writes the index to `path` through `path + '.tmp'`, so a half-written file never replaces a
  // good one. The caller must have closed any connection to `path`.
  finish(path: string, meta: Record<string, string>): void {
    const n = this.tagged
    const w2 = this.wordKinds.map((kind, i) => {
      if (kind === USER) return 0
      const idf = Math.log((n + 1) / (this.postings[i].length + 1)) + 1
      return idf * idf
    })
    const normSq = new Float64Array(this.rows.length + 1)
    this.postings.forEach((list, i) => {
      if (!w2[i]) return
      for (const packed of list) {
        const p = (packed % LEVEL_BITS) / 100
        normSq[Math.floor(packed / LEVEL_BITS)] += w2[i] * p * p
      }
    })

    const tmp = `${path}.tmp`
    rmSync(tmp, { force: true })
    const db = new DatabaseSync(tmp)
    try {
      db.exec('PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA cache_size = -200000')
      db.exec(SCHEMA)
      db.exec('BEGIN')
      const insertItem = db.prepare('INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
      for (const row of this.rows) insertItem.run(...row, Math.sqrt(normSq[row[0] as number]))
      const insertWord = db.prepare('INSERT INTO words VALUES (?, ?, ?, ?, ?)')
      this.wordKinds.forEach((kind, i) => insertWord.run(i + 1, kind, this.wordTexts[i], this.postings[i].length, w2[i]))
      // One statement per chunk of a word's postings rather than one per row: the rows arrive
      // in (word_id, item_id) order, so the WITHOUT ROWID table is filled by appending.
      const insertPostings = db.prepare(
        `INSERT INTO postings SELECT ?, j.value / ${LEVEL_BITS}, j.value % ${LEVEL_BITS} FROM json_each(?) j`
      )
      this.postings.forEach((list, i) => {
        for (let start = 0; start < list.length; start += POSTINGS_CHUNK)
          insertPostings.run(i + 1, JSON.stringify(list.slice(start, start + POSTINGS_CHUNK)))
      })
      const insertMeta = db.prepare('INSERT INTO meta VALUES (?, ?)')
      for (const [key, value] of Object.entries({ ...meta, schema: SCHEMA_VERSION, files: String(this.rows.length) }))
        insertMeta.run(key, value)
      db.exec('COMMIT')
      db.exec(SORT_INDEXES)
    } finally {
      db.close()
    }
    renameSync(tmp, path)
  }
}

const SORT_SQL: Record<Sort, string> = {
  'mtime-desc': 'i.mtime DESC, i.id',
  'mtime-asc': 'i.mtime, i.id',
  'name-asc': 'i.name COLLATE NOCASE, i.id',
  'name-desc': 'i.name COLLATE NOCASE DESC, i.id',
  'size-desc': 'i.size DESC, i.id',
  'size-asc': 'i.size, i.id'
}

const HIT_COLUMNS = 'i.handle, i.name, i.size, i.mtime, i.rating, i.video, i.has_thumbnail'

type SqlValue = string | number | null
type Source = 'all' | 'base' | 'ranked'

interface Prepared {
  key: string
  source: Source
  counts: Record<Rating, number>
  untagged: number
  missingReference: boolean
}

function escapeLike(text: string): string {
  return text.replace(/[\\%_]/g, (c) => `\\${c}`)
}

function startOfDay(date: string): number {
  const [y, m, d] = date.split('-').map(Number)
  return Math.floor(new Date(y, m - 1, d).getTime() / 1000)
}

// The conditions minus ids, so the same search typed twice reuses the prepared tables.
function keyOf(conditions: Condition[]): string {
  return JSON.stringify(conditions.map(({ id: _id, ...rest }) => rest))
}

export class Searcher {
  private readonly db: DatabaseSync
  private prepared: Prepared | null = null

  constructor(path: string) {
    this.db = new DatabaseSync(path)
    this.db.exec('PRAGMA temp_store = MEMORY; PRAGMA cache_size = -262144; PRAGMA mmap_size = 2147483648')
  }

  close(): void {
    this.db.close()
  }

  meta(): Record<string, string> {
    const rows = this.db.prepare('SELECT key, value FROM meta').all() as { key: string; value: string }[]
    return Object.fromEntries(rows.map((r) => [r.key, r.value]))
  }

  search(request: SearchRequest): SearchResult {
    const started = performance.now()
    const key = keyOf(request.conditions)
    if (this.prepared?.key !== key) this.prepared = this.prepare(request.conditions, key)
    const p = this.prepared
    const ratingIds = request.ratings.map((r) => RATINGS.indexOf(r)).filter((r) => r >= 0)
    const total = ratingIds.length
      ? request.ratings.reduce((sum, r) => sum + p.counts[r], 0)
      : RATINGS.reduce((sum, r) => sum + p.counts[r], p.untagged)
    const where = ratingIds.length ? `WHERE i.rating IN (${ratingIds.join(',')})` : ''
    const from =
      p.source === 'ranked'
        ? `FROM ranked r CROSS JOIN items i ON i.id = r.item_id ${where} ORDER BY r.rank`
        : p.source === 'base'
          ? `FROM base b CROSS JOIN items i ON i.id = b.item_id ${where} ORDER BY ${SORT_SQL[request.sort]}`
          : `FROM items i ${where} ORDER BY ${SORT_SQL[request.sort]}`
    const score = p.source === 'ranked' ? ', r.score' : ''
    const rows = this.db
      .prepare(`SELECT ${HIT_COLUMNS}${score} ${from} LIMIT ? OFFSET ?`)
      .all(request.pageSize, request.page * request.pageSize) as Record<string, SqlValue>[]
    const hits: Hit[] = rows.map((r) => ({
      handle: r.handle as string,
      name: r.name as string,
      size: r.size as number,
      mtime: r.mtime as number,
      rating: ratingName(r.rating as number | null) as Rating | null,
      video: r.video === 1,
      hasThumbnail: r.has_thumbnail === 1,
      ...(p.source === 'ranked' ? { score: r.score as number } : {})
    }))
    return {
      total,
      ratingCounts: p.counts,
      hits,
      page: request.page,
      ...(p.missingReference ? { missingReference: true } : {}),
      millis: Math.round(performance.now() - started)
    }
  }

  // WD Tagger's words join with _, the user's own tags may hold spaces: a word typed with
  // spaces matches either way.
  private wordIds(kinds: number[], word: string): { ids: number[]; files: number } {
    const rows = this.db
      .prepare(`SELECT id, files FROM words WHERE word IN (?, ?) AND kind IN (${kinds.join(',')})`)
      .all(word, word.replace(/ /g, '_')) as { id: number; files: number }[]
    return { ids: rows.map((r) => r.id), files: rows.reduce((s, r) => s + r.files, 0) }
  }

  private prepare(conditions: Condition[], key: string): Prepared {
    const db = this.db
    const filters: string[] = []
    const params: SqlValue[] = []
    const wordSets: { ids: number[]; files: number }[] = []
    let similar: { handle: string } | null = null
    for (const c of conditions) {
      if (c.kind === 'tag' || c.kind === 'character') {
        const words = this.wordIds(c.kind === 'tag' ? [GENERAL, USER] : [CHARACTER], c.word)
        if (!c.negated) wordSets.push(words)
        else if (words.ids.length)
          filters.push(`NOT EXISTS (SELECT 1 FROM postings x WHERE x.word_id IN (${words.ids.join(',')}) AND x.item_id = i.id)`)
      } else if (c.kind === 'name') {
        filters.push("i.name LIKE ? ESCAPE '\\'")
        params.push(`%${escapeLike(c.text)}%`)
      } else if (c.kind === 'size') {
        filters.push(`i.size ${c.op} ?`)
        params.push(c.bytes)
      } else if (c.kind === 'modified') {
        filters.push(c.op === '>' ? 'i.mtime >= ?' : 'i.mtime < ?')
        params.push(startOfDay(c.date))
      } else similar = c
    }

    let source: Source = 'all'
    db.exec('DROP TABLE IF EXISTS temp.base; DROP TABLE IF EXISTS temp.ranked; DROP TABLE IF EXISTS temp.query_words')
    if (wordSets.length || filters.length) {
      source = 'base'
      db.exec('CREATE TEMP TABLE base (item_id INTEGER PRIMARY KEY)')
      if (wordSets.every((s) => s.ids.length)) {
        if (wordSets.length) {
          // Start from the rarest word's postings and look the others up by primary key.
          const [first, ...others] = [...wordSets].sort((a, b) => a.files - b.files)
          const exists = others.map(
            (s) => `EXISTS (SELECT 1 FROM postings x WHERE x.word_id IN (${s.ids.join(',')}) AND x.item_id = p.item_id)`
          )
          const where = [`p.word_id IN (${first.ids.join(',')})`, ...exists, ...filters].join(' AND ')
          db.prepare(
            `INSERT OR IGNORE INTO base SELECT p.item_id FROM postings p CROSS JOIN items i ON i.id = p.item_id WHERE ${where}`
          ).run(...params)
        } else {
          db.prepare(`INSERT INTO base SELECT i.id FROM items i WHERE ${filters.join(' AND ')}`).run(...params)
        }
      }
    }

    let missingReference = false
    if (similar) {
      const ref = db.prepare('SELECT id, tags, size, crc FROM items WHERE handle = ?').get(similar.handle) as
        | { id: number; tags: string; size: number; crc: string | null }
        | undefined
      db.exec('CREATE TEMP TABLE ranked (rank INTEGER PRIMARY KEY, item_id INTEGER NOT NULL, score REAL NOT NULL)')
      if (!ref) missingReference = true
      else this.rank(ref, source === 'base')
      source = 'ranked'
    }

    const table = source === 'ranked' ? 'ranked' : source === 'base' ? 'base' : null
    const countRows = (
      table
        ? db.prepare(`SELECT i.rating, COUNT(*) AS n FROM ${table} t CROSS JOIN items i ON i.id = t.item_id GROUP BY i.rating`)
        : db.prepare('SELECT i.rating, COUNT(*) AS n FROM items i GROUP BY i.rating')
    ).all() as { rating: number | null; n: number }[]
    const counts = Object.fromEntries(RATINGS.map((r) => [r, 0])) as Record<Rating, number>
    let untagged = 0
    for (const row of countRows) {
      const name = ratingName(row.rating) as Rating | null
      if (name) counts[name] = row.n
      else untagged += row.n
    }
    return { key, source, counts, untagged, missingReference }
  }

  private rank(ref: { id: number; tags: string; size: number; crc: string | null }, withinBase: boolean): void {
    const db = this.db
    const words = splitTags(JSON.parse(ref.tags) as string[]).words.filter((w) => w.kind !== USER)
    db.exec('CREATE TEMP TABLE query_words (word_id INTEGER PRIMARY KEY, qw REAL NOT NULL)')
    const find = db.prepare('SELECT id, w2 FROM words WHERE kind = ? AND word = ?')
    const insert = db.prepare('INSERT OR IGNORE INTO query_words VALUES (?, ?)')
    let qn = 0
    for (const w of words) {
      const row = find.get(w.kind, w.word) as { id: number; w2: number } | undefined
      if (!row) continue
      const f = w.level / 100
      insert.run(row.id, row.w2 * f)
      qn += row.w2 * f * f
    }
    if (!qn) return
    const copy = ref.crc === null ? '' : 'AND NOT (i.size = :size AND i.crc = :crc)'
    // CROSS JOIN fixes the order: the query's few words, their postings, then lookups by key.
    db.prepare(
      `INSERT INTO ranked (item_id, score)
       SELECT p.item_id, SUM(q.qw * p.level) / 100.0 / (i.norm * :qnorm) AS score
       FROM query_words q
       CROSS JOIN postings p ON p.word_id = q.word_id
       ${withinBase ? 'CROSS JOIN base b ON b.item_id = p.item_id' : ''}
       CROSS JOIN items i ON i.id = p.item_id
       WHERE p.item_id != :ref ${copy}
       GROUP BY p.item_id
       ORDER BY score DESC, p.item_id`
    ).run({ qnorm: Math.sqrt(qn), ref: ref.id, ...(ref.crc === null ? {} : { size: ref.size, crc: ref.crc }) })
  }

  suggest(kind: 'tag' | 'character', text: string): Suggestion[] {
    const q = text.trim().toLowerCase()
    if (!q) return []
    const u = q.replace(/ /g, '_')
    const kinds = kind === 'character' ? [CHARACTER] : [GENERAL, USER]
    return this.db
      .prepare(
        `SELECT word, SUM(files) AS files FROM words
         WHERE kind IN (${kinds.join(',')}) AND (instr(word, :q) > 0 OR instr(word, :u) > 0)
         GROUP BY word
         ORDER BY word IN (:q, :u) DESC, (substr(word, 1, length(:q)) = :q OR substr(word, 1, length(:u)) = :u) DESC,
                  files DESC, word
         LIMIT 10`
      )
      .all({ q, u }) as unknown as Suggestion[]
  }

  detail(handle: string): Detail | null {
    const row = this.db.prepare('SELECT tags FROM items WHERE handle = ?').get(handle) as { tags: string } | undefined
    if (!row) return null
    const { words, rating } = splitTags(JSON.parse(row.tags) as string[])
    const of = (kind: number) => words.filter((w) => w.kind === kind).map((w) => w.word)
    return {
      handle,
      rating: ratingName(rating) as Rating | null,
      characters: of(CHARACTER),
      general: of(GENERAL),
      user: of(USER)
    }
  }
}

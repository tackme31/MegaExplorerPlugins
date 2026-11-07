import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { after, before, describe, test } from 'node:test'
import type { Condition, SearchRequest } from '../shared/types.ts'
import { Builder, type RawItem, Searcher } from './store.ts'
import { splitTags } from './tags.ts'

const DAY = 86400
const BASE_TIME = Math.floor(new Date(2025, 0, 1).getTime() / 1000)

function item(n: number, tags: string[], extra: Partial<RawItem> = {}): RawItem {
  return {
    handle: `H${n}`,
    name: `file${n}.jpg`,
    size: n * 1000,
    mtime: BASE_TIME + n * DAY,
    tags,
    hasThumbnail: true,
    crc: `crc${n}`,
    ...extra
  }
}

const ITEMS: RawItem[] = [
  item(1, ['wd:1girl long_hair smile', 'rating:general', 'chara:hatsune_miku']),
  item(2, ['wd:1girl long_hair smile', 'rating:general', 'chara:hatsune_miku'], { crc: 'crc1', size: 1000 }),
  item(3, ['wd:1girl short_hair', 'rating:sensitive']),
  item(4, ['wd:long_hair smile umbrella', 'rating:explicit', 'chara:kagamine_rin']),
  item(5, ['wd:cat', 'rating:general', 'Holiday', 'Long Trip']),
  item(6, null as unknown as string[], { name: 'clip6.mp4' }),
  item(7, ['wd:1girl_smile', 'rating:general'], { name: 'Summer_100%.png' })
]

let dir: string
let searcher: Searcher

type NoId<T> = T extends unknown ? Omit<T, 'id'> : never

function search(conditions: NoId<Condition>[], extra: Partial<SearchRequest> = {}) {
  return searcher.search({
    conditions: conditions.map((c, id) => ({ ...c, id }) as Condition),
    ratings: [],
    sort: 'mtime-asc',
    page: 0,
    pageSize: 50,
    ...extra
  })
}

const handles = (r: { hits: { handle: string }[] }) => r.hits.map((h) => h.handle)

before(() => {
  dir = mkdtempSync(join(tmpdir(), 'wdgallery-test-'))
  const builder = new Builder()
  builder.add(ITEMS.slice(0, 3))
  builder.add(ITEMS.slice(3))
  builder.finish(join(dir, 'index.sqlite'), { root: 'R' })
  searcher = new Searcher(join(dir, 'index.sqlite'))
})

after(() => {
  searcher.close()
  rmSync(dir, { recursive: true, force: true })
})

describe('splitTags', () => {
  test('splits each kind with levels and keeps the first rating', () => {
    const { words, rating } = splitTags(['wd:a b c', 'rating:Sensitive', 'rating:general', 'chara:x chara:y', 'Mine'])
    assert.equal(rating, 1)
    assert.deepEqual(
      words.map((w) => [w.kind, w.word, w.level]),
      [[0, 'a', 100], [0, 'b', 75], [0, 'c', 50], [1, 'x', 100], [1, 'y', 50], [3, 'mine', 100]]
    )
  })
})

describe('search', () => {
  test('no conditions lists every file with rating counts', () => {
    const r = search([])
    assert.equal(r.total, 7)
    assert.deepEqual(r.ratingCounts, { general: 4, sensitive: 1, questionable: 0, explicit: 1 })
  })

  test('tags match whole words, not parts', () => {
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'smile' }])), ['H1', 'H2', 'H4'])
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'smil' }])), [])
    assert.deepEqual(handles(search([{ kind: 'tag', word: '1girl' }, { kind: 'tag', word: 'smile' }])), ['H1', 'H2'])
  })

  test('a bare word also finds the user own tags; chara: only characters', () => {
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'holiday' }])), ['H5'])
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'long trip' }])), ['H5'])
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'long hair' }])), ['H1', 'H2', 'H4'])
    assert.deepEqual(handles(search([{ kind: 'character', word: 'kagamine_rin' }])), ['H4'])
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'kagamine_rin' }])), [])
  })

  test('a negated tag leaves out the files carrying it', () => {
    const not = (word: string) => ({ kind: 'tag', word, negated: true }) as const
    assert.deepEqual(handles(search([not('smile')])), ['H3', 'H5', 'H6', 'H7'])
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'long_hair' }, not('1girl')])), ['H4'])
    assert.deepEqual(handles(search([not('long trip'), not('1girl')])), ['H4', 'H6', 'H7'])
    assert.equal(search([not('no_such_tag')]).total, 7)
    assert.deepEqual(handles(search([{ kind: 'similar', handle: 'H1', name: '' }, not('umbrella')])), ['H3'])
    assert.deepEqual(search([{ kind: 'tag', word: 'smile' }, not('smile')]).total, 0)
  })

  test('a negated character too, also within a similarity search', () => {
    const notChara = (word: string) => ({ kind: 'character', word, negated: true }) as const
    assert.deepEqual(handles(search([notChara('hatsune_miku')])), ['H3', 'H4', 'H5', 'H6', 'H7'])
    assert.equal(search([{ kind: 'tag', word: 'hatsune_miku', negated: true }]).total, 7)
    const like1 = { kind: 'similar', handle: 'H1', name: '' } as const
    assert.deepEqual(handles(search([like1])), ['H3', 'H4'])
    assert.deepEqual(handles(search([like1, notChara('kagamine_rin')])), ['H3'])
  })

  test('name, size and date filters, alone and with tags', () => {
    assert.deepEqual(handles(search([{ kind: 'name', text: '100%' }])), ['H7'])
    assert.equal(handles(search([{ kind: 'name', text: 'FILE' }])).length, 5)
    assert.deepEqual(handles(search([{ kind: 'size', op: '>', bytes: 4500 }])), ['H5', 'H6', 'H7'])
    assert.deepEqual(handles(search([{ kind: 'modified', op: '<', date: '2025-01-04' }])), ['H1', 'H2'])
    assert.deepEqual(handles(search([{ kind: 'tag', word: 'long_hair' }, { kind: 'size', op: '<', bytes: 3500 }])), ['H1', 'H2'])
  })

  test('ratings filter the hits but not the counts', () => {
    const r = search([{ kind: 'tag', word: '1girl' }], { ratings: ['sensitive'] })
    assert.deepEqual(handles(r), ['H3'])
    assert.equal(r.total, 1)
    assert.deepEqual(r.ratingCounts, { general: 2, sensitive: 1, questionable: 0, explicit: 0 })
  })

  test('sorting and paging', () => {
    assert.deepEqual(handles(search([], { sort: 'size-desc', pageSize: 2, page: 1 })), ['H5', 'H4'])
    assert.deepEqual(handles(search([], { sort: 'name-asc' })).slice(0, 2), ['H6', 'H1'])
  })

  test('video files are marked', () => {
    assert.equal(search([{ kind: 'name', text: 'clip' }]).hits[0].video, true)
  })
})

describe('similarity', () => {
  test('ranks by shared words, leaves out the file itself and its copies', () => {
    const r = search([{ kind: 'similar', handle: 'H1', name: 'file1.jpg' }])
    // H2 is a copy of H1 (same size and crc); H5 to H7 share no word. Scores are WD Similar's
    // for the same files.
    assert.deepEqual(handles(r), ['H3', 'H4'])
    assert.deepEqual(r.hits.map((h) => Math.round(h.score! * 10000) / 10000), [0.4521, 0.3072])
  })

  test('combines with the other conditions and with ratings', () => {
    assert.deepEqual(handles(search([{ kind: 'similar', handle: 'H3', name: '' }, { kind: 'tag', word: 'smile' }])), ['H1', 'H2'])
    const r = search([{ kind: 'similar', handle: 'H4', name: '' }], { ratings: ['explicit', 'general'] })
    assert.deepEqual(handles(r), ['H1', 'H2'])
    assert.deepEqual(r.ratingCounts, { general: 2, sensitive: 0, questionable: 0, explicit: 0 })
  })

  test('a reference gone from the index gives nothing', () => {
    const r = search([{ kind: 'similar', handle: 'gone', name: '' }])
    assert.equal(r.missingReference, true)
    assert.equal(r.hits.length, 0)
  })
})

describe('suggest and detail', () => {
  test('exact, then prefix, then contains', () => {
    assert.deepEqual(
      searcher.suggest('tag', 'smile').map((s) => s.word),
      ['smile', '1girl_smile']
    )
    assert.deepEqual(
      searcher.suggest('tag', 'long ').map((s) => ({ ...s })),
      [{ word: 'long trip', files: 1 }, { word: 'long_hair', files: 3 }].sort((a, b) => b.files - a.files)
    )
    assert.deepEqual({ ...searcher.suggest('character', 'miku')[0] }, { word: 'hatsune_miku', files: 2 })
  })

  test('detail splits the stored tags', () => {
    assert.deepEqual(searcher.detail('H5'), {
      handle: 'H5',
      rating: 'general',
      characters: [],
      general: ['cat'],
      user: ['holiday', 'long trip']
    })
    assert.equal(searcher.detail('nope'), null)
  })
})

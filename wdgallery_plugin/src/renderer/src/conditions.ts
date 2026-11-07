import type { Condition } from '../../shared/types'
import { formatSize } from './format'

let nextId = 1
export function newId(): number {
  return nextId++
}

const UNITS: Record<string, number> = { b: 1, kb: 1024, mb: 1024 * 1024, gb: 1024 * 1024 * 1024 }

// What the search box accepts: name:<text>, size:>1MB, modified:>2025-01-01, chara:<name>;
// anything else is one tag word. A malformed size: or modified: is taken as a tag, which then
// finds nothing, rather than dropped silently.
export function parseCondition(text: string): Condition | null {
  const t = text.trim()
  if (!t) return null
  const id = newId()
  const [, key, rest] = /^(\w+):(.*)$/.exec(t) ?? []
  if (key === 'name' && rest) return { id, kind: 'name', text: rest }
  if (key === 'chara' && rest) return { id, kind: 'character', word: rest.trim().toLowerCase().replace(/ /g, '_') }
  if (key === 'size') {
    const m = /^([<>])\s*(\d+(?:\.\d+)?)\s*(b|kb|mb|gb)?$/i.exec(rest ?? '')
    if (m) return { id, kind: 'size', op: m[1] as '>' | '<', bytes: Math.round(Number(m[2]) * UNITS[(m[3] ?? 'b').toLowerCase()]) }
  }
  if (key === 'modified') {
    const m = /^([<>])\s*(\d{4}-\d{2}-\d{2})$/.exec(rest ?? '')
    if (m) return { id, kind: 'modified', op: m[1] as '>' | '<', date: m[2] }
  }
  return { id, kind: 'tag', word: t.toLowerCase() }
}

export function labelOf(c: Condition): { key: string; value: string } {
  switch (c.kind) {
    case 'tag':
      return { key: c.negated ? 'not' : 'tag', value: c.word }
    case 'character':
      return { key: c.negated ? 'not chara' : 'chara', value: c.word }
    case 'name':
      return { key: 'name', value: c.text }
    case 'size':
      return { key: 'size', value: `${c.op} ${formatSize(c.bytes)}` }
    case 'modified':
      return { key: 'modified', value: `${c.op === '>' ? 'from' : 'before'} ${c.date}` }
    case 'similar':
      return { key: 'similar to', value: c.name }
  }
}

// Same condition twice adds nothing; a new similar-to replaces the old one, and a tag replaces
// its own opposite, since both together could match nothing.
export function withCondition(list: Condition[], c: Condition): Condition[] {
  if (c.kind === 'similar') return [...list.filter((x) => x.kind !== 'similar'), c]
  if (c.kind === 'tag' || c.kind === 'character')
    list = list.filter((x) => !(x.kind === c.kind && x.word === c.word && !x.negated !== !c.negated))
  const key = JSON.stringify({ ...c, id: 0 })
  return list.some((x) => JSON.stringify({ ...x, id: 0 }) === key) ? list : [...list, c]
}

// Flips a tag or character in place; another chip of the same word, now a duplicate, goes.
export function toggleNegated(list: Condition[], id: number): Condition[] {
  const c = list.find((x) => x.id === id)
  if (c?.kind !== 'tag' && c?.kind !== 'character') return list
  const { negated: _negated, ...rest } = c
  const flipped: Condition = c.negated ? rest : { ...rest, negated: true }
  return list
    .filter((x) => x === c || !(x.kind === c.kind && x.word === c.word))
    .map((x) => (x === c ? flipped : x))
}

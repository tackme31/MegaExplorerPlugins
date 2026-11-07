// WD Tagger packs many words into one MEGA tag (wd:1girl long_hair, chara:a chara:b,
// rating:general); exact matching needs them apart.

export const GENERAL = 0
export const CHARACTER = 1
export const USER = 3

export interface Word {
  kind: number
  word: string
  // Weight in hundredths by place in its tag: WD Tagger writes the most confident word first,
  // so it falls from 100 for the first to 50 for the last (as WD Similar weighs them).
  level: number
}

export interface SplitTags {
  words: Word[]
  rating: number | null
}

const RATING_NAMES = ['general', 'sensitive', 'questionable', 'explicit']

function levelsOf(count: number, i: number): number {
  return count > 1 ? Math.round(100 - (50 * i) / (count - 1)) : 100
}

// Each (kind, word) once, first occurrence kept; words lowercased, as MEGA matches tags
// case-insensitively.
export function splitTags(tags: readonly string[] | null | undefined): SplitTags {
  const words: Word[] = []
  const seen = new Set<string>()
  let rating: number | null = null
  const add = (kind: number, word: string, level: number): void => {
    const w = word.toLowerCase()
    const key = `${kind}\t${w}`
    if (w && !seen.has(key)) {
      seen.add(key)
      words.push({ kind, word: w, level })
    }
  }
  for (const tag of tags ?? []) {
    if (tag.startsWith('wd:')) {
      const list = tag.slice(3).split(' ').filter(Boolean)
      list.forEach((w, i) => add(GENERAL, w, levelsOf(list.length, i)))
    } else if (tag.startsWith('chara:')) {
      const list = tag
        .split(' ')
        .filter((w) => w.startsWith('chara:'))
        .map((w) => w.slice(6))
        .filter(Boolean)
      list.forEach((w, i) => add(CHARACTER, w, levelsOf(list.length, i)))
    } else if (tag.startsWith('rating:')) {
      const r = RATING_NAMES.indexOf(tag.slice(7).trim().toLowerCase())
      if (r >= 0 && rating === null) rating = r
    } else {
      add(USER, tag.trim(), 100)
    }
  }
  return { words, rating }
}

export function ratingName(rating: number | null): string | null {
  return rating === null ? null : (RATING_NAMES[rating] ?? null)
}

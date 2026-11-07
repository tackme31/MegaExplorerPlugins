import { useEffect, useRef, useState } from 'react'
import { Search, Sparkles, X } from 'lucide-react'
import type { Condition } from '../../shared/types'
import { labelOf, newId, parseCondition } from './conditions'
import { thumbnailUrl } from './format'

const CHARACTER_PREFIX = 'chara:'

interface Suggestion {
  kind: 'tag' | 'character'
  word: string
  count: number
}

// Only bare words (tags) and chara: are suggested; the order (exact, prefix, contains, then
// most files) is the index's.
function useSuggestions(text: string): Suggestion[] {
  const [list, setList] = useState<Suggestion[]>([])
  useEffect(() => {
    const t = text.trim().toLowerCase()
    const kind: Suggestion['kind'] = t.startsWith(CHARACTER_PREFIX) ? 'character' : 'tag'
    const query = kind === 'character' ? t.slice(CHARACTER_PREFIX.length) : t
    if (!query || (kind === 'tag' && /^\w+:/.test(t))) {
      setList([])
      return
    }
    let live = true
    window.gallery.suggest(kind, query).then(
      (words) => live && setList(words.map((w) => ({ kind, word: w.word, count: w.files }))),
      () => live && setList([])
    )
    return () => {
      live = false
    }
  }, [text])
  return list
}

function Chip(props: { condition: Condition; onRemove: () => void }) {
  const { key, value } = labelOf(props.condition)
  const c = props.condition
  const tone =
    c.kind === 'similar'
      ? 'bg-violet-500/20 pl-1 text-violet-100 ring-1 ring-violet-400/40'
      : c.kind === 'character'
        ? 'bg-fuchsia-500/15 pl-2.5 text-fuchsia-100'
        : 'bg-white/10 pl-2.5 text-neutral-100'
  return (
    <span className={`flex h-7 max-w-72 shrink-0 items-center gap-1.5 rounded-md pr-1 text-[13px] ${tone}`}>
      {c.kind === 'similar' && (
        <>
          <img src={thumbnailUrl(c.handle)} className="h-5 w-5 rounded-sm bg-neutral-700 object-cover" />
          <Sparkles size={13} className="shrink-0 text-violet-300" />
        </>
      )}
      <span className="shrink-0 text-neutral-400">{key}:</span>
      <span className="truncate">{value}</span>
      <button
        onClick={props.onRemove}
        title="Remove"
        className="grid h-5 w-5 shrink-0 place-items-center rounded text-neutral-400 hover:bg-white/15 hover:text-white"
      >
        <X size={13} />
      </button>
    </span>
  )
}

export function SearchBar(props: {
  conditions: Condition[]
  onAdd: (c: Condition) => void
  onRemove: (id: number) => void
  onClear: () => void
}) {
  const [text, setText] = useState('')
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const suggestions = useSuggestions(text)
  const showList = open && suggestions.length > 0

  function accept(s: Suggestion) {
    props.onAdd({ id: newId(), kind: s.kind, word: s.word })
    setText('')
  }

  function submit() {
    if (showList && suggestions[active]) return accept(suggestions[active])
    const c = parseCondition(text)
    if (c) props.onAdd(c)
    setText('')
  }

  return (
    <div className="relative">
      <div
        onClick={() => input.current?.focus()}
        className="flex min-h-11 cursor-text flex-wrap items-center gap-1.5 rounded-lg bg-neutral-800 px-3 py-2 ring-1 ring-white/10 focus-within:ring-sky-500/70"
      >
        <Search size={17} className="mr-1 shrink-0 text-neutral-400" />
        {props.conditions.map((c) => (
          <Chip key={c.id} condition={c} onRemove={() => props.onRemove(c.id)} />
        ))}
        <input
          ref={input}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              submit()
            } else if (e.key === 'Tab' && showList) {
              e.preventDefault()
              accept(suggestions[active])
            } else if (e.key === 'ArrowDown' && showList) {
              e.preventDefault()
              setActive((a) => (a + 1) % suggestions.length)
            } else if (e.key === 'ArrowUp' && showList) {
              e.preventDefault()
              setActive((a) => (a - 1 + suggestions.length) % suggestions.length)
            } else if (e.key === 'Escape') {
              setOpen(false)
            } else if (e.key === 'Backspace' && !text && props.conditions.length) {
              props.onRemove(props.conditions[props.conditions.length - 1].id)
            }
          }}
          placeholder={props.conditions.length ? '' : 'Tags, chara:…, name:…, size:>1MB, modified:>2025-01-01'}
          className="h-7 min-w-48 flex-1 bg-transparent text-sm text-neutral-100 outline-none placeholder:text-neutral-500"
        />
        {props.conditions.length > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              props.onClear()
            }}
            className="shrink-0 rounded px-2 py-1 text-xs text-neutral-400 hover:bg-white/10 hover:text-white"
          >
            Clear all
          </button>
        )}
      </div>

      {showList && (
        <ul className="absolute top-full left-10 z-40 mt-1 w-80 overflow-hidden rounded-lg bg-neutral-800 py-1 shadow-xl ring-1 ring-white/10">
          {suggestions.map((s, i) => (
            <li
              key={s.word}
              // mousedown, not click: click would come after the input's blur has closed the list.
              onMouseDown={(e) => {
                e.preventDefault()
                accept(s)
              }}
              onMouseEnter={() => setActive(i)}
              className={`flex h-8 cursor-pointer items-center gap-2 px-3 text-sm ${
                i === active ? 'bg-sky-600/40 text-white' : 'text-neutral-200'
              }`}
            >
              {s.kind === 'character' && <span className="text-fuchsia-300">chara:</span>}
              <span className="flex-1 truncate">{s.word}</span>
              <span className="text-xs text-neutral-400 tabular-nums">{s.count.toLocaleString()}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

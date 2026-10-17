// The image area. Holds at most two layers — the image arriving and the one leaving — and
// animates them with the Web Animations API, so a transition is just two element.animate()
// calls and needs no CSS state classes.

import { useLayoutEffect, useRef } from 'react'
import type { Fit, Transition } from '@shared/types'

export interface Slide {
  // Unique per showing, not per image: the same image shown again must mount a new layer.
  key: number
  src: string
  // +1 when moving forward, -1 backward; decides which way a slide transition runs.
  direction: 1 | -1
}

interface Props {
  current: Slide | null
  leaving: Slide | null
  fit: Fit
  transition: Transition
  durationMs: number
}

function keyframes(transition: Transition, direction: number, entering: boolean): Keyframe[] {
  const shift = `${direction * (entering ? 6 : -6)}%`
  switch (transition) {
    case 'slide':
      return entering
        ? [{ opacity: 0, transform: `translateX(${shift})` }, { opacity: 1, transform: 'none' }]
        : [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: `translateX(${shift})` }]
    case 'zoom':
      return entering
        ? [{ opacity: 0, transform: 'scale(1.06)' }, { opacity: 1, transform: 'none' }]
        : [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(0.97)' }]
    default:
      return entering ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 1 }, { opacity: 0 }]
  }
}

function Layer(props: { slide: Slide; entering: boolean; fit: Fit; transition: Transition; durationMs: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const { slide, entering, transition, durationMs } = props
  useLayoutEffect(() => {
    if (transition === 'none' || !ref.current) return
    const animation = ref.current.animate(keyframes(transition, slide.direction, entering), {
      duration: durationMs,
      easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
      fill: 'forwards'
    })
    return () => animation.cancel()
  }, [entering, transition, durationMs, slide.direction])

  const image =
    props.fit === 'cover'
      ? 'h-full w-full object-cover'
      : props.fit === 'actual'
        ? 'max-w-none'
        : // max-* rather than w/h-full: an image smaller than the window stays at its own size.
          'max-h-full max-w-full object-contain'
  return (
    <div ref={ref} className="absolute inset-0 flex items-center justify-center overflow-hidden">
      <img src={props.slide.src} className={`${image} select-none`} draggable={false} alt="" />
    </div>
  )
}

export function Stage({ current, leaving, fit, transition, durationMs }: Props) {
  return (
    <div className="absolute inset-0">
      {leaving && transition !== 'none' && (
        <Layer key={leaving.key} slide={leaving} entering={false} fit={fit} transition={transition} durationMs={durationMs} />
      )}
      {current && (
        <Layer key={current.key} slide={current} entering fit={fit} transition={transition} durationMs={durationMs} />
      )}
    </div>
  )
}

import { clsx } from 'clsx'

interface BadgeProps {
  label: string
  className?: string
  size?: 'sm' | 'md'
}

export function Badge({ label, className, size = 'sm' }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full font-medium whitespace-nowrap',
        size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs',
        className,
      )}
    >
      {label}
    </span>
  )
}

interface ScorePillProps {
  score: number | null
}

export function ScorePill({ score }: ScorePillProps) {
  if (score === null) return <span className="text-slate-300 text-xs">—</span>
  const rounded = Math.round(score * 10) / 10

  let bg = 'bg-green-100 text-green-700'
  if (rounded >= 4.5) bg = 'bg-red-100 text-red-700'
  else if (rounded >= 3.5) bg = 'bg-orange-100 text-orange-700'
  else if (rounded >= 2.5) bg = 'bg-amber-100 text-amber-700'
  else if (rounded >= 1.5) bg = 'bg-lime-100 text-lime-700'

  return (
    <span className={clsx('inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-bold tabular-nums', bg)}>
      {rounded.toFixed(1)}
      <span className="font-normal text-[10px] opacity-60">/5</span>
    </span>
  )
}

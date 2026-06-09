import { clsx } from 'clsx'

interface BadgeProps {
  label: string
  className?: string
  size?: 'sm' | 'md'
}

export function Badge({ label, className, size = 'sm' }: BadgeProps) {
  return (
    <span className={clsx(
      'inline-flex items-center rounded-full font-semibold whitespace-nowrap leading-none',
      size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-2.5 py-1 text-xs',
      className,
    )}>
      {label}
    </span>
  )
}

export function ScorePill({ score }: { score: number | null }) {
  if (score === null) return <span className="text-[#c3c6d4] text-xs font-medium">—</span>
  const rounded = Math.round(score * 10) / 10

  let bg = '#d4f4e2'; let color = '#007038'
  if (rounded >= 4.5) { bg = '#ffd3d9'; color = '#c0253d' }
  else if (rounded >= 3.5) { bg = '#ffe5b4'; color = '#c47c00' }
  else if (rounded >= 2.5) { bg = '#fff3cd'; color = '#8a6300' }
  else if (rounded >= 1.5) { bg = '#d4f4e2'; color = '#007038' }

  return (
    <span
      className="inline-flex items-center gap-0.5 rounded-full px-2 py-1 text-xs font-bold tabular-nums leading-none"
      style={{ background: bg, color }}
    >
      {rounded.toFixed(1)}
      <span className="font-normal text-[10px] opacity-60">/5</span>
    </span>
  )
}

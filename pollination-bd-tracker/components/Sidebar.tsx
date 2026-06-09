'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Flame, Building2, Kanban } from 'lucide-react'

const NAV = [
  { href: '/', label: 'Hot Sheet', icon: Flame },
  { href: '/companies', label: 'Companies', icon: Building2 },
  { href: '/pipeline', label: 'Pipeline', icon: Kanban },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-56 flex-shrink-0 bg-[#00579B] flex flex-col h-full">
      {/* Logo / wordmark */}
      <div className="px-5 pt-6 pb-4 border-b border-white/10">
        <p className="text-white/60 text-[10px] uppercase tracking-widest font-semibold">Pollination</p>
        <h1 className="text-white font-bold text-base leading-tight mt-0.5">BD Tracker</h1>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? 'bg-white/15 text-white font-semibold'
                  : 'text-white/70 hover:text-white hover:bg-white/10'
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/10">
        <p className="text-white/40 text-[10px]">ASRS BD Intelligence</p>
        <p className="text-white/25 text-[10px]">June 2026</p>
      </div>
    </aside>
  )
}

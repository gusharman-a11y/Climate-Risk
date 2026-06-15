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
    <header className="h-14 bg-white border-b border-slate-200 flex items-center px-6 gap-8 sticky top-0 z-20 w-full">
      {/* Wordmark */}
      <span className="font-bold text-slate-900 text-sm tracking-tight shrink-0">BD Tracker</span>

      {/* Nav */}
      <nav className="flex items-center gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${
                active
                  ? 'bg-[#0073ea]/10 text-[#0073ea] font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Icon size={15} />
              {label}
            </Link>
          )
        })}
      </nav>
    </header>
  )
}

'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Flame, Building2, Kanban } from 'lucide-react'

const NAV = [
  { href: '/', label: 'Hot Sheet', icon: Flame },
  { href: '/companies', label: 'Companies', icon: Building2 },
  { href: '/pipeline', label: 'Pipeline', icon: Kanban },
]

export default function TopNav() {
  const pathname = usePathname()

  return (
    <header className="h-14 bg-white border-b border-[#e6e9ef] flex items-center px-5 gap-6 sticky top-0 z-20 shadow-[0_2px_4px_rgba(0,0,0,0.04)]">
      {/* Logo */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="w-7 h-7 rounded-lg bg-[#0073ea] flex items-center justify-center">
          <span className="text-white font-extrabold text-xs">BD</span>
        </div>
        <span className="font-bold text-[#323338] text-sm hidden sm:block">BD Tracker</span>
      </div>

      {/* Divider */}
      <div className="h-6 w-px bg-[#e6e9ef]" />

      {/* Nav links */}
      <nav className="flex items-center gap-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-all ${
                active
                  ? 'text-[#0073ea] bg-[#cce5ff]/40'
                  : 'text-[#676879] hover:text-[#323338] hover:bg-[#f6f7fb]'
              }`}
            >
              <Icon size={15} strokeWidth={active ? 2.5 : 2} />
              {label}
            </Link>
          )
        })}
      </nav>
    </header>
  )
}

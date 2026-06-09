'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronRight, Search, Filter } from 'lucide-react'
import type { Company, AsrsGroup } from '@/lib/types'
import { asrsGroupBadge, relationshipBadge, scoreRowClass } from '@/lib/types'
import { Badge, ScorePill } from '@/components/Badge'

interface Props {
  companies: Company[]
}

const GROUPS: AsrsGroup[] = ['Group 1', 'Group 2', 'Group 3', 'Unclassified']

const GROUP_DESCRIPTIONS: Record<AsrsGroup, string> = {
  'Group 1': 'Mandatory NOW — FY2025/26',
  'Group 2': 'Mandatory FY2026/27',
  'Group 3': 'Mandatory FY2027/28',
  'Unclassified': 'Group unconfirmed',
}

export default function HotSheetClient({ companies }: Props) {
  const [search, setSearch] = useState('')
  const [sectorFilter, setSectorFilter] = useState('')
  const [minScore, setMinScore] = useState(0)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const sectors = useMemo(() => {
    const s = [...new Set(companies.map(c => c.sector).filter(Boolean))] as string[]
    return s.sort()
  }, [companies])

  const filtered = useMemo(() => {
    return companies.filter(c => {
      if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
      if (sectorFilter && c.sector !== sectorFilter) return false
      if (minScore && (c.score_overall ?? 0) < minScore) return false
      return true
    })
  }, [companies, search, sectorFilter, minScore])

  const grouped = useMemo(() => {
    return GROUPS.reduce<Record<string, Company[]>>((acc, g) => {
      acc[g] = filtered.filter(c => c.asrs_group === g)
      return acc
    }, {} as Record<string, Company[]>)
  }, [filtered])

  const toggleGroup = (g: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      next.has(g) ? next.delete(g) : next.add(g)
      return next
    })
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="border-b border-slate-200 bg-white px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div>
          <h1 className="text-lg font-bold text-slate-900">Hot Sheet</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {filtered.length} prospects · ranked by BD score
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search companies..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm border border-slate-200 rounded-md w-52 focus:outline-none focus:ring-2 focus:ring-[#00579B]/30"
            />
          </div>
          {/* Sector filter */}
          <div className="relative flex items-center gap-1.5">
            <Filter size={14} className="text-slate-400" />
            <select
              value={sectorFilter}
              onChange={e => setSectorFilter(e.target.value)}
              className="text-sm border border-slate-200 rounded-md py-1.5 px-2 focus:outline-none focus:ring-2 focus:ring-[#00579B]/30 bg-white"
            >
              <option value="">All sectors</option>
              {sectors.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {/* Min score */}
          <select
            value={minScore}
            onChange={e => setMinScore(Number(e.target.value))}
            className="text-sm border border-slate-200 rounded-md py-1.5 px-2 focus:outline-none focus:ring-2 focus:ring-[#00579B]/30 bg-white"
          >
            <option value={0}>All scores</option>
            <option value={3}>Score ≥ 3</option>
            <option value={4}>Score ≥ 4</option>
            <option value={4.5}>Score ≥ 4.5</option>
          </select>
        </div>
      </div>

      {/* Table header */}
      <div className="sticky top-[73px] z-10 bg-slate-50 border-b border-slate-200 grid grid-cols-[3fr_1fr_1fr_2fr_1fr_1fr] gap-0 px-6 py-2">
        {['Company', 'Score', 'ASRS Group', 'Top Signal', 'Sector', 'Relationship'].map(h => (
          <span key={h} className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">{h}</span>
        ))}
      </div>

      {/* Grouped rows */}
      <div className="flex-1">
        {GROUPS.map(group => {
          const rows = grouped[group]
          if (!rows?.length) return null
          const isCollapsed = collapsed.has(group)
          const gb = asrsGroupBadge(group)

          return (
            <div key={group}>
              {/* Group header — Monday-style */}
              <button
                onClick={() => toggleGroup(group)}
                className="w-full flex items-center gap-3 px-6 py-2.5 bg-slate-50 border-b border-slate-200 hover:bg-slate-100 transition-colors text-left"
              >
                {isCollapsed ? <ChevronRight size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                <Badge label={group} className={gb.className} />
                <span className="text-xs text-slate-500">{GROUP_DESCRIPTIONS[group]}</span>
                <span className="ml-auto text-xs font-semibold text-slate-600">{rows.length} companies</span>
              </button>

              {/* Rows */}
              {!isCollapsed && rows.map(company => {
                const rb = relationshipBadge(company.relationship_status)
                const gb2 = asrsGroupBadge(company.asrs_group)
                const scoreClass = scoreRowClass(company.score_overall)

                return (
                  <Link
                    key={company.id}
                    href={`/companies/${company.id}`}
                    className={`grid grid-cols-[3fr_1fr_1fr_2fr_1fr_1fr] gap-0 px-6 py-3 border-b border-slate-100 hover:bg-blue-50/40 transition-colors items-center ${scoreClass} pl-5`}
                  >
                    {/* Company name */}
                    <div>
                      <p className="text-sm font-medium text-slate-900 truncate">{company.name}</p>
                      {company.asx_code && (
                        <p className="text-[11px] text-slate-400 font-mono">{company.asx_code}</p>
                      )}
                    </div>

                    {/* Score */}
                    <div>
                      <ScorePill score={company.score_overall} />
                    </div>

                    {/* ASRS group */}
                    <div>
                      <Badge label={gb2.label} className={gb2.className} />
                    </div>

                    {/* Top signal */}
                    <div>
                      <p className="text-xs text-slate-600 truncate max-w-[220px]">
                        {company.top_signal ?? '—'}
                      </p>
                    </div>

                    {/* Sector */}
                    <div>
                      <p className="text-xs text-slate-500 truncate">{company.sector ?? '—'}</p>
                    </div>

                    {/* Relationship */}
                    <div>
                      <Badge label={rb.label} className={rb.className} />
                      {company.relationship_lead && (
                        <p className="text-[10px] text-slate-400 mt-0.5 truncate">{company.relationship_lead}</p>
                      )}
                    </div>
                  </Link>
                )
              })}
            </div>
          )
        })}

        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-slate-400">
            <p className="text-sm">No companies match your filters.</p>
          </div>
        )}
      </div>
    </div>
  )
}

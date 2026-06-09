'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronRight, Search } from 'lucide-react'
import type { Company, AsrsGroup } from '@/lib/types'
import { asrsGroupBadge, relationshipBadge, scoreRowClass } from '@/lib/types'
import { Badge, ScorePill } from '@/components/Badge'

interface Props { companies: Company[] }

const GROUPS: AsrsGroup[] = ['Group 1', 'Group 2', 'Group 3', 'Unclassified']

const GROUP_META: Record<AsrsGroup, { label: string; sub: string; dot: string }> = {
  'Group 1': { label: 'Group 1', sub: 'Mandatory NOW — FY2025/26', dot: '#e2445c' },
  'Group 2': { label: 'Group 2', sub: 'Mandatory FY2026/27', dot: '#fdab3d' },
  'Group 3': { label: 'Group 3', sub: 'Mandatory FY2027/28', dot: '#ffcb00' },
  'Unclassified': { label: 'Unclassified', sub: 'Group unconfirmed', dot: '#c3c6d4' },
}

const COLS = ['Company', 'Score', 'ASRS Group', 'Top Signal', 'Sector', 'Relationship']

export default function HotSheetClient({ companies }: Props) {
  const [search, setSearch] = useState('')
  const [sectorFilter, setSectorFilter] = useState('')
  const [minScore, setMinScore] = useState(0)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const sectors = useMemo(() => {
    return [...new Set(companies.map(c => c.sector).filter(Boolean))] .sort() as string[]
  }, [companies])

  const filtered = useMemo(() => companies.filter(c => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
    if (sectorFilter && c.sector !== sectorFilter) return false
    if (minScore && (c.score_overall ?? 0) < minScore) return false
    return true
  }), [companies, search, sectorFilter, minScore])

  const grouped = useMemo(() => GROUPS.reduce<Record<string, Company[]>>((acc, g) => {
    acc[g] = filtered.filter(c => c.asrs_group === g)
    return acc
  }, {} as Record<string, Company[]>), [filtered])

  const toggle = (g: string) => setCollapsed(prev => {
    const next = new Set(prev)
    next.has(g) ? next.delete(g) : next.add(g)
    return next
  })

  return (
    <div>
      {/* Page header */}
      <div className="bg-white border-b border-[#e6e9ef] px-6 py-3 flex items-center justify-between sticky top-14 z-10">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-700 text-[#323338] font-bold">Hot Sheet</h1>
          <span className="text-xs text-[#676879] bg-[#f6f7fb] px-2 py-0.5 rounded-full border border-[#e6e9ef]">
            {filtered.length} prospects
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#c3c6d4]" />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm border border-[#e6e9ef] rounded-md w-44 focus:outline-none focus:border-[#0073ea] focus:ring-2 focus:ring-[#0073ea]/20 bg-white text-[#323338] placeholder:text-[#c3c6d4]"
            />
          </div>

          {/* Sector */}
          <select
            value={sectorFilter}
            onChange={e => setSectorFilter(e.target.value)}
            className="text-sm border border-[#e6e9ef] rounded-md py-1.5 px-2.5 focus:outline-none focus:border-[#0073ea] bg-white text-[#323338]"
          >
            <option value="">All sectors</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {/* Min score */}
          <select
            value={minScore}
            onChange={e => setMinScore(Number(e.target.value))}
            className="text-sm border border-[#e6e9ef] rounded-md py-1.5 px-2.5 focus:outline-none focus:border-[#0073ea] bg-white text-[#323338]"
          >
            <option value={0}>All scores</option>
            <option value={3}>≥ 3.0</option>
            <option value={4}>≥ 4.0</option>
            <option value={4.5}>≥ 4.5</option>
          </select>
        </div>
      </div>

      {/* Column headers */}
      <div className="sticky top-[105px] z-10 bg-[#f6f7fb] border-b border-[#e6e9ef] grid grid-cols-[2.5fr_80px_110px_2fr_1fr_130px] px-6 py-2 gap-2">
        {COLS.map(h => (
          <span key={h} className="text-[11px] font-600 font-semibold text-[#676879] uppercase tracking-wide">{h}</span>
        ))}
      </div>

      {/* Groups */}
      {GROUPS.map(group => {
        const rows = grouped[group]
        if (!rows?.length) return null
        const meta = GROUP_META[group]
        const isCollapsed = collapsed.has(group)

        return (
          <div key={group}>
            {/* Group header — Monday style with coloured dot */}
            <button
              onClick={() => toggle(group)}
              className="w-full flex items-center gap-3 px-6 py-2 bg-white border-b border-[#e6e9ef] hover:bg-[#f6f7fb] transition-colors text-left"
              style={{ borderLeft: `3px solid ${meta.dot}` }}
            >
              <span className="text-slate-400 w-4 flex-shrink-0">
                {isCollapsed
                  ? <ChevronRight size={14} />
                  : <ChevronDown size={14} />
                }
              </span>
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ background: meta.dot }}
              />
              <span className="text-sm font-semibold text-[#323338]">{meta.label}</span>
              <span className="text-xs text-[#676879]">{meta.sub}</span>
              <span className="ml-auto text-xs font-semibold text-[#676879]">
                {rows.length} {rows.length === 1 ? 'company' : 'companies'}
              </span>
            </button>

            {/* Rows */}
            {!isCollapsed && rows.map((company, i) => {
              const rb = relationshipBadge(company.relationship_status)
              const gb = asrsGroupBadge(company.asrs_group)
              const scoreClass = scoreRowClass(company.score_overall)

              return (
                <Link
                  key={company.id}
                  href={`/companies/${company.id}`}
                  className={`grid grid-cols-[2.5fr_80px_110px_2fr_1fr_130px] px-6 py-0 gap-2 border-b border-[#e6e9ef] hover:bg-[#e8f0fd]/30 transition-colors items-stretch ${scoreClass} ${i % 2 === 0 ? 'bg-white' : 'bg-[#fafbff]'}`}
                >
                  {/* Company */}
                  <div className="flex flex-col justify-center py-2.5 min-w-0">
                    <p className="text-sm font-semibold text-[#323338] truncate leading-tight">{company.name}</p>
                    {company.asx_code && (
                      <p className="text-[11px] text-[#676879] font-mono mt-0.5">{company.asx_code}</p>
                    )}
                  </div>

                  {/* Score */}
                  <div className="flex items-center">
                    <ScorePill score={company.score_overall} />
                  </div>

                  {/* ASRS group */}
                  <div className="flex items-center">
                    <Badge label={gb.label} className={gb.className} />
                  </div>

                  {/* Top signal */}
                  <div className="flex items-center min-w-0">
                    <p className="text-xs text-[#676879] truncate">{company.top_signal ?? '—'}</p>
                  </div>

                  {/* Sector */}
                  <div className="flex items-center min-w-0">
                    <p className="text-xs text-[#676879] truncate">{company.sector ?? '—'}</p>
                  </div>

                  {/* Relationship */}
                  <div className="flex flex-col justify-center gap-0.5">
                    <Badge label={rb.label} className={rb.className} />
                    {company.relationship_lead && (
                      <p className="text-[10px] text-[#676879] truncate">{company.relationship_lead}</p>
                    )}
                  </div>
                </Link>
              )
            })}
          </div>
        )
      })}

      {filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-[#676879]">
          <p className="text-sm">No companies match your filters.</p>
        </div>
      )}
    </div>
  )
}

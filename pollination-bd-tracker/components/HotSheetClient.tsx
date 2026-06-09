'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronRight, Search } from 'lucide-react'
import type { Company, AsrsGroup } from '@/lib/types'
import { asrsGroupBadge, relationshipBadge, scoreRowClass } from '@/lib/types'
import { Badge, ScorePill } from '@/components/Badge'

interface Props {
  companies: Company[]
  sbtiV2Companies: Company[]
}

// ── ASRS groups ───────────────────────────────────────────────────────────────
const ASRS_GROUPS: AsrsGroup[] = ['Group 1', 'Group 2', 'Group 3']

const GROUP_META: Record<AsrsGroup, { sub: string; dot: string }> = {
  'Group 1': { sub: 'Mandatory NOW — FY2025/26', dot: '#e2445c' },
  'Group 2': { sub: 'Mandatory FY2026/27', dot: '#fdab3d' },
  'Group 3': { sub: 'Mandatory FY2027/28', dot: '#ffcb00' },
  'Unclassified': { sub: 'Group unconfirmed', dot: '#c3c6d4' },
}

// ── Shared row component ──────────────────────────────────────────────────────
function CompanyRow({ company, i }: { company: Company; i: number }) {
  const rb = relationshipBadge(company.relationship_status)
  const gb = asrsGroupBadge(company.asrs_group)
  const scoreClass = scoreRowClass(company.score_overall)

  return (
    <Link
      key={company.id}
      href={`/companies/${company.id}`}
      className={`grid grid-cols-[2.5fr_80px_110px_2fr_1fr_130px] px-6 py-0 gap-2 border-b border-[#e6e9ef] hover:bg-[#e8f0fd]/30 transition-colors items-stretch ${scoreClass} ${i % 2 === 0 ? 'bg-white' : 'bg-[#fafbff]'}`}
    >
      <div className="flex flex-col justify-center py-2.5 min-w-0">
        <p className="text-sm font-semibold text-[#323338] truncate leading-tight">{company.name}</p>
        {company.asx_code && <p className="text-[11px] text-[#676879] font-mono mt-0.5">{company.asx_code}</p>}
      </div>
      <div className="flex items-center"><ScorePill score={company.score_overall} /></div>
      <div className="flex items-center"><Badge label={gb.label} className={gb.className} /></div>
      <div className="flex items-center min-w-0">
        <p className="text-xs text-[#676879] truncate">{company.top_signal ?? '—'}</p>
      </div>
      <div className="flex items-center min-w-0">
        <p className="text-xs text-[#676879] truncate">{company.sector ?? '—'}</p>
      </div>
      <div className="flex flex-col justify-center gap-0.5">
        <Badge label={rb.label} className={rb.className} />
        {company.relationship_lead && (
          <p className="text-[10px] text-[#676879] truncate">{company.relationship_lead}</p>
        )}
      </div>
    </Link>
  )
}

// ── SBTi V2 row — different columns ──────────────────────────────────────────
function SbtiV2Row({ company, i }: { company: Company; i: number }) {
  const rb = relationshipBadge(company.relationship_status)
  const gb = asrsGroupBadge(company.asrs_group)
  const dateStr = company.sbti_date_updated ? company.sbti_date_updated.slice(0, 7) : '—'
  const yr = company.sbti_date_updated ? parseInt(company.sbti_date_updated.slice(0, 4)) : null
  const urgency = yr && yr < 2021 ? 'bg-[#ffd3d9] text-[#c0253d]' : yr && yr < 2023 ? 'bg-[#ffe5b4] text-[#c47c00]' : 'bg-[#f6f7fb] text-[#676879]'

  return (
    <Link
      href={`/companies/${company.id}`}
      className={`grid grid-cols-[2.5fr_100px_110px_2fr_1fr_130px] px-6 py-0 gap-2 border-b border-[#e6e9ef] hover:bg-[#e8f0fd]/30 transition-colors items-stretch border-l-[3px] border-l-[#a25ddc] ${i % 2 === 0 ? 'bg-white' : 'bg-[#fafbff]'}`}
    >
      <div className="flex flex-col justify-center py-2.5 min-w-0">
        <p className="text-sm font-semibold text-[#323338] truncate leading-tight">{company.name}</p>
        {company.asx_code && <p className="text-[11px] text-[#676879] font-mono mt-0.5">{company.asx_code}</p>}
      </div>
      <div className="flex items-center">
        <span className={`text-xs font-bold px-2 py-1 rounded-full ${urgency}`}>{dateStr}</span>
      </div>
      <div className="flex items-center"><Badge label={gb.label} className={gb.className} /></div>
      <div className="flex items-center min-w-0">
        <p className="text-xs text-[#676879] truncate">{company.sector ?? '—'}</p>
      </div>
      <div className="flex items-center">
        <ScorePill score={company.score_overall} />
      </div>
      <div className="flex flex-col justify-center gap-0.5">
        <Badge label={rb.label} className={rb.className} />
        {company.relationship_lead && (
          <p className="text-[10px] text-[#676879] truncate">{company.relationship_lead}</p>
        )}
      </div>
    </Link>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function HotSheetClient({ companies, sbtiV2Companies }: Props) {
  const [search, setSearch] = useState('')
  const [sectorFilter, setSectorFilter] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [sbtiFilter, setSbtiFilter] = useState('')
  const [minScore, setMinScore] = useState(0)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set(['sbti-v2']))

  const sectors = useMemo(() =>
    [...new Set(companies.map(c => c.sector).filter(Boolean))].sort() as string[]
  , [companies])

  const matchesSbti = (c: Company) => {
    if (!sbtiFilter) return true
    const s = (c.sbti_status ?? '').toLowerCase()
    if (sbtiFilter === 'none') return !c.sbti_status || s === ''
    if (sbtiFilter === 'removed') return s.includes('removed')
    if (sbtiFilter === 'committed') return s.includes('committed') && !s.includes('removed')
    if (sbtiFilter === 'validated') return s.includes('targets set')
    return true
  }

  const filtered = useMemo(() => companies.filter(c => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
    if (sectorFilter && c.sector !== sectorFilter) return false
    if (groupFilter && c.asrs_group !== groupFilter) return false
    if (!matchesSbti(c)) return false
    if (minScore && (c.score_overall ?? 0) < minScore) return false
    return true
  }), [companies, search, sectorFilter, groupFilter, sbtiFilter, minScore])

  const filteredV2 = useMemo(() => sbtiV2Companies.filter(c => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
    if (sectorFilter && c.sector !== sectorFilter) return false
    if (groupFilter && c.asrs_group !== groupFilter) return false
    return true
  }), [sbtiV2Companies, search, sectorFilter, groupFilter])

  const grouped = useMemo(() => ASRS_GROUPS.reduce<Record<string, Company[]>>((acc, g) => {
    acc[g] = filtered.filter(c => c.asrs_group === g)
    return acc
  }, {} as Record<string, Company[]>), [filtered])

  const toggle = (g: string) => setCollapsed(prev => {
    const next = new Set(prev)
    next.has(g) ? next.delete(g) : next.add(g)
    return next
  })

  // Auto-expand SBTi V2 group when validated filter applied
  const handleSbtiFilter = (val: string) => {
    setSbtiFilter(val)
    if (val === 'validated') {
      setCollapsed(prev => { const next = new Set(prev); next.delete('sbti-v2'); return next })
    }
  }

  const totalShown = filtered.length + filteredV2.length

  return (
    <div>
      {/* Page header */}
      <div className="bg-white border-b border-[#e6e9ef] px-6 py-3 flex items-center justify-between sticky top-14 z-10">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-bold text-[#323338]">Hot Sheet</h1>
          <span className="text-xs text-[#676879] bg-[#f6f7fb] px-2 py-0.5 rounded-full border border-[#e6e9ef]">
            {totalShown} prospects
          </span>
        </div>
        <div className="flex items-center gap-2">
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
          {/* ASRS Group filter */}
          <select value={groupFilter} onChange={e => setGroupFilter(e.target.value)}
            className="text-sm border border-[#e6e9ef] rounded-md py-1.5 px-2.5 focus:outline-none focus:border-[#0073ea] bg-white text-[#323338]">
            <option value="">All groups</option>
            <option value="Group 1">Group 1</option>
            <option value="Group 2">Group 2</option>
            <option value="Group 3">Group 3</option>
          </select>

          {/* SBTi filter */}
          <select value={sbtiFilter} onChange={e => handleSbtiFilter(e.target.value)}
            className="text-sm border border-[#e6e9ef] rounded-md py-1.5 px-2.5 focus:outline-none focus:border-[#0073ea] bg-white text-[#323338]">
            <option value="">All SBTi</option>
            <option value="none">No SBTi</option>
            <option value="committed">Committed</option>
            <option value="validated">Validated</option>
            <option value="removed">Removed</option>
          </select>

          <select value={sectorFilter} onChange={e => setSectorFilter(e.target.value)}
            className="text-sm border border-[#e6e9ef] rounded-md py-1.5 px-2.5 focus:outline-none focus:border-[#0073ea] bg-white text-[#323338]">
            <option value="">All sectors</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={minScore} onChange={e => setMinScore(Number(e.target.value))}
            className="text-sm border border-[#e6e9ef] rounded-md py-1.5 px-2.5 focus:outline-none focus:border-[#0073ea] bg-white text-[#323338]">
            <option value={0}>All scores</option>
            <option value={3}>≥ 3.0</option>
            <option value={4}>≥ 4.0</option>
            <option value={4.5}>≥ 4.5</option>
          </select>
        </div>
      </div>

      {/* Column headers — main groups */}
      <div className="sticky top-[105px] z-10 bg-[#f6f7fb] border-b border-[#e6e9ef] grid grid-cols-[2.5fr_80px_110px_2fr_1fr_130px] px-6 py-2 gap-2">
        {['Company', 'Score', 'ASRS Group', 'Top Signal', 'Sector', 'Relationship'].map(h => (
          <span key={h} className="text-[11px] font-semibold text-[#676879] uppercase tracking-wide">{h}</span>
        ))}
      </div>

      {/* ASRS groups */}
      {ASRS_GROUPS.map(group => {
        const rows = grouped[group]
        if (!rows?.length) return null
        const meta = GROUP_META[group]
        const isCollapsed = collapsed.has(group)

        return (
          <div key={group}>
            <button
              onClick={() => toggle(group)}
              className="w-full flex items-center gap-3 px-6 py-2 bg-white border-b border-[#e6e9ef] hover:bg-[#f6f7fb] transition-colors text-left"
              style={{ borderLeft: `3px solid ${meta.dot}` }}
            >
              <span className="text-[#c3c6d4] w-4 shrink-0">
                {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
              </span>
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: meta.dot }} />
              <span className="text-sm font-semibold text-[#323338]">{group}</span>
              <span className="text-xs text-[#676879]">{meta.sub}</span>
              <span className="ml-auto text-xs font-semibold text-[#676879]">{rows.length} companies</span>
            </button>
            {!isCollapsed && rows.map((c, i) => <CompanyRow key={c.id} company={c} i={i} />)}
          </div>
        )
      })}

      {/* SBTi V2 Refresh group */}
      {filteredV2.length > 0 && (() => {
        const isCollapsed = collapsed.has('sbti-v2')
        const pre2023 = filteredV2.filter(c => c.sbti_date_updated && c.sbti_date_updated < '2023-01-01').length
        return (
          <div>
            {/* Different column headers for V2 group */}
            <button
              onClick={() => toggle('sbti-v2')}
              className="w-full flex items-center gap-3 px-6 py-2 bg-white border-b border-[#e6e9ef] hover:bg-[#f6f7fb] transition-colors text-left"
              style={{ borderLeft: '3px solid #a25ddc' }}
            >
              <span className="text-[#c3c6d4] w-4 shrink-0">
                {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
              </span>
              <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-[#a25ddc]" />
              <span className="text-sm font-semibold text-[#323338]">SBTi Validated — V2 Refresh Needed</span>
              <span className="text-xs text-[#676879]">Validated under old standard — SBTi V2 requires resubmission</span>
              {pre2023 > 0 && (
                <span className="ml-2 text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#ede3f9] text-[#7b3db8]">
                  {pre2023} pre-2023
                </span>
              )}
              <span className="ml-auto text-xs font-semibold text-[#676879]">{filteredV2.length} companies</span>
            </button>

            {!isCollapsed && (
              <>
                {/* V2-specific column headers */}
                <div className="bg-[#f6f7fb] border-b border-[#e6e9ef] grid grid-cols-[2.5fr_100px_110px_2fr_1fr_130px] px-6 py-2 gap-2">
                  {['Company', 'Validated', 'ASRS Group', 'Sector', 'Score', 'Relationship'].map(h => (
                    <span key={h} className="text-[11px] font-semibold text-[#676879] uppercase tracking-wide">{h}</span>
                  ))}
                </div>
                {filteredV2.map((c, i) => <SbtiV2Row key={c.id} company={c} i={i} />)}
              </>
            )}
          </div>
        )
      })()}

      {totalShown === 0 && (
        <div className="flex items-center justify-center py-32 text-[#676879]">
          <p className="text-sm">No companies match your filters.</p>
        </div>
      )}
    </div>
  )
}

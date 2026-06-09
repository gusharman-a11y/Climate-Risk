'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { Search } from 'lucide-react'
import type { Company } from '@/lib/types'
import { asrsGroupBadge, relationshipBadge } from '@/lib/types'
import { Badge, ScorePill } from '@/components/Badge'

interface Props { companies: Company[] }

const SELECT = 'text-sm border border-[#e6e9ef] rounded-md py-1.5 px-2.5 bg-white text-[#323338] focus:outline-none focus:border-[#0073ea]'

function SbtiPill({ status }: { status: string | null }) {
  if (!status) return <span className="text-xs text-[#c3c6d4]">—</span>
  const s = status.toLowerCase()
  const cls = s.includes('targets set') ? 'bg-[#d4f4e2] text-[#007038]' :
               s.includes('committed') && !s.includes('removed') ? 'bg-[#cce5ff] text-[#0060c0]' :
               s.includes('removed') ? 'bg-[#ffd3d9] text-[#c0253d]' :
               'bg-[#f6f7fb] text-[#676879]'
  return <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${cls}`}>{status}</span>
}

export default function CompaniesClient({ companies }: Props) {
  const [search, setSearch] = useState('')
  const [sectorFilter, setSectorFilter] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [relFilter, setRelFilter] = useState('')
  const [sbtiFilter, setSbtiFilter] = useState('')

  const sectors = useMemo(() =>
    [...new Set(companies.map(c => c.sector).filter(Boolean))].sort() as string[]
  , [companies])

  const filtered = useMemo(() => companies.filter(c => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase()) &&
        !(c.asx_code ?? '').toLowerCase().includes(search.toLowerCase())) return false
    if (sectorFilter && c.sector !== sectorFilter) return false
    if (groupFilter && c.asrs_group !== groupFilter) return false
    if (relFilter && c.relationship_status !== relFilter) return false
    if (sbtiFilter) {
      const s = (c.sbti_status ?? '').toLowerCase()
      if (sbtiFilter === 'none' && c.sbti_status) return false
      if (sbtiFilter === 'removed' && !s.includes('removed')) return false
      if (sbtiFilter === 'committed' && (!s.includes('committed') || s.includes('removed'))) return false
      if (sbtiFilter === 'validated' && !s.includes('targets set')) return false
    }
    return true
  }), [companies, search, sectorFilter, groupFilter, relFilter, sbtiFilter])

  return (
    <div>
      {/* Page header */}
      <div className="bg-white border-b border-[#e6e9ef] px-6 py-3 flex items-center justify-between sticky top-14 z-10 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-bold text-[#323338]">Companies</h1>
          <span className="text-xs text-[#676879] bg-[#f6f7fb] px-2 py-0.5 rounded-full border border-[#e6e9ef]">
            {filtered.length} of {companies.length}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#c3c6d4]" />
            <input type="text" placeholder="Search name or ASX code..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm border border-[#e6e9ef] rounded-md w-52 focus:outline-none focus:border-[#0073ea] focus:ring-2 focus:ring-[#0073ea]/20 bg-white text-[#323338] placeholder:text-[#c3c6d4]" />
          </div>
          <select value={groupFilter} onChange={e => setGroupFilter(e.target.value)} className={SELECT}>
            <option value="">All groups</option>
            <option value="Group 1">Group 1</option>
            <option value="Group 2">Group 2</option>
            <option value="Group 3">Group 3</option>
            <option value="Unclassified">Unclassified</option>
          </select>
          <select value={sbtiFilter} onChange={e => setSbtiFilter(e.target.value)} className={SELECT}>
            <option value="">All SBTi</option>
            <option value="none">No SBTi</option>
            <option value="committed">Committed</option>
            <option value="validated">Validated</option>
            <option value="removed">Removed</option>
          </select>
          <select value={sectorFilter} onChange={e => setSectorFilter(e.target.value)} className={SELECT}>
            <option value="">All sectors</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={relFilter} onChange={e => setRelFilter(e.target.value)} className={SELECT}>
            <option value="">All relationships</option>
            <option value="current_client">Current client</option>
            <option value="past_client">Past client</option>
            <option value="warm_contact">Warm contact</option>
            <option value="none">Cold</option>
          </select>
        </div>
      </div>

      {/* Column headers */}
      <div className="sticky top-[105px] z-10 bg-[#f6f7fb] border-b border-[#e6e9ef] grid grid-cols-[2fr_80px_110px_100px_130px] px-6 py-2 gap-4">
        {['Company + Climate Target', 'Score', 'ASRS Group', 'SBTi', 'Relationship'].map(h => (
          <span key={h} className="text-[11px] font-semibold text-[#676879] uppercase tracking-wide">{h}</span>
        ))}
      </div>

      {/* Rows */}
      {filtered.map((company, i) => {
        const rb = relationshipBadge(company.relationship_status)
        const gb = asrsGroupBadge(company.asrs_group)
        const target = (company as any).target_description as string | null
        const scope = (company as any).target_scope as string | null
        const targetYear = (company as any).target_year as number | null
        const netZeroYear = (company as any).nzt_end_year as number | null

        return (
          <Link
            key={company.id}
            href={`/companies/${company.id}`}
            className={`grid grid-cols-[2fr_80px_110px_100px_130px] px-6 py-3 gap-4 border-b border-[#e6e9ef] hover:bg-[#e8f0fd]/30 transition-colors items-start ${i % 2 === 0 ? 'bg-white' : 'bg-[#fafbff]'}`}
          >
            {/* Company + full target */}
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-sm font-semibold text-[#323338] leading-tight">{company.name}</p>
                {company.asx_code && (
                  <span className="text-[11px] font-mono text-[#676879] bg-[#f6f7fb] px-1.5 py-0.5 rounded shrink-0">{company.asx_code}</span>
                )}
              </div>

              {/* Full climate target — the main addition */}
              {target ? (
                <p className="text-xs text-[#323338] leading-relaxed mt-0.5">{target}</p>
              ) : (
                <p className="text-xs text-[#c3c6d4] italic">No public climate target</p>
              )}

              {/* Target metadata row */}
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                {company.target_classification && (
                  <span className="text-[10px] text-[#676879] bg-[#f6f7fb] border border-[#e6e9ef] px-1.5 py-0.5 rounded">
                    {company.target_classification}
                  </span>
                )}
                {scope && (
                  <span className="text-[10px] text-[#676879]">{scope}</span>
                )}
                {targetYear && (
                  <span className="text-[10px] text-[#676879]">Target: {targetYear}</span>
                )}
                {netZeroYear && (
                  <span className="text-[10px] text-[#676879]">Net zero: {netZeroYear}</span>
                )}
              </div>
            </div>

            {/* Score */}
            <div className="pt-0.5"><ScorePill score={company.score_overall} /></div>

            {/* ASRS Group */}
            <div className="pt-0.5"><Badge label={gb.label} className={gb.className} /></div>

            {/* SBTi */}
            <div className="pt-0.5"><SbtiPill status={company.sbti_status} /></div>

            {/* Relationship */}
            <div className="flex flex-col gap-1 pt-0.5">
              <Badge label={rb.label} className={rb.className} />
              {company.relationship_lead && (
                <p className="text-[10px] text-[#676879]">{company.relationship_lead}</p>
              )}
            </div>
          </Link>
        )
      })}

      {filtered.length === 0 && (
        <div className="flex items-center justify-center py-32 text-[#676879]">
          <p className="text-sm">No companies match your filters.</p>
        </div>
      )}
    </div>
  )
}

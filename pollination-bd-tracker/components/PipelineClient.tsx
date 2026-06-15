'use client'

import Link from 'next/link'
import type { Company, PipelineStage } from '@/lib/types'
import { PIPELINE_STAGE_LABELS, relationshipBadge } from '@/lib/types'
import { Badge, ScorePill } from '@/components/Badge'

interface Props { companies: Company[] }

const STAGES: PipelineStage[] = ['watch', 'prospect', 'qualified', 'proposal', 'negotiation', 'mandated', 'missed']

const STAGE_META: Record<PipelineStage, { color: string; bg: string; text: string }> = {
  watch:       { color: '#c3c6d4', bg: '#f6f7fb',  text: '#676879' },
  prospect:    { color: '#0073ea', bg: '#cce5ff',  text: '#0060c0' },
  qualified:   { color: '#a25ddc', bg: '#ede3f9',  text: '#7b3db8' },
  proposal:    { color: '#fdab3d', bg: '#fff3e0',  text: '#c47c00' },
  negotiation: { color: '#e2445c', bg: '#ffd3d9',  text: '#c0253d' },
  mandated:    { color: '#00c875', bg: '#d4f4e2',  text: '#007038' },
  missed:      { color: '#c3c6d4', bg: '#f6f7fb',  text: '#9699a6' },
}

export default function PipelineClient({ companies }: Props) {
  const byStage = STAGES.reduce<Record<string, Company[]>>((acc, s) => {
    acc[s] = companies.filter(c => c.pipeline_stage === s)
    return acc
  }, {})

  const total = companies.filter(c => c.pipeline_stage !== 'missed').length

  return (
    <div className="flex flex-col min-h-screen">
      {/* Page header */}
      <div className="bg-white border-b border-[#e6e9ef] px-6 py-3 sticky top-14 z-10 flex items-center gap-3">
        <h1 className="text-base font-bold text-[#323338]">Pipeline</h1>
        <span className="text-xs text-[#676879] bg-[#f6f7fb] px-2 py-0.5 rounded-full border border-[#e6e9ef]">
          {total} active
        </span>
      </div>

      {/* Kanban */}
      <div className="overflow-x-auto flex-1 p-5">
        <div className="flex gap-3 min-w-max items-start">
          {STAGES.map(stage => {
            const rows = byStage[stage] ?? []
            const meta = STAGE_META[stage]

            return (
              <div key={stage} className="w-60 flex-shrink-0 flex flex-col gap-2">
                {/* Column header */}
                <div className="flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: meta.color }} />
                    <span className="text-xs font-semibold text-[#323338]">{PIPELINE_STAGE_LABELS[stage]}</span>
                  </div>
                  <span
                    className="text-[11px] font-bold px-1.5 py-0.5 rounded-full"
                    style={{ background: meta.bg, color: meta.text }}
                  >
                    {rows.length}
                  </span>
                </div>

                {/* Cards */}
                <div className="flex flex-col gap-2">
                  {rows.map(company => {
                    const rb = relationshipBadge(company.relationship_status)
                    return (
                      <Link
                        key={company.id}
                        href={`/companies/${company.id}`}
                        className="bg-white rounded-lg border border-[#e6e9ef] p-3.5 hover:border-[#0073ea]/40 hover:shadow-md transition-all block group"
                        style={{ borderTop: `3px solid ${meta.color}` }}
                      >
                        <p className="text-sm font-semibold text-[#323338] leading-tight mb-0.5 group-hover:text-[#0073ea] transition-colors">
                          {company.name}
                        </p>
                        {company.asx_code && (
                          <p className="text-[10px] font-mono text-[#676879] mb-2">{company.asx_code}</p>
                        )}
                        <div className="flex items-center justify-between mt-2">
                          <ScorePill score={company.score_overall} />
                          <Badge label={rb.label} className={rb.className} />
                        </div>
                        {company.pipeline_notes && (
                          <p className="text-[11px] text-[#676879] mt-2 line-clamp-2 leading-relaxed">
                            {company.pipeline_notes}
                          </p>
                        )}
                        {company.pipeline_owner && (
                          <div className="mt-2 flex items-center gap-1.5">
                            <div className="w-5 h-5 rounded-full bg-[#0073ea]/10 flex items-center justify-center">
                              <span className="text-[9px] font-bold text-[#0073ea]">
                                {company.pipeline_owner.split(' ').map((n: string) => n[0]).join('').slice(0,2).toUpperCase()}
                              </span>
                            </div>
                            <span className="text-[10px] text-[#676879]">{company.pipeline_owner}</span>
                          </div>
                        )}
                      </Link>
                    )
                  })}

                  {rows.length === 0 && (
                    <div className="border-2 border-dashed border-[#e6e9ef] rounded-lg p-5 text-center">
                      <p className="text-xs text-[#c3c6d4]">No companies</p>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

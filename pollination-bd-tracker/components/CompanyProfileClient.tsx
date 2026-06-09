'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, ChevronDown, ChevronRight, ExternalLink, Pencil } from 'lucide-react'
import type { Company, Signal } from '@/lib/types'
import { asrsGroupBadge, relationshipBadge, PIPELINE_STAGE_LABELS } from '@/lib/types'
import { Badge, ScorePill } from '@/components/Badge'
import { updatePipelineStage, updateRelationship } from '@/lib/data'

interface Props {
  company: Company
  signals: Signal[]
}

const SCORE_LABELS = ['ASRS Urgency', 'Target Gap', 'Risk Signals', 'Intent Signals', 'Relationship']
const SCORE_KEYS = ['score_asrs', 'score_target_gap', 'score_risk', 'score_intent', 'score_relationship'] as const

export default function CompanyProfileClient({ company: initial, signals }: Props) {
  const [company, setCompany] = useState(initial)
  const [relExpanded, setRelExpanded] = useState(false)
  const [editingRel, setEditingRel] = useState(false)
  const [relDraft, setRelDraft] = useState({
    relationship_status: company.relationship_status,
    relationship_lead: company.relationship_lead ?? '',
    relationship_contacts: company.relationship_contacts ?? '',
    relationship_notes: company.relationship_notes ?? '',
    last_interaction_date: company.last_interaction_date ?? '',
  })
  const [pipelineStage, setPipelineStage] = useState(company.pipeline_stage ?? '')
  const [pipelineNotes, setPipelineNotes] = useState(company.pipeline_notes ?? '')
  const [saving, setSaving] = useState(false)

  const gb = asrsGroupBadge(company.asrs_group)
  const rb = relationshipBadge(company.relationship_status)

  async function saveRelationship() {
    setSaving(true)
    await updateRelationship(company.id, relDraft as Parameters<typeof updateRelationship>[1])
    setCompany(prev => ({ ...prev, ...relDraft }))
    setEditingRel(false)
    setSaving(false)
  }

  async function savePipeline() {
    setSaving(true)
    await updatePipelineStage(company.id, pipelineStage || null, pipelineNotes)
    setCompany(prev => ({ ...prev, pipeline_stage: (pipelineStage || null) as Company['pipeline_stage'], pipeline_notes: pipelineNotes }))
    setSaving(false)
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      {/* Back */}
      <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-4">
        <ArrowLeft size={14} /> Hot Sheet
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-slate-900">{company.name}</h1>
            {company.asx_code && (
              <span className="text-sm font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded">{company.asx_code}</span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge label={gb.label} className={gb.className} size="md" />
            <Badge label={rb.label} className={rb.className} size="md" />
            {company.sector && <span className="text-sm text-slate-500">{company.sector}</span>}
            {company.mandatory_from && (
              <span className="text-xs text-slate-400">Mandatory from {company.mandatory_from}</span>
            )}
          </div>
        </div>
        <ScorePill score={company.score_overall} />
      </div>

      <div className="grid grid-cols-3 gap-5">
        {/* LEFT col: Score breakdown + Signals */}
        <div className="col-span-2 space-y-5">

          {/* Score breakdown */}
          <div className="bg-white border border-slate-200 rounded-lg p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Score Breakdown</h2>
            <div className="space-y-2">
              {SCORE_LABELS.map((label, i) => {
                const key = SCORE_KEYS[i]
                const val = company[key] ?? 0
                return (
                  <div key={label} className="flex items-center gap-3">
                    <span className="text-xs text-slate-500 w-32 shrink-0">{label}</span>
                    <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${(val / 5) * 100}%`,
                          background: val >= 4 ? '#EF4444' : val >= 3 ? '#F59E0B' : val >= 2 ? '#84CC16' : '#22C55E',
                        }}
                      />
                    </div>
                    <span className="text-xs font-bold text-slate-700 w-6 text-right tabular-nums">{val}/5</span>
                  </div>
                )
              })}
            </div>
            {company.top_signal && (
              <div className="mt-4 pt-3 border-t border-slate-100">
                <p className="text-xs text-slate-500 mb-0.5">Top signal</p>
                <p className="text-sm text-slate-700">{company.top_signal}</p>
              </div>
            )}
          </div>

          {/* Company data */}
          <div className="bg-white border border-slate-200 rounded-lg p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Company Data</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              {[
                ['SBTi Status', company.sbti_status],
                ['Target Classification', company.target_classification],
                ['Target Year', company.target_year],
                ['Net Zero Year', company.net_zero_year],
                ['NGER Scope 1', company.nger_scope1_tco2e ? `${(company.nger_scope1_tco2e / 1e6).toFixed(2)} Mt` : null],
                ['NGER Year', company.nger_year],
                ['Safeguard Covered', company.safeguard_covered ? 'Yes' : 'No'],
                ['NZT Status', company.nzt_status],
                ['NZT End Target', company.nzt_end_target],
                ['NZT Interim %', company.nzt_interim_pct ? `${company.nzt_interim_pct}%` : null],
                ['NZT Published Plan', company.nzt_published_plan === null ? null : company.nzt_published_plan ? 'Yes' : 'No'],
                ['Race to Zero', company.nzt_race_to_zero === null ? null : company.nzt_race_to_zero ? 'Yes' : 'No'],
              ].map(([label, value]) => value != null ? (
                <div key={String(label)} className="flex gap-1">
                  <dt className="text-slate-400 shrink-0">{label}:</dt>
                  <dd className="text-slate-700 font-medium">{String(value)}</dd>
                </div>
              ) : null)}
            </dl>
          </div>

          {/* Signal timeline */}
          <div className="bg-white border border-slate-200 rounded-lg p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Signal Timeline</h2>
            {signals.length === 0 ? (
              <p className="text-sm text-slate-400">No signals recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {signals.map(sig => (
                  <div key={sig.id} className="flex gap-3 pb-3 border-b border-slate-50 last:border-0">
                    <div className="mt-0.5 w-1.5 h-1.5 rounded-full bg-[#00579B] shrink-0 mt-1.5" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-slate-700">{sig.headline}</p>
                        <span className="text-[11px] text-slate-400 whitespace-nowrap shrink-0">
                          {new Date(sig.signal_date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: '2-digit' })}
                        </span>
                      </div>
                      {sig.body && <p className="text-xs text-slate-500 mt-0.5">{sig.body}</p>}
                      {sig.source_url && (
                        <a href={sig.source_url} target="_blank" rel="noreferrer"
                          className="inline-flex items-center gap-0.5 text-[11px] text-[#00579B] mt-0.5 hover:underline">
                          Source <ExternalLink size={10} />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT col: Relationship + Pipeline */}
        <div className="space-y-5">
          {/* Relationship */}
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setRelExpanded(v => !v)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-700">Relationship</span>
                <Badge label={rb.label} className={rb.className} />
              </div>
              <div className="flex items-center gap-1">
                <button onClick={e => { e.stopPropagation(); setEditingRel(v => !v); setRelExpanded(true) }}
                  className="p-1 hover:bg-slate-100 rounded">
                  <Pencil size={12} className="text-slate-400" />
                </button>
                {relExpanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
              </div>
            </button>

            {relExpanded && (
              <div className="px-4 pb-4 border-t border-slate-100">
                {editingRel ? (
                  <div className="space-y-2 mt-3">
                    <select
                      value={relDraft.relationship_status}
                      onChange={e => setRelDraft(p => ({ ...p, relationship_status: e.target.value as Company['relationship_status'] }))}
                      className="w-full text-sm border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#00579B]"
                    >
                      <option value="none">Cold</option>
                      <option value="warm_contact">Warm contact</option>
                      <option value="past_client">Past client</option>
                      <option value="current_client">Current client</option>
                    </select>
                    <input placeholder="Pollination lead" value={relDraft.relationship_lead}
                      onChange={e => setRelDraft(p => ({ ...p, relationship_lead: e.target.value }))}
                      className="w-full text-sm border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#00579B]" />
                    <input placeholder="Contact names/titles" value={relDraft.relationship_contacts}
                      onChange={e => setRelDraft(p => ({ ...p, relationship_contacts: e.target.value }))}
                      className="w-full text-sm border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#00579B]" />
                    <input type="date" value={relDraft.last_interaction_date}
                      onChange={e => setRelDraft(p => ({ ...p, last_interaction_date: e.target.value }))}
                      className="w-full text-sm border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#00579B]" />
                    <textarea placeholder="Relationship notes" value={relDraft.relationship_notes} rows={3}
                      onChange={e => setRelDraft(p => ({ ...p, relationship_notes: e.target.value }))}
                      className="w-full text-sm border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#00579B] resize-none" />
                    <div className="flex gap-2">
                      <button onClick={saveRelationship} disabled={saving}
                        className="flex-1 text-xs bg-[#00579B] text-white rounded py-1.5 hover:bg-[#004a85] disabled:opacity-50">
                        {saving ? 'Saving…' : 'Save'}
                      </button>
                      <button onClick={() => setEditingRel(false)}
                        className="flex-1 text-xs border border-slate-200 rounded py-1.5 hover:bg-slate-50">
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <dl className="space-y-1.5 mt-3">
                    {company.relationship_lead && (
                      <div><dt className="text-[11px] text-slate-400">Lead</dt><dd className="text-sm text-slate-700">{company.relationship_lead}</dd></div>
                    )}
                    {company.relationship_contacts && (
                      <div><dt className="text-[11px] text-slate-400">Contacts</dt><dd className="text-sm text-slate-700">{company.relationship_contacts}</dd></div>
                    )}
                    {company.last_interaction_date && (
                      <div><dt className="text-[11px] text-slate-400">Last interaction</dt><dd className="text-sm text-slate-700">{company.last_interaction_date}</dd></div>
                    )}
                    {company.relationship_notes && (
                      <div><dt className="text-[11px] text-slate-400">Notes</dt><dd className="text-sm text-slate-700 whitespace-pre-wrap">{company.relationship_notes}</dd></div>
                    )}
                    {!company.relationship_lead && !company.relationship_contacts && !company.relationship_notes && (
                      <p className="text-xs text-slate-400">No relationship details recorded.</p>
                    )}
                  </dl>
                )}
              </div>
            )}
          </div>

          {/* Pipeline */}
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Pipeline Stage</h2>
            <select
              value={pipelineStage}
              onChange={e => setPipelineStage(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-[#00579B]"
            >
              <option value="">— Not in pipeline —</option>
              {Object.entries(PIPELINE_STAGE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <textarea
              placeholder="Pipeline notes / next action…"
              value={pipelineNotes}
              rows={4}
              onChange={e => setPipelineNotes(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-[#00579B]"
            />
            <button
              onClick={savePipeline}
              disabled={saving}
              className="mt-2 w-full text-xs bg-[#00579B] text-white rounded py-1.5 hover:bg-[#004a85] disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

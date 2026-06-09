/**
 * Workflow: Greenwashing & News Monitor
 *
 * DO NOT RUN YET — staged for future use.
 *
 * Monitors all hot sheet companies for:
 * - ACCC greenwashing enforcement actions
 * - Climate-related shareholder resolutions
 * - AGM climate votes
 * - Director/CSO/CFO changes
 * - Negative climate press (last 30 days)
 * - SBTi status changes
 *
 * When to run: Weekly, triggered via schedule or manually.
 * Each new signal found → stored in signals table → hot sheet score updates.
 *
 * Future: Add as a scheduled Vercel cron job.
 */

export const meta = {
  name: 'greenwashing-monitor',
  description: 'Monitor hot sheet companies for greenwashing cases, shareholder resolutions, and climate news',
  phases: [
    { title: 'Load', detail: 'Get all Group 1 + Group 2 companies from DB' },
    { title: 'Monitor', detail: 'Fan out agents to search for signals per company' },
    { title: 'Deduplicate', detail: 'Filter out signals already in DB' },
    { title: 'Save', detail: 'Write new signals to DB and rescore affected companies' },
  ],
}

const SIGNAL_SCHEMA = {
  type: 'object',
  properties: {
    company_name: { type: 'string' },
    signals_found: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          signal_type: {
            type: 'string',
            enum: [
              'greenwashing_case',
              'shareholder_resolution',
              'agm_climate_item',
              'new_director',
              'sbti_removed',
              'sbti_vintage_old',
              'delivery_behind',
              'asrs_mentioned_report',
              'merger_acquisition',
              'manual',
            ],
          },
          headline: { type: 'string' },
          body: { type: 'string' },
          source_url: { type: 'string' },
          date: { type: 'string' },
          score_impact: {
            type: 'string',
            enum: ['high', 'medium', 'low'],
            description: 'How much does this signal boost BD priority?',
          },
        },
        required: ['signal_type', 'headline', 'score_impact'],
      },
    },
    nothing_found: { type: 'boolean' },
  },
  required: ['company_name', 'signals_found'],
}

// ── SIGNAL TYPE GUIDE (for agents) ───────────────────────────────────────────
// greenwashing_case:    ACCC action, court case, consumer complaint upheld
// shareholder_resolution: Filed or voted on climate resolution at AGM
// agm_climate_item:    Climate strategy tabled at upcoming AGM
// new_director:        New board member with climate/sustainability background
// sbti_removed:        Company withdrew SBTi commitment
// delivery_behind:     Emissions data shows they're off their stated trajectory
// asrs_mentioned_report: Sustainability report explicitly discusses ASRS compliance
// merger_acquisition:  M&A that changes climate obligations or ownership
// manual:              Other notable climate-related development

// ── Phase 1: Load companies ───────────────────────────────────────────────────
phase('Load')

const DB_RESULT = await agent(
  `Query Supabase REST API to get Group 1 and Group 2 companies.

URL: https://ahoyjvqvgbmcoydjgzpb.supabase.co/rest/v1/companies
Headers:
  apikey: sb_publishable_y8P5je4IqUJm2PCS_itZjQ_zLx0zZ9r
  Authorization: Bearer sb_publishable_y8P5je4IqUJm2PCS_itZjQ_zLx0zZ9r

Params:
  select=id,name,asx_code,sector,asrs_group,score_overall,sbti_status
  relationship_status=neq.current_client
  asrs_group=in.(Group 1,Group 2)
  order=score_overall.desc
  limit=50

Return companies array.`,
  {
    label: 'Load companies',
    schema: {
      type: 'object',
      properties: {
        companies: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              name: { type: 'string' },
              asx_code: { type: 'string' },
              sector: { type: 'string' },
              asrs_group: { type: 'string' },
            },
            required: ['id', 'name'],
          },
        },
      },
      required: ['companies'],
    },
  }
)

const companies = DB_RESULT ? DB_RESULT.companies : []
log('Monitoring ' + companies.length + ' companies')

// ── Phase 2: Monitor each company ─────────────────────────────────────────────
phase('Monitor')

const monitorResults = await pipeline(
  companies,
  (company) => agent(
    `Search for recent climate-related news and signals about ${company.name} (ASX: ${company.asx_code || 'private'}).

Search for news from the last 90 days on these specific topics:

1. GREENWASHING: Search "[company name] greenwashing ACCC 2025 2026" and "[company name] climate misleading advertising"
2. SHAREHOLDER: Search "[company name] climate resolution shareholder AGM 2025 2026"
3. AGM: Search "[company name] AGM climate 2025 2026 vote"
4. DIRECTORS: Search "[company name] new chief sustainability officer CSO climate director 2025 2026"
5. ASRS: Search "[company name] ASRS sustainability reporting 2025 2026"
6. EMISSIONS: Search "[company name] emissions target behind schedule 2025 2026"

For each signal found:
- Give the exact headline text
- Give the source URL
- Give the date if known
- Rate impact: high (greenwashing case, major shareholder revolt) / medium (AGM item, director change) / low (minor mention)

Only report signals with a reliable source URL. If nothing found for a category, skip it.
Set nothing_found=true if genuinely no relevant news found.`,
    {
      label: company.name.slice(0, 30),
      phase: 'Monitor',
      schema: SIGNAL_SCHEMA,
    }
  )
)

const validResults = monitorResults.filter(Boolean)
const newSignals = validResults.flatMap(function(r) { return r.signals_found || [] })
const highImpact = newSignals.filter(function(s) { return s.score_impact === 'high' })

log('Companies monitored: ' + validResults.length)
log('Total signals found: ' + newSignals.length)
log('High impact signals: ' + highImpact.length)

// ── Phase 3: Deduplicate (check not already in DB) ────────────────────────────
phase('Deduplicate')

// For now just log — full dedup requires fetching existing signals
// TODO: fetch existing signal headlines per company and filter out duplicates
log('Deduplication: ' + newSignals.length + ' signals to review (manual dedup in v1)')

// ── Phase 4: Save ─────────────────────────────────────────────────────────────
phase('Save')

const companyIdMap = {}
companies.forEach(function(c) { companyIdMap[c.name] = c.id })

const signalsToSave = []
validResults.forEach(function(result, idx) {
  const company = companies[idx]
  if (!company || !result || !result.signals_found) return

  result.signals_found.forEach(function(sig) {
    signalsToSave.push({
      company_id: company.id,
      signal_type: sig.signal_type,
      signal_date: sig.date || new Date().toISOString().slice(0, 10),
      headline: sig.headline,
      body: sig.body || null,
      source_url: sig.source_url || null,
      source: 'greenwashing_monitor',
      score_delta: sig.score_impact === 'high' ? 1.5 : sig.score_impact === 'medium' ? 0.75 : 0.25,
    })
  })
})

log('Signals ready to save: ' + signalsToSave.length)

// NOTE: Saving disabled in this version — review signals manually first
// To enable: uncomment the Supabase POST below
//
// if (signalsToSave.length > 0) {
//   await agent(`POST to https://ahoyjvqvgbmcoydjgzpb.supabase.co/rest/v1/signals
//     with body: ${JSON.stringify(signalsToSave)}
//     Headers: apikey + Authorization = sb_publishable_...
//     Content-Type: application/json`)
// }

return {
  companies_monitored: validResults.length,
  signals_found: newSignals.length,
  high_impact: highImpact.length,
  signals_ready: signalsToSave.length,
  top_signals: highImpact.slice(0, 10).map(function(s) {
    return { type: s.signal_type, headline: s.headline, impact: s.score_impact }
  }),
  all_results: validResults.map(function(r, i) {
    return {
      company: companies[i] ? companies[i].name : 'unknown',
      signals: r.signals_found ? r.signals_found.length : 0,
      nothing_found: r.nothing_found || false,
    }
  }),
}

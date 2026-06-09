/**
 * Workflow: Research Hot Sheet Companies
 *
 * Deploys one agent per top hot sheet company to:
 * 1. Find their latest sustainability report URL
 * 2. Extract key decarbonisation actions and commitments
 * 3. Flag any ASRS mentions
 * 4. Write results as signals back to the DB
 *
 * Run via: workflow({ scriptPath: 'scripts/workflows/research_hotsheet.js' })
 * Or trigger from the app's "Research" button (future).
 */

export const meta = {
  name: 'research-hotsheet',
  description: 'Research top hot sheet companies for decarbonisation actions and sustainability reports',
  phases: [
    { title: 'Load', detail: 'Fetch top companies from Supabase' },
    { title: 'Research', detail: 'One agent per company — find sustainability report, extract actions' },
    { title: 'Save', detail: 'Write signals back to database' },
  ],
}

const RESEARCH_SCHEMA = {
  type: 'object',
  properties: {
    company_name: { type: 'string' },
    asx_code: { type: 'string' },
    sustainability_report_url: { type: 'string' },
    report_year: { type: 'string' },
    asrs_mentioned: { type: 'boolean' },
    asrs_context: { type: 'string' },
    key_actions: {
      type: 'array',
      items: { type: 'string' },
      description: 'Specific decarbonisation actions, investments, or commitments found',
    },
    interim_target_found: { type: 'string' },
    scope3_approach: { type: 'string' },
    notable_signals: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          signal_type: { type: 'string', enum: ['asrs_mentioned_report', 'greenwashing_case', 'agm_climate_item', 'new_director', 'delivery_behind', 'manual'] },
          headline: { type: 'string' },
          body: { type: 'string' },
          source_url: { type: 'string' },
        },
        required: ['signal_type', 'headline'],
      },
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['company_name', 'notable_signals', 'confidence'],
}

// ── Phase 1: Load top companies from Supabase ─────────────────────────────────
phase('Load')

const DB_RESULT = await agent(
  `Query Supabase to get the top 25 hot sheet companies.

  URL: https://ahoyjvqvgbmcoydjgzpb.supabase.co/rest/v1/companies
  Method: GET
  Headers:
    apikey: sb_publishable_y8P5je4IqUJm2PCS_itZjQ_zLx0zZ9r
    Authorization: Bearer sb_publishable_y8P5je4IqUJm2PCS_itZjQ_zLx0zZ9r

  Query params:
    select=id,name,asx_code,sector,asrs_group,score_overall,target_classification,sbti_status,sbti_date_updated
    relationship_status=neq.current_client
    sbti_status=neq.Targets set
    asrs_group=neq.Unclassified
    score_overall=gt.0
    order=score_overall.desc
    limit=25

  Return the list of companies as JSON. Each company needs: id, name, asx_code, sector, score_overall.`,
  {
    label: 'Load top 25 companies',
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
              score_overall: { type: 'number' },
              asrs_group: { type: 'string' },
              target_classification: { type: 'string' },
              sbti_status: { type: 'string' },
            },
            required: ['id', 'name'],
          },
        },
      },
      required: ['companies'],
    },
  }
)

const companies = (DB_RESULT && DB_RESULT.companies) ? DB_RESULT.companies : []
log('Companies to research: ' + companies.length)

if (companies.length === 0) {
  log('No companies returned — check Supabase connection')
  return { error: 'No companies loaded', results: [] }
}

// ── Phase 2: Research each company in parallel ────────────────────────────────
phase('Research')

const researchResults = await pipeline(
  companies,
  (company) => agent(
    `Research ${company.name} (ASX: ${company.asx_code || 'private'}, Sector: ${company.sector || 'unknown'}) for their climate and decarbonisation activities.

YOUR TASK:
1. Find their latest sustainability/climate/ESG report URL (search "[company name] sustainability report 2024 2025 site:[company].com.au OR filetype:pdf")
2. Check their website and any publicly available reports for:
   - Specific decarbonisation investments or projects announced
   - Any mention of ASRS (Australian Sustainability Reporting Standards) or AASB S2
   - Their scope 3 emissions approach
   - Any interim reduction targets with percentages
   - Any recent climate-related news (last 12 months)
3. Search for "[company name] ASRS sustainability disclosure 2025 2026"
4. Search for "[company name] climate target decarbonisation 2025"

Context:
- ASRS Group: ${company.asrs_group} (${company.asrs_group === 'Group 1' ? 'mandatory NOW' : 'mandatory FY2026/27'})
- Target classification: ${company.target_classification || 'No public target'}
- SBTi status: ${company.sbti_status || 'None'}
- BD score: ${company.score_overall}/5

Be specific about what you found and where. If ASRS is mentioned, quote the exact context.
Flag as a notable signal if you find: ASRS mentions, specific investment announcements, greenwashing risk, board changes.`,
    {
      label: company.name.slice(0, 30),
      phase: 'Research',
      schema: RESEARCH_SCHEMA,
    }
  )
)

const validResults = researchResults.filter(Boolean)
log('Research complete: ' + validResults.length + '/' + companies.length + ' companies')

// Count signals found
const totalSignals = validResults.reduce(function(sum, r) {
  return sum + (r.notable_signals ? r.notable_signals.length : 0)
}, 0)
const asrsMentions = validResults.filter(function(r) { return r.asrs_mentioned }).length
const reportFound = validResults.filter(function(r) { return r.sustainability_report_url }).length

log('Signals found: ' + totalSignals)
log('ASRS mentions: ' + asrsMentions)
log('Sustainability reports found: ' + reportFound)

// ── Phase 3: Save signals to Supabase ─────────────────────────────────────────
phase('Save')

// Match results back to company IDs
const companyIdMap = {}
companies.forEach(function(c) { companyIdMap[c.name] = c.id })

const signalsToSave = []
validResults.forEach(function(result, idx) {
  const company = companies[idx]
  if (!company || !result) return
  const companyId = company.id

  // Save notable signals
  if (result.notable_signals && result.notable_signals.length > 0) {
    result.notable_signals.forEach(function(sig) {
      signalsToSave.push({
        company_id: companyId,
        signal_type: sig.signal_type || 'manual',
        signal_date: new Date().toISOString().slice(0, 10),
        headline: sig.headline,
        body: sig.body || null,
        source_url: sig.source_url || result.sustainability_report_url || null,
        source: 'automated_research',
        score_delta: sig.signal_type === 'asrs_mentioned_report' ? 1.0 :
                     sig.signal_type === 'greenwashing_case' ? 2.0 : 0.5,
      })
    })
  }

  // Always save the sustainability report URL as a signal if found
  if (result.sustainability_report_url && result.key_actions && result.key_actions.length > 0) {
    signalsToSave.push({
      company_id: companyId,
      signal_type: 'manual',
      signal_date: new Date().toISOString().slice(0, 10),
      headline: 'Sustainability report: ' + result.key_actions[0],
      body: result.key_actions.join(' | '),
      source_url: result.sustainability_report_url,
      source: 'automated_research',
      score_delta: 0,
    })
  }
})

log('Signals to save: ' + signalsToSave.length)

// Write signals in batches via Supabase REST
if (signalsToSave.length > 0) {
  const saveResult = await agent(
    `Save these signals to Supabase via REST API POST.

URL: https://ahoyjvqvgbmcoydjgzpb.supabase.co/rest/v1/signals
Method: POST
Headers:
  apikey: sb_publishable_y8P5je4IqUJm2PCS_itZjQ_zLx0zZ9r
  Authorization: Bearer sb_publishable_y8P5je4IqUJm2PCS_itZjQ_zLx0zZ9r
  Content-Type: application/json
  Prefer: return=minimal

Body (array of signal objects):
${JSON.stringify(signalsToSave, null, 2)}

Make the POST request and confirm how many signals were saved. Return { saved: number, error: string | null }`,
    {
      label: 'Save ' + signalsToSave.length + ' signals',
      schema: {
        type: 'object',
        properties: {
          saved: { type: 'number' },
          error: { type: 'string' },
        },
        required: ['saved'],
      },
    }
  )
  log('Saved: ' + (saveResult ? saveResult.saved : 0) + ' signals')
}

// Return summary
return {
  companies_researched: validResults.length,
  signals_found: totalSignals,
  asrs_mentions: asrsMentions,
  reports_found: reportFound,
  results: validResults.map(function(r, i) {
    return {
      company: companies[i] ? companies[i].name : 'unknown',
      report_url: r.sustainability_report_url || null,
      asrs_mentioned: r.asrs_mentioned || false,
      signals: r.notable_signals ? r.notable_signals.length : 0,
      key_actions: r.key_actions || [],
      confidence: r.confidence,
    }
  }),
}

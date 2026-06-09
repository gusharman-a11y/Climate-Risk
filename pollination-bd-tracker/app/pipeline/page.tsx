import { getPipelineCompanies } from '@/lib/data'
import PipelineClient from '@/components/PipelineClient'

export const dynamic = 'force-dynamic'

export default async function PipelinePage() {
  const companies = await getPipelineCompanies()
  return <PipelineClient companies={companies} />
}

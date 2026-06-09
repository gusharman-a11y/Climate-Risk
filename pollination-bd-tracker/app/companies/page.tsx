import { unstable_cache } from 'next/cache'
import { getCompanies } from '@/lib/data'
import CompaniesClient from '@/components/CompaniesClient'

const getCachedCompanies = unstable_cache(
  () => getCompanies(),
  ['companies-all'],
  { revalidate: 300 },
)

export default async function CompaniesPage() {
  const companies = await getCachedCompanies()
  return <CompaniesClient companies={companies} />
}

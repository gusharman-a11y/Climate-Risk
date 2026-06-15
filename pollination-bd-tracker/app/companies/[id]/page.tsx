import { getCompany, getSignals } from '@/lib/data'
import CompanyProfileClient from '@/components/CompanyProfileClient'
import { notFound } from 'next/navigation'

export const dynamic = 'force-dynamic'

export default async function CompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const [company, signals] = await Promise.all([getCompany(id), getSignals(id)])
  if (!company) notFound()
  return <CompanyProfileClient company={company} signals={signals} />
}

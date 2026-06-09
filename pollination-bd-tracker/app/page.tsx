import { getHotSheet } from '@/lib/data'
import HotSheetClient from '@/components/HotSheetClient'

export const dynamic = 'force-dynamic'

export default async function HotSheetPage() {
  const companies = await getHotSheet()
  return <HotSheetClient companies={companies} />
}

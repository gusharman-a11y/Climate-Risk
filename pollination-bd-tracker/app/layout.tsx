import type { Metadata } from 'next'
import { Figtree } from 'next/font/google'
import './globals.css'
import TopNav from '@/components/TopNav'

const figtree = Figtree({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-figtree',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'BD Tracker',
  description: 'Australian ASRS business development pipeline',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={figtree.variable}>
      <body className="min-h-screen bg-[#f6f7fb]" style={{ fontFamily: 'var(--font-figtree), Figtree, sans-serif' }}>
        <TopNav />
        <main>{children}</main>
      </body>
    </html>
  )
}

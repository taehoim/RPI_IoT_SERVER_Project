'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardScreen } from './components/DashboardScreen'

export default function Home() {
  const router = useRouter()
  const [hasToken, setHasToken] = useState<boolean | null>(null)

  useEffect(() => {
    const ok = !!localStorage.getItem('jwt')
    if (!ok) {
      router.replace('/login')
      return
    }
    setHasToken(true)
  }, [router])

  if (!hasToken) return null
  return <DashboardScreen />
}

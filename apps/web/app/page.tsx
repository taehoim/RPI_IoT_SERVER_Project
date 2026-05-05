'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useApi } from '@iot/api'

interface Sensor {
  channel_id: string
  channel_name: string
  measurement_key: string
  value: number | null
  unit: string
  status: string
}
interface Actuator { id: string; display_name: string; state: string }
interface Dashboard {
  gateway: { name: string; serial_number: string }
  sensors: Sensor[]
  actuators: Actuator[]
  last_seen: string | null
}
interface Gateway { id: string; serial_number: string; name: string }

const STATUS_COLOR: Record<string, string> = {
  ok: '#34C759', warn: '#FF9500', danger: '#FF3B30', unknown: '#8E8E93',
}

export default function Home() {
  const api = useApi()
  const router = useRouter()
  const [data, setData] = useState<Dashboard | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [gwId, setGwId] = useState<string | null>(null)

  useEffect(() => {
    if (!localStorage.getItem('jwt')) {
      router.replace('/login')
      return
    }
    api.get<Gateway[]>('/api/gateways')
      .then((list) => { if (list[0]) setGwId(list[0].id) })
      .catch((e) => setErr(e?.message || 'gateway 로딩 실패'))
  }, [api, router])

  useEffect(() => {
    if (!gwId) return
    let cancelled = false
    const fetchDash = () =>
      api.get<Dashboard>(`/api/dashboard?gateway_id=${gwId}`)
        .then((d) => { if (!cancelled) setData(d) })
        .catch((e) => { if (!cancelled) setErr(e?.message || 'dashboard 로딩 실패') })
    fetchDash()
    const id = setInterval(fetchDash, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [gwId, api])

  const sendCmd = async (a: Actuator) => {
    if (!gwId) return
    const next = a.state === 'on' ? 'OFF' : 'ON'
    try {
      await api.post(`/api/gateways/${gwId}/commands`, {
        actuator_channel_id: a.id, action: next, require_ack: true,
      })
      const d = await api.get<Dashboard>(`/api/dashboard?gateway_id=${gwId}`)
      setData(d)
    } catch (e: any) {
      setErr(e?.message || 'command 실패')
    }
  }

  if (err) {
    return (
      <div style={{ padding: 24, color: '#FF3B30', fontFamily: '-apple-system, sans-serif' }}>
        ⚠ {err}
        <br/>
        <a href="/login" style={{ color: '#007AFF' }}>/login으로 가서 토큰 재발급</a>
      </div>
    )
  }
  if (!data) return <div style={{ padding: 24, fontFamily: '-apple-system, sans-serif' }}>로딩 중...</div>

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 24, fontFamily: '-apple-system, sans-serif' }}>
      <h1 style={{ fontSize: 32 }}>{data.gateway.name || data.gateway.serial_number}</h1>
      <p style={{ color: '#666' }}>마지막 업데이트: {data.last_seen ? new Date(data.last_seen).toLocaleTimeString() : '없음'}</p>

      <h2 style={{ marginTop: 32, fontSize: 20 }}>센서</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 8 }}>
        {data.sensors.map((s) => (
          <div key={s.channel_id + s.measurement_key} style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16, background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>
            <div style={{ color: '#666', fontSize: 12 }}>{s.channel_name}</div>
            <div style={{ color: '#999', fontSize: 11, marginTop: 2 }}>{s.measurement_key}</div>
            <div style={{ color: STATUS_COLOR[s.status] || '#000', fontSize: 28, fontWeight: 700, marginTop: 8 }}>
              {typeof s.value === 'number' ? s.value.toFixed(1) : '—'}
              <span style={{ fontSize: 14, color: '#666', marginLeft: 4 }}>{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 32, fontSize: 20 }}>액추에이터</h2>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
        {data.actuators.map((a) => (
          <button
            key={a.id}
            onClick={() => sendCmd(a)}
            style={{
              padding: '16px 24px', borderRadius: 12, border: 0, cursor: 'pointer', fontSize: 16,
              background: a.state === 'on' ? '#007AFF' : '#E5E5EA',
              color: a.state === 'on' ? 'white' : 'black',
              minWidth: 140,
            }}
          >
            <div style={{ fontWeight: 600 }}>{a.display_name}</div>
            <div style={{ fontSize: 12, opacity: 0.8 }}>{a.state === 'on' ? '켜짐' : a.state === 'off' ? '꺼짐' : '알 수 없음'}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

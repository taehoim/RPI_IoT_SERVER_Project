'use client'

import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'

export interface TrendPoint {
  ts: string
  value: number
}

export function TrendChart({ data }: { data: TrendPoint[] }) {
  const formatted = data.map((d) => ({
    time: new Date(d.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    value: d.value,
  }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={formatted}>
        <XAxis dataKey="time" tick={{ fontSize: 11 }} minTickGap={40} />
        <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
        <Tooltip />
        <Line type="monotone" dataKey="value" stroke="#007AFF" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

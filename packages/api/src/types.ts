export interface Gateway {
  id: string
  serial_number: string
  name: string
  status: 'online' | 'offline' | 'degraded'
  site_id: string
}

export interface SensorReading {
  channel_id: string
  channel_name: string
  measurement_key: string
  value: number
  unit: string
  ts: string
  status: 'ok' | 'warn' | 'danger'
}

export interface ActuatorChannel {
  id: string
  slug: string
  display_name: string
  state: 'on' | 'off' | 'unknown'
  enabled: boolean
}

export interface DashboardData {
  gateway: Gateway
  sensors: SensorReading[]
  actuators: ActuatorChannel[]
  last_seen: string | null
}

export interface CommandPayload {
  actuator_channel_id: string
  action: 'ON' | 'OFF'
  require_ack: boolean
}

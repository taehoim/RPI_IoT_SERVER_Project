'use client'

import { useRef } from 'react'

export default function LoginPage() {
  const ref = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    // Strip all whitespace — terminal copy can include line breaks.
    const t = (ref.current?.value || '').replace(/\s+/g, '')
    if (!t) {
      alert('토큰이 비어 있습니다.')
      return
    }
    const parts = t.split('.')
    if (parts.length !== 3) {
      alert(`JWT 형식 오류: dot로 구분된 3부분이어야 함 (현재 ${parts.length}부분)`)
      return
    }
    localStorage.setItem('jwt', t)
    // Hard navigation — bypasses next/navigation in case router is broken.
    window.location.href = '/'
  }

  return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 16, fontFamily: '-apple-system, sans-serif' }}>
      <h2>로그인</h2>
      <p style={{ color: '#666' }}>
        터미널에서 <code>sudo /opt/iot-sim/bin/sim-fake-jwt</code> 실행 후 출력 붙여넣기
      </p>
      <textarea
        ref={ref}
        placeholder="JWT token (eyJhbGc...)"
        rows={5}
        defaultValue=""
        style={{
          width: '100%', padding: 12, fontSize: 14, marginTop: 16,
          boxSizing: 'border-box', border: '1px solid #ddd', borderRadius: 6,
          fontFamily: 'monospace', resize: 'vertical',
        }}
      />
      <button
        onClick={submit}
        type="button"
        style={{
          width: '100%', padding: 12, fontSize: 16, marginTop: 12,
          background: '#007AFF', color: 'white',
          border: 0, borderRadius: 6, cursor: 'pointer',
        }}
      >
        들어가기
      </button>
    </div>
  )
}

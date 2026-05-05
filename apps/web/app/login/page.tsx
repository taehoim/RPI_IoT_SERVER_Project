'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { YStack, Input, Button, H2, Paragraph } from 'tamagui'

export default function LoginPage() {
  const [token, setToken] = useState('')
  const router = useRouter()

  const submit = () => {
    const trimmed = token.trim()
    if (!trimmed) return
    localStorage.setItem('jwt', trimmed)
    router.push('/')
  }

  return (
    <YStack padding="$4" gap="$4" maxWidth={500} margin="auto" marginTop="$10">
      <H2>로그인</H2>
      <Paragraph theme="alt2">
        Sim mode: 터미널에서 <Paragraph fontFamily="$mono">{`python3 deploy/scripts/sim-fake-jwt.py`}</Paragraph> 실행 후 출력 붙여넣기.
      </Paragraph>
      <Input
        size="$4"
        placeholder="JWT token..."
        value={token}
        onChangeText={setToken}
        secureTextEntry
        onSubmitEditing={submit}
      />
      <Button theme="active" onPress={submit} disabled={!token.trim()}>
        들어가기
      </Button>
    </YStack>
  )
}

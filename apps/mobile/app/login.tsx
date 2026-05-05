import { useRouter } from 'expo-router'
import { useState } from 'react'
import { YStack, Input, Button, H2, Paragraph } from 'tamagui'
import * as SecureStore from 'expo-secure-store'

export default function Login() {
  const [token, setToken] = useState('')
  const router = useRouter()

  const submit = () => {
    const trimmed = token.trim()
    if (!trimmed) return
    SecureStore.setItem('jwt', trimmed)
    router.replace('/')
  }

  return (
    <YStack padding="$4" gap="$4" marginTop="$10">
      <H2>로그인</H2>
      <Paragraph theme="alt2">Sim JWT 붙여넣기</Paragraph>
      <Input
        size="$4"
        value={token}
        onChangeText={setToken}
        secureTextEntry
        autoCapitalize="none"
        onSubmitEditing={submit}
      />
      <Button theme="active" onPress={submit} disabled={!token.trim()}>
        들어가기
      </Button>
    </YStack>
  )
}

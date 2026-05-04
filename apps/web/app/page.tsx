import { YStack, H1, Paragraph } from '@iot/ui'

export default function Home() {
  return (
    <YStack padding="$4" gap="$3" maxWidth={600} margin="auto" marginTop="$10">
      <H1>대시보드 준비 중</H1>
      <Paragraph theme="alt2">
        Task 9에서 SiteSelector + 센서 카드 + 액추에이터 토글이 추가됩니다.
      </Paragraph>
    </YStack>
  )
}

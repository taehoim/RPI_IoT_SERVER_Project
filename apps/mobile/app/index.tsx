import { YStack, H1, Paragraph } from 'tamagui'

export default function Home() {
  return (
    <YStack flex={1} alignItems="center" justifyContent="center" padding="$4" gap="$3">
      <H1>대시보드 준비 중</H1>
      <Paragraph theme="alt2" textAlign="center">
        Task 12에서 SiteSelector + 센서 카드 + 액추에이터 토글로 채워집니다.
      </Paragraph>
    </YStack>
  )
}

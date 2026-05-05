import { Providers } from './providers'

export const metadata = {
  title: '농장 모니터',
  description: 'IoT Gateway Dashboard',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body style={{ margin: 0, fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif' }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

/**
 * One receipt.
 *
 * The reading runs on the server after the upload, so this screen asks again
 * every few seconds until the parsed values arrive.
 */

import { Image } from 'expo-image'
import { useLocalSearchParams } from 'expo-router'
import { useEffect, useState } from 'react'
import { ScrollView, View } from 'react-native'

import { api, mediaUrl } from '@/api/client'
import type { ReceiptDetail } from '@/api/types'
import { Body, Caption, Card, Loading, Screen, Title } from '@/components/ui'
import { formatDate, formatMoney } from '@/lib/format'
import { radius, spacing } from '@/theme'

export default function ReceiptScreen() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const [receipt, setReceipt] = useState<ReceiptDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const read = async (): Promise<void> => {
      try {
        const next = await api.get<ReceiptDetail>(`/api/receipts/${id}`)
        if (cancelled) return
        setReceipt(next)
        // Ask again while the reading is not finished.
        if (!next.ocr_parsed_json) timer = setTimeout(() => void read(), 3000)
      } catch (failure) {
        if (!cancelled) {
          setError(failure instanceof Error ? failure.message : 'The receipt did not load.')
        }
      }
    }
    void read()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [id])

  if (error) {
    return (
      <Screen edges={['bottom']}>
        <View style={{ padding: spacing.lg }}>
          <Caption>{error}</Caption>
        </View>
      </Screen>
    )
  }
  if (!receipt) return <Loading label="Reading the receipt" />

  return (
    <Screen edges={['bottom']}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}>
        <Title>{receipt.vendor ?? 'Receipt'}</Title>
        <Caption>
          {formatDate(receipt.purchase_date)} · {formatMoney(receipt.total_amount)}
        </Caption>

        <Image
          source={{ uri: mediaUrl(receipt.file_path) }}
          style={{ width: '100%', height: 320, borderRadius: radius.md }}
          contentFit="contain"
        />

        {!receipt.ocr_parsed_json ? (
          <Card>
            <Body weight="600">The server is reading it</Body>
            <Caption>Tesseract runs on the CPU. The fields fill themselves.</Caption>
          </Card>
        ) : null}

        {receipt.lines.length > 0 ? (
          <Card>
            <Body weight="600">Lines</Body>
            <View style={{ marginTop: spacing.sm, gap: 6 }}>
              {receipt.lines.map((line) => (
                <View
                  key={line.id}
                  style={{ flexDirection: 'row', justifyContent: 'space-between' }}
                >
                  <Caption>{line.line_text}</Caption>
                  <Caption>{formatMoney(line.line_amount)}</Caption>
                </View>
              ))}
            </View>
          </Card>
        ) : null}

        <Caption>Correct the details in the web interface.</Caption>
      </ScrollView>
    </Screen>
  )
}

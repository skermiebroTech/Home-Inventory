/**
 * The camera tab, with three modes.
 *
 * Photo: one picture goes to the model, which returns a filled form.
 * Barcode: the code goes to the product databases.
 * Receipt: the picture goes to the OCR pipeline.
 *
 * Every mode needs the network. Offline, the tab says so and offers the
 * plain add form instead.
 */

import { Ionicons } from '@expo/vector-icons'
import { CameraView, useCameraPermissions } from 'expo-camera'
import { useRouter } from 'expo-router'
import { useRef, useState } from 'react'
import { Alert, Pressable, ScrollView, View } from 'react-native'

import { api } from '@/api/client'
import type { AiJob, BarcodeProduct, ReceiptDetail } from '@/api/types'
import { Body, Button, Caption, Card, Screen, Title } from '@/components/ui'
import { isOnline } from '@/sync/engine'
import { radius, spacing, useTheme } from '@/theme'

type Mode = 'photo' | 'barcode' | 'receipt'

const MODES: Array<{ key: Mode; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
  { key: 'photo', label: 'Item', icon: 'camera' },
  { key: 'barcode', label: 'Barcode', icon: 'barcode' },
  { key: 'receipt', label: 'Receipt', icon: 'receipt' },
]

/** Ask the server until the job ends, or until the wait is too long. */
async function waitForJob(job: AiJob, seconds = 90): Promise<AiJob> {
  let current = job
  const until = Date.now() + seconds * 1000
  while (current.status !== 'succeeded' && current.status !== 'failed' && Date.now() < until) {
    await new Promise((resolve) => setTimeout(resolve, 2000))
    current = await api.get<AiJob>(`/api/ai/jobs/${current.id}`)
  }
  return current
}

export default function Scan() {
  const theme = useTheme()
  const router = useRouter()
  const camera = useRef<CameraView>(null)
  const [permission, requestPermission] = useCameraPermissions()
  const [mode, setMode] = useState<Mode>('photo')
  const [busy, setBusy] = useState<string | null>(null)
  const [locked, setLocked] = useState(false)

  if (!permission) return <Screen><View /></Screen>

  if (!permission.granted) {
    return (
      <Screen>
        <View style={{ flex: 1, justifyContent: 'center', padding: spacing.lg, gap: spacing.md }}>
          <Title>The camera is off</Title>
          <Body muted>
            HomeStock uses the camera to photograph an item, to read a barcode, and to
            capture a receipt.
          </Body>
          <Button title="Turn the camera on" onPress={() => void requestPermission()} />
        </View>
      </Screen>
    )
  }

  const guardOnline = async (): Promise<boolean> => {
    if (await isOnline()) return true
    Alert.alert(
      'No connection',
      'The scan needs the server. Add the item by hand, and the phone sends it later.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Add by hand', onPress: () => router.push('/items/add') },
      ],
    )
    return false
  }

  const takePhoto = async (): Promise<void> => {
    if (!(await guardOnline())) return
    const shot = await camera.current?.takePictureAsync({ quality: 0.7 })
    if (!shot) return

    setBusy(mode === 'receipt' ? 'Reading the receipt' : 'The model is looking')
    try {
      const form = new FormData()
      form.append('file', {
        uri: shot.uri,
        name: 'scan.jpg',
        type: 'image/jpeg',
      } as unknown as Blob)

      if (mode === 'receipt') {
        const receipt = await api.upload<ReceiptDetail>('/api/receipts/upload', form)
        router.push(`/receipts/${receipt.id}`)
        return
      }

      const started = await api.upload<AiJob>('/api/ai/recognize', form)
      const finished = await waitForJob(started)
      const first = finished.recognize_result?.items[0]

      if (finished.status === 'failed' || !first) {
        Alert.alert(
          'Nothing recognised',
          finished.error ?? 'The model did not name an item. Add it by hand.',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Add by hand', onPress: () => router.push('/items/add') },
          ],
        )
        return
      }

      // The form opens with the answer of the model, and with the photograph
      // waiting in the queue.
      router.push({
        pathname: '/items/add',
        params: {
          name: first.name,
          brand: first.brand ?? '',
          category: first.category ?? '',
          condition: first.condition ?? '',
          value: first.estimated_value_aud ?? '',
          photo: shot.uri,
        },
      })
    } catch (error) {
      Alert.alert('That did not work', error instanceof Error ? error.message : 'Unknown failure.')
    } finally {
      setBusy(null)
    }
  }

  const readBarcode = async (code: string): Promise<void> => {
    if (locked) return
    setLocked(true)
    setBusy('Looking the code up')
    try {
      const product = await api.get<BarcodeProduct>(
        `/api/items/barcode/${encodeURIComponent(code)}`,
      )
      router.push({
        pathname: '/items/add',
        params: {
          name: product.name ?? '',
          brand: product.brand ?? '',
          category: product.category ?? '',
          barcode: product.barcode,
        },
      })
    } catch {
      Alert.alert('No product found', `No database knows the code ${code}.`, [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Add by hand',
          onPress: () => router.push({ pathname: '/items/add', params: { barcode: code } }),
        },
      ])
    } finally {
      setBusy(null)
      setTimeout(() => setLocked(false), 2000)
    }
  }

  return (
    <Screen edges={['top']}>
      <View style={{ flex: 1 }}>
        <CameraView
          ref={camera}
          style={{ flex: 1 }}
          facing="back"
          barcodeScannerSettings={{
            barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'qr'],
          }}
          onBarcodeScanned={
            mode === 'barcode'
              ? (event) => {
                  void readBarcode(event.data)
                }
              : undefined
          }
        />

        <View style={{ position: 'absolute', top: spacing.md, left: 0, right: 0, alignItems: 'center' }}>
          <View
            style={{
              flexDirection: 'row',
              backgroundColor: '#000000aa',
              borderRadius: 999,
              padding: 4,
              gap: 4,
            }}
          >
            {MODES.map((entry) => (
              <Pressable
                key={entry.key}
                onPress={() => setMode(entry.key)}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 6,
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                  borderRadius: 999,
                  backgroundColor: mode === entry.key ? theme.accent : 'transparent',
                }}
              >
                <Ionicons name={entry.icon} size={15} color="#ffffff" />
                <Caption tone="#ffffff">{entry.label}</Caption>
              </Pressable>
            ))}
          </View>
        </View>

        {busy ? (
          <View
            style={{
              position: 'absolute',
              bottom: 130,
              left: spacing.lg,
              right: spacing.lg,
            }}
          >
            <Card>
              <Body weight="600">{busy}</Body>
              <Caption>The server runs the model on its CPU, so this takes a moment.</Caption>
            </Card>
          </View>
        ) : null}

        {mode !== 'barcode' ? (
          <View style={{ position: 'absolute', bottom: spacing.xl, left: 0, right: 0, alignItems: 'center' }}>
            <Pressable
              onPress={() => void takePhoto()}
              disabled={busy !== null}
              style={{
                width: 72,
                height: 72,
                borderRadius: 999,
                borderWidth: 4,
                borderColor: '#ffffff',
                backgroundColor: busy ? '#ffffff66' : '#ffffffdd',
              }}
            />
          </View>
        ) : (
          <View
            style={{
              position: 'absolute',
              bottom: spacing.xl,
              left: spacing.lg,
              right: spacing.lg,
            }}
          >
            <Card>
              <Body weight="600">Point the camera at a barcode</Body>
              <Caption>HomeStock reads it and asks the free product databases.</Caption>
            </Card>
          </View>
        )}
      </View>
    </Screen>
  )
}

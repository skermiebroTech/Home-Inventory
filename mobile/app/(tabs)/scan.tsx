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
import { CameraView, type CameraType, useCameraPermissions } from 'expo-camera'
import * as ImagePicker from 'expo-image-picker'
import { useRouter } from 'expo-router'
import { useRef, useState } from 'react'
import { Alert, Image, Pressable, ScrollView, View } from 'react-native'

import { api } from '@/api/client'
import type { AiJob, BarcodeProduct, ReceiptDetail } from '@/api/types'
import { Body, Button, Caption, Card, Screen, Title } from '@/components/ui'
import { getItemByTag } from '@/db'
import { isOnline } from '@/sync/engine'
import { radius, spacing, useTheme } from '@/theme'

type Mode = 'photo' | 'bulk' | 'barcode' | 'receipt'

const MODES: Array<{ key: Mode; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
  { key: 'photo', label: 'Item', icon: 'camera' },
  { key: 'bulk', label: 'Shelf', icon: 'grid' },
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
  const [facing, setFacing] = useState<CameraType>('back')
  const [busy, setBusy] = useState<string | null>(null)
  const [locked, setLocked] = useState(false)
  // One item often needs several photographs: the item, its label, and its
  // box. They all go to the model together.
  const [shots, setShots] = useState<string[]>([])

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

  /** Take one picture. In photo mode it joins the tray. */
  const shoot = async (): Promise<void> => {
    const shot = await camera.current?.takePictureAsync({ quality: 0.7 })
    if (!shot) return
    await keep(shot.uri)
  }

  /**
   * Open the camera application of the phone.
   *
   * This window has one lens and it cannot focus on a label held close. The
   * camera application of the phone offers every lens, the macro mode, and
   * tap to focus, so a close picture goes through it.
   */
  const shootWithThePhone = async (): Promise<void> => {
    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 })
    if (result.canceled || !result.assets[0]) return
    await keep(result.assets[0].uri)
  }

  /** Send a receipt straight up. Every other picture joins the tray. */
  const keep = async (uri: string): Promise<void> => {
    if (mode === 'receipt') {
      await sendReceipt(uri)
      return
    }
    setShots((current) => [...current, uri])
  }

  const sendReceipt = async (uri: string): Promise<void> => {
    if (!(await guardOnline())) return
    setBusy('Reading the receipt')
    try {
      const form = new FormData()
      form.append('file', {
        uri,
        name: 'receipt.jpg',
        type: 'image/jpeg',
      } as unknown as Blob)
      const receipt = await api.upload<ReceiptDetail>('/api/receipts/upload', form)
      router.push(`/receipts/${receipt.id}`)
    } catch (error) {
      Alert.alert(
        'That did not work',
        error instanceof Error ? error.message : 'Unknown failure.',
      )
    } finally {
      setBusy(null)
    }
  }

  /** Send every picture in the tray to the model. */
  const identify = async (): Promise<void> => {
    if (shots.length === 0) return
    if (!(await guardOnline())) return

    setBusy(
      shots.length === 1
        ? 'The model is looking'
        : `Reading ${shots.length} photographs`,
    )
    try {
      const form = new FormData()
      shots.forEach((uri, index) => {
        form.append('files', {
          uri,
          name: `scan-${index + 1}.jpg`,
          type: 'image/jpeg',
        } as unknown as Blob)
      })

      const path = mode === 'bulk' ? '/api/ai/bulk-scan' : '/api/ai/recognize'
      const started = await api.upload<AiJob>(path, form)
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

      // The form opens with the answer of the model. Every photograph waits
      // in the queue and goes up with the item.
      router.push({
        pathname: '/items/add',
        params: {
          name: first.name,
          brand: first.brand ?? '',
          model: first.model ?? '',
          serial: first.serial_number ?? '',
          category: first.category ?? '',
          condition: first.condition ?? '',
          value: first.estimated_value_aud ?? '',
          photos: shots.join('|'),
        },
      })
      setShots([])
    } catch (error) {
      Alert.alert(
        'That did not work',
        error instanceof Error ? error.message : 'Unknown failure.',
      )
    } finally {
      setBusy(null)
    }
  }

  /**
   * Return the asset tag that a HomeStock label holds.
   *
   * A label reads "http://tower:7850/a/0000042", and a person may also point
   * the camera at a sticker that carries the bare number.
   */
  const assetTagOf = (code: string): string | null => {
    const link = code.match(/\/a\/(\d{1,7})\b/)
    if (link?.[1]) return link[1].padStart(7, '0')
    const bare = code.trim()
    return /^\d{7}$/.test(bare) ? bare : null
  }

  const readBarcode = async (code: string): Promise<void> => {
    if (locked) return

    // Our own label comes first. It opens the item, offline as well, because
    // the phone already holds the row.
    const tag = assetTagOf(code)
    if (tag) {
      const item = await getItemByTag(tag)
      setLocked(true)
      setTimeout(() => setLocked(false), 2000)
      if (item) {
        router.push(`/items/${item.id}`)
      } else {
        Alert.alert(
          'No item here',
          `Nothing on this phone carries the tag ${tag}. Sync and try again.`,
        )
      }
      return
    }

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
          facing={facing}
          autofocus="on"
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
                onPress={() => {
                  setMode(entry.key)
                  setShots([])
                }}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 6,
                  paddingHorizontal: 12,
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
          <View
            style={{
              position: 'absolute',
              bottom: spacing.lg,
              left: 0,
              right: 0,
              gap: spacing.md,
            }}
          >
            {shots.length > 0 ? (
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={{ paddingHorizontal: spacing.lg, gap: 8 }}
              >
                {shots.map((uri) => (
                  <Pressable
                    key={uri}
                    onPress={() =>
                      setShots((current) => current.filter((entry) => entry !== uri))
                    }
                  >
                    <Image
                      source={{ uri }}
                      style={{
                        width: 64,
                        height: 64,
                        borderRadius: radius.sm,
                        borderWidth: 2,
                        borderColor: '#ffffffcc',
                      }}
                    />
                    <View
                      style={{
                        position: 'absolute',
                        top: -4,
                        right: -4,
                        backgroundColor: '#000000cc',
                        borderRadius: 999,
                        padding: 2,
                      }}
                    >
                      <Ionicons name="close" size={12} color="#ffffff" />
                    </View>
                  </Pressable>
                ))}
              </ScrollView>
            ) : null}

            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'center',
                gap: spacing.lg,
              }}
            >
              <View style={{ width: 104, flexDirection: 'row', gap: spacing.sm }}>
                <Pressable
                  onPress={() => setFacing(facing === 'back' ? 'front' : 'back')}
                  accessibilityLabel="Change the camera"
                  style={{
                    backgroundColor: '#000000aa',
                    borderRadius: 999,
                    padding: 12,
                  }}
                >
                  <Ionicons name="camera-reverse" size={20} color="#ffffff" />
                </Pressable>
                <Pressable
                  onPress={() => void shootWithThePhone()}
                  accessibilityLabel="Use the camera application of the phone"
                  style={{
                    backgroundColor: '#000000aa',
                    borderRadius: 999,
                    padding: 12,
                  }}
                >
                  <Ionicons name="phone-portrait" size={20} color="#ffffff" />
                </Pressable>
              </View>
              <Pressable
                onPress={() => void shoot()}
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
              <View style={{ width: 104 }}>
                {shots.length > 0 ? (
                  <Button
                    title={`Use ${shots.length}`}
                    icon="checkmark"
                    onPress={() => void identify()}
                  />
                ) : null}
              </View>
            </View>

            {mode !== 'receipt' ? (
              <View style={{ alignItems: 'center' }}>
                <Caption tone="#ffffffcc">
                  {shots.length === 0
                    ? 'Take the item, its label, and its box. For a close label, use the phone button.'
                    : 'Tap a picture to drop it.'}
                </Caption>
              </View>
            ) : null}
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

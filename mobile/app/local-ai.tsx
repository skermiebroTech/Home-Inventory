/**
 * The model that runs on the phone.
 *
 * A person downloads one model here, and the camera then names an item with
 * no server and no network. The weights are large, so this screen says what
 * a download costs before it starts, and it can give the space back.
 */

import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from 'expo-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, ScrollView, View } from 'react-native'

import { Body, Button, Caption, Card, Screen, Title } from '@/components/ui'
import {
  DownloadCancelled,
  MODELS,
  askServerToCache,
  cancel,
  forgetOnServer,
  download,
  remove,
  serverModels,
  statusOf,
  totalBytes,
  unfinished,
  type DownloadProgress,
  type LocalModel,
  type ServerModel,
} from '@/ai/local'
import ProgressBar from '@/components/ProgressBar'
import { formatBytes, formatWait } from '@/lib/format'
import { useSettingsStore } from '@/store/settings'
import { spacing, useTheme } from '@/theme'

export default function LocalAi() {
  const theme = useTheme()
  const settings = useSettingsStore()
  const [ready, setReady] = useState<Record<string, boolean>>({})
  const [onDisk, setOnDisk] = useState<Record<string, number>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [progress, setProgress] = useState<DownloadProgress | null>(null)
  const [paused, setPaused] = useState<LocalModel | null>(null)
  const [onServer, setOnServer] = useState<ServerModel[]>([])
  //: The last reading of each server fetch, so the rate can be worked out.
  const samples = useRef<Record<string, { bytes: number; at: number; rate: number }>>(
    {},
  )

  /** Read the server again and work out how fast each fetch is going. */
  const refreshServer = useCallback(async (): Promise<void> => {
    const rows = await serverModels()
    const now = Date.now()
    for (const row of rows) {
      const last = samples.current[row.id]
      if (last && row.cached_bytes > last.bytes) {
        const seconds = (now - last.at) / 1000
        const sample = seconds > 0 ? (row.cached_bytes - last.bytes) / seconds : 0
        samples.current[row.id] = {
          bytes: row.cached_bytes,
          at: now,
          // Smoothed, like the download on the phone. A raw reading jumps.
          rate: last.rate ? last.rate * 0.7 + sample * 0.3 : sample,
        }
      } else if (!last) {
        samples.current[row.id] = { bytes: row.cached_bytes, at: now, rate: 0 }
      }
    }
    setOnServer(rows)
  }, [])

  const load = useCallback(async () => {
    const state: Record<string, boolean> = {}
    const sizes: Record<string, number> = {}
    for (const model of MODELS) {
      const status = await statusOf(model)
      state[model.id] = status.ready
      sizes[model.id] = status.bytes
    }
    setReady(state)
    setOnDisk(sizes)
    setPaused(await unfinished())
    await refreshServer()
  }, [refreshServer])

  const fetchModel = async (model: LocalModel): Promise<void> => {
    setBusy(model.id)
    setProgress(null)
    try {
      await download(model, setProgress)
      settings.setLocalModel(model.id)
      await load()
      Alert.alert(
        'The model is on the phone',
        'The camera uses it now. It works with no signal.',
      )
    } catch (error) {
      if (!(error instanceof DownloadCancelled)) {
        Alert.alert(
          'The download stopped',
          error instanceof Error ? error.message : 'Try again on WiFi.',
        )
      }
      await load()
    } finally {
      setBusy(null)
      setProgress(null)
    }
  }

  // The server takes many minutes over a model. Ask it again while it works,
  // so the screen moves instead of showing one figure until somebody leaves.
  useEffect(() => {
    if (!onServer.some((one) => one.fetching)) return
    const timer = setInterval(() => void refreshServer(), 3000)
    return () => clearInterval(timer)
  }, [onServer, refreshServer])

  const cacheOnServer = async (model: LocalModel): Promise<void> => {
    try {
      await askServerToCache(model)
      await load()
      Alert.alert(
        'The server is fetching it',
        'It downloads once, over its own connection. Every phone in the ' +
          'house then takes it from the local network in a minute.',
      )
    } catch (error) {
      Alert.alert(
        'The server would not',
        error instanceof Error ? error.message : 'It may be away.',
      )
    }
  }

  const serverRate = (id: string): number => samples.current[id]?.rate ?? 0

  /** Tell the server to stop fetching, and to throw the part away. */
  const stopServer = async (model: LocalModel): Promise<void> => {
    try {
      await forgetOnServer(model)
    } finally {
      delete samples.current[model.id]
      await refreshServer()
    }
  }

  const stop = async (): Promise<void> => {
    await cancel()
    await load()
  }

  useFocusEffect(
    useCallback(() => {
      void (async () => {
        await load()
        // Android may stop the application during a download of two
        // gigabytes. Opening this screen carries on from the bytes that
        // reached the phone, rather than waiting to be asked.
        const pending = await unfinished()
        if (pending && !busy) void fetchModel(pending)
      })()
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [load]),
  )


  const dropModel = (model: LocalModel): void => {
    Alert.alert(
      'Delete the model?',
      `This gives ${formatBytes(totalBytes(model))} back.`,
      [
      { text: 'Keep', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await remove(model)
          if (settings.localModel === model.id) settings.setLocalModel(null)
          await load()
        },
      },
    ])
  }

  return (
    <Screen edges={['bottom']}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}>
        <View>
          <Title>Recognition on the phone</Title>
          <Body muted>
            The phone can name an item without the server. It needs a model,
            which is a large download that stays on the phone.
          </Body>
        </View>

        {MODELS.map((model) => {
          const here = ready[model.id] ?? false
          const chosen = settings.localModel === model.id
          const working = busy === model.id
          const held = onServer.find((one) => one.id === model.id)

          return (
            <Card key={model.id}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <View style={{ flex: 1 }}>
                  <Body weight="600">{model.name}</Body>
                  <Caption>
                    {formatBytes(totalBytes(model))} · {model.note}
                  </Caption>
                  {!ready[model.id] && (onDisk[model.id] ?? 0) > 0 ? (
                    <Caption tone={theme.warn}>
                      {formatBytes(onDisk[model.id] ?? 0)} is already on the
                      phone.
                    </Caption>
                  ) : null}
                  {!ready[model.id] && !held?.fetching ? (
                    <Caption tone={held?.ready ? theme.accent : undefined}>
                      {held?.ready
                        ? 'Your server holds it. The download stays on your network.'
                        : 'From the internet. Your server does not hold it.'}
                    </Caption>
                  ) : null}
                </View>
                {chosen && here ? (
                  <Ionicons name="checkmark-circle" size={22} color={theme.accent} />
                ) : null}
              </View>

              {held?.fetching ? (
                <View style={{ marginTop: spacing.md, gap: 6 }}>
                  <ProgressBar
                    fraction={held.bytes > 0 ? held.cached_bytes / held.bytes : 0}
                  />
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Caption>
                      Your server: {formatBytes(held.cached_bytes)} of{' '}
                      {formatBytes(held.bytes)}
                    </Caption>
                    <View style={{ flex: 1 }} />
                    <Caption>
                      {serverRate(model.id) > 0
                        ? `${formatBytes(serverRate(model.id))}/s`
                        : 'Starting'}
                    </Caption>
                  </View>
                  <Caption>
                    {serverRate(model.id) > 0
                      ? `${formatWait(
                          (held.bytes - held.cached_bytes) / serverRate(model.id),
                        )} left. You can leave this screen.`
                      : 'You can leave this screen.'}
                  </Caption>
                </View>
              ) : null}

              {working ? (
                <View style={{ marginTop: spacing.md, gap: 6 }}>
                  <ProgressBar fraction={progress?.fraction ?? 0} />
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Caption>
                      {formatBytes(progress?.written ?? 0)} of{' '}
                      {formatBytes(progress?.total ?? totalBytes(model))}
                    </Caption>
                    <View style={{ flex: 1 }} />
                    <Caption>
                      {Math.round((progress?.fraction ?? 0) * 100)}%
                    </Caption>
                  </View>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Caption>
                      {progress?.perSecond
                        ? `${formatBytes(progress.perSecond)}/s`
                        : 'Starting'}
                    </Caption>
                    <View style={{ flex: 1 }} />
                    <Caption>
                      {progress?.secondsLeft !== undefined
                        ? `${formatWait(progress.secondsLeft)} left`
                        : ''}
                    </Caption>
                  </View>
                  <Caption>
                    It carries on where it stopped if the application closes.
                  </Caption>
                  <Button
                    title="Cancel"
                    variant="secondary"
                    icon="close"
                    onPress={() => void stop()}
                    style={{ marginTop: 4 }}
                  />
                </View>
              ) : (
                <View style={{ flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md }}>
                  {here ? (
                    <>
                      {!chosen ? (
                        <Button
                          title="Use this one"
                          variant="secondary"
                          onPress={() => settings.setLocalModel(model.id)}
                          style={{ flex: 1 }}
                        />
                      ) : null}
                      <Button
                        title={`Delete ${formatBytes(onDisk[model.id] ?? 0)}`}
                        variant="secondary"
                        icon="trash"
                        onPress={() => dropModel(model)}
                        style={{ flex: 1 }}
                      />
                    </>
                  ) : (
                    <>
                      <Button
                        title={
                          paused?.id === model.id
                            ? `Carry on · ${formatBytes(
                                Math.max(0, totalBytes(model) - (onDisk[model.id] ?? 0)),
                              )} left`
                            : `Download ${formatBytes(totalBytes(model))}`
                        }
                        icon="cloud-download"
                        onPress={() => void fetchModel(model)}
                        style={{ flex: 1 }}
                        disabled={busy !== null}
                      />
                      {(onDisk[model.id] ?? 0) > 0 ? (
                        <Button
                          title="Delete"
                          variant="secondary"
                          icon="trash"
                          onPress={() => dropModel(model)}
                          disabled={busy !== null}
                        />
                      ) : null}
                      {held?.fetching ? (
                        <Button
                          title="Stop the server"
                          variant="secondary"
                          icon="close"
                          onPress={() => void stopServer(model)}
                        />
                      ) : !held?.ready ? (
                        <Button
                          title="Keep on the server"
                          variant="secondary"
                          icon="cloud-upload"
                          onPress={() => void cacheOnServer(model)}
                          disabled={busy !== null}
                        />
                      ) : null}
                    </>
                  )}
                </View>
              )}
            </Card>
          )
        })}

        <Card>
          <Body weight="600">How it behaves</Body>
          <Caption>
            With a model here, the camera asks the phone first and never waits
            for the server. Without one, it asks the server as before. The
            first photograph after the application starts is slower, because
            the model has to reach memory.
          </Caption>
        </Card>
      </ScrollView>
    </Screen>
  )
}

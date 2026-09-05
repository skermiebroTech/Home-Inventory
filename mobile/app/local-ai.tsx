/**
 * The model that runs on the phone.
 *
 * A person downloads one model here, and the camera then names an item with
 * no server and no network. The weights are large, so this screen says what
 * a download costs before it starts, and it can give the space back.
 */

import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from 'expo-router'
import { useCallback, useState } from 'react'
import { Alert, ScrollView, View } from 'react-native'

import { Body, Button, Caption, Card, Screen, Title } from '@/components/ui'
import { MODELS, download, remove, statusOf, type LocalModel } from '@/ai/local'
import { useSettingsStore } from '@/store/settings'
import { spacing, useTheme } from '@/theme'

export default function LocalAi() {
  const theme = useTheme()
  const settings = useSettingsStore()
  const [ready, setReady] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)

  const load = useCallback(async () => {
    const state: Record<string, boolean> = {}
    for (const model of MODELS) state[model.id] = (await statusOf(model)).ready
    setReady(state)
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load()
    }, [load]),
  )

  const fetchModel = async (model: LocalModel): Promise<void> => {
    setBusy(model.id)
    setProgress(0)
    try {
      await download(model, setProgress)
      settings.setLocalModel(model.id)
      await load()
      Alert.alert(
        'The model is on the phone',
        'The camera uses it now. It works with no signal.',
      )
    } catch (error) {
      Alert.alert(
        'The download stopped',
        error instanceof Error ? error.message : 'Try again on WiFi.',
      )
    } finally {
      setBusy(null)
    }
  }

  const dropModel = (model: LocalModel): void => {
    Alert.alert('Remove the model?', `This gives ${model.size} back.`, [
      { text: 'Keep', style: 'cancel' },
      {
        text: 'Remove',
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

          return (
            <Card key={model.id}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <View style={{ flex: 1 }}>
                  <Body weight="600">{model.name}</Body>
                  <Caption>
                    {model.size} · {model.note}
                  </Caption>
                </View>
                {chosen && here ? (
                  <Ionicons name="checkmark-circle" size={22} color={theme.accent} />
                ) : null}
              </View>

              {working ? (
                <View style={{ marginTop: spacing.md }}>
                  <View
                    style={{
                      height: 6,
                      borderRadius: 999,
                      backgroundColor: theme.border,
                      overflow: 'hidden',
                    }}
                  >
                    <View
                      style={{
                        height: 6,
                        width: `${Math.round(progress * 100)}%`,
                        backgroundColor: theme.accent,
                      }}
                    />
                  </View>
                  <Caption>
                    {Math.round(progress * 100)}% · keep this screen open
                  </Caption>
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
                        title="Remove"
                        variant="secondary"
                        icon="trash"
                        onPress={() => dropModel(model)}
                        style={{ flex: 1 }}
                      />
                    </>
                  ) : (
                    <Button
                      title={`Download ${model.size}`}
                      icon="cloud-download"
                      onPress={() => void fetchModel(model)}
                      style={{ flex: 1 }}
                      disabled={busy !== null}
                    />
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

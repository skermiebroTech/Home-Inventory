/** Locations, tags, lending, maintenance, and the settings. */

import { useFocusEffect, useRouter } from 'expo-router'
import { useCallback, useState } from 'react'
import { Alert, ScrollView, Switch, View } from 'react-native'

import { Body, Button, Caption, Card, ListRow, Screen, Title } from '@/components/ui'
import {
  listCables,
  listItems,
  listLocations,
  listMaintenance,
  listSpares,
  listTags,
  resetDatabase,
} from '@/db'
import { plural, relativeTime } from '@/lib/format'
import { NfcUnavailableError, scanAndLookup } from '@/lib/nfc'
import { clearReminders, scheduleReminders } from '@/lib/notifications'
import { useAuthStore } from '@/store/auth'
import { useSettingsStore } from '@/store/settings'
import { useSyncStore } from '@/store/sync'
import { spacing, useTheme } from '@/theme'

export default function More() {
  const theme = useTheme()
  const router = useRouter()
  const { user, serverUrl, signOut } = useAuthStore()
  const settings = useSettingsStore()
  const sync = useSyncStore()
  const [counts, setCounts] = useState({
    locations: 0,
    tags: 0,
    lent: 0,
    due: 0,
    spares: 0,
    lowSpares: 0,
    cables: 0,
  })

  useFocusEffect(
    useCallback(() => {
      void (async () => {
        const [locations, tags, items, logs, spares, cables] = await Promise.all([
          listLocations(),
          listTags(),
          listItems({ limit: 500 }),
          listMaintenance(),
          listSpares(),
          listCables(),
        ])
        setCounts({
          locations: locations.length,
          tags: tags.length,
          lent: items.filter((item) => item.is_lent).length,
          due: logs.filter((log) => log.next_due_date !== null).length,
          spares: spares.length,
          lowSpares: spares.filter((spare) => spare.is_low).length,
          cables: cables.reduce((sum, cable) => sum + cable.quantity, 0),
        })
      })()
    }, []),
  )

  const readTag = async (): Promise<void> => {
    try {
      const found = await scanAndLookup()
      if (found.target_type === 'item') router.push(`/items/${found.target_id}`)
      else router.push('/(tabs)/items')
    } catch (error) {
      Alert.alert(
        error instanceof NfcUnavailableError ? 'No NFC here' : 'Nothing found',
        error instanceof Error ? error.message : 'The tag did not read.',
      )
    }
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}>
        <Title>More</Title>

        <Card style={{ padding: 0 }}>
          <ListRow
            title="Locations"
            subtitle={`${plural(counts.locations, 'room, zone, or container', 'rooms, zones, and containers')}`}
            icon="map"
            onPress={() => router.push('/(tabs)/items')}
          />
          <ListRow
            title="Tags"
            subtitle={plural(counts.tags, 'tag')}
            icon="pricetags"
            onPress={() => router.push('/(tabs)/items')}
          />
          <ListRow
            title="Out on loan"
            subtitle={plural(counts.lent, 'item')}
            icon="hand-left"
            onPress={() => router.push('/(tabs)/items')}
          />
          <ListRow
            title="Maintenance"
            subtitle={`${plural(counts.due, 'date')} recorded`}
            icon="construct"
            onPress={() => router.push('/(tabs)/home')}
          />
          <ListRow
            title="Spares"
            subtitle={
              counts.lowSpares > 0
                ? `${plural(counts.spares, 'row')}, ${counts.lowSpares} running low`
                : plural(counts.spares, 'row')
            }
            icon="cube"
            onPress={() => router.push('/spares')}
          />
          <ListRow
            title="Cables"
            subtitle={plural(counts.cables, 'lead')}
            icon="git-branch"
            onPress={() => router.push('/cables')}
          />
          <ListRow
            title="Recognition on the phone"
            subtitle={
              settings.localModel
                ? 'A model is on the phone. The camera uses it.'
                : 'Off. The camera asks the server.'
            }
            icon="hardware-chip"
            onPress={() => router.push('/local-ai')}
          />
          <ListRow
            title="Read an NFC tag"
            subtitle="Hold the phone against a labelled item or box"
            icon="radio"
            onPress={() => void readTag()}
          />
        </Card>

        <Card>
          <Body weight="600">Sync</Body>
          <Caption>
            Last sync {relativeTime(sync.lastSync)}. {plural(sync.pending, 'change')} and{' '}
            {plural(sync.queuedPhotos, 'photograph')} are waiting.
          </Caption>
          {sync.lastFailures.length > 0 ? (
            <View style={{ marginTop: spacing.sm }}>
              <Caption tone={theme.danger}>
                {plural(sync.lastFailures.length, 'change')} could not be sent:
              </Caption>
              {sync.lastFailures.slice(0, 3).map((message) => (
                <Caption key={message}>{message}</Caption>
              ))}
            </View>
          ) : null}

          <View style={{ marginTop: spacing.md }}>
            <Button
              title={sync.running ? 'Syncing' : 'Sync now'}
              icon="sync"
              loading={sync.running}
              onPress={() => void sync.run()}
            />
          </View>
        </Card>

        <Card>
          <Body weight="600">Settings</Body>

          <View style={{ marginTop: spacing.md, gap: spacing.md }}>
            <Row
              label="Send photographs over WiFi only"
              hint="A photograph is large. This keeps it off your mobile data."
              value={settings.photosOnWifiOnly}
              onChange={(next) => void settings.update({ photosOnWifiOnly: next })}
            />
            <Row
              label="Sync when the application opens"
              value={settings.syncOnOpen}
              onChange={(next) => void settings.update({ syncOnOpen: next })}
            />
            <Row
              label="Reminders"
              hint="A warranty that ends, a service that is due, or an item that is still out."
              value={settings.reminders}
              onChange={async (next) => {
                await settings.update({ reminders: next })
                if (next) await scheduleReminders()
                else await clearReminders()
              }}
            />
          </View>
        </Card>

        <Card>
          <Body weight="600">Account</Body>
          <Caption>{user?.email}</Caption>
          <Caption>{serverUrl}</Caption>
          <View style={{ marginTop: spacing.md, gap: spacing.sm }}>
            <Button
              title="Sign out"
              variant="secondary"
              icon="log-out"
              onPress={() => {
                Alert.alert('Sign out?', 'The local copy stays on the phone.', [
                  { text: 'Cancel', style: 'cancel' },
                  { text: 'Sign out', style: 'destructive', onPress: () => void signOut() },
                ])
              }}
            />
            <Button
              title="Delete the local copy"
              variant="danger"
              icon="trash"
              onPress={() => {
                Alert.alert(
                  'Delete the local copy?',
                  'Anything that has not reached the server goes away. The next sync reads everything again.',
                  [
                    { text: 'Cancel', style: 'cancel' },
                    {
                      text: 'Delete',
                      style: 'destructive',
                      onPress: async () => {
                        await resetDatabase()
                        await sync.refreshCounts()
                        await sync.run()
                      },
                    },
                  ],
                )
              }}
            />
          </View>
        </Card>

        <Caption>HomeStock {serverUrl ? `· ${serverUrl}` : ''}</Caption>
      </ScrollView>
    </Screen>
  )
}

function Row({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint?: string
  value: boolean
  onChange: (next: boolean) => void
}) {
  const theme = useTheme()
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.md }}>
      <View style={{ flex: 1 }}>
        <Body>{label}</Body>
        {hint ? <Caption>{hint}</Caption> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ true: theme.accent, false: theme.border }}
      />
    </View>
  )
}

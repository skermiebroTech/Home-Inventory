/** The dashboard. Every number comes from the local database. */

import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect, useRouter } from 'expo-router'
import { useCallback, useEffect, useState } from 'react'
import { RefreshControl, ScrollView, View } from 'react-native'

import { Badge, Body, Button, Caption, Card, ListRow, Screen, Title } from '@/components/ui'
import { listItems, listMaintenance, type LocalItem } from '@/db'
import { daysUntil, formatMoney, plural, relativeTime } from '@/lib/format'
import type { MaintenanceLog } from '@/api/types'
import { useAuthStore } from '@/store/auth'
import { useSyncStore } from '@/store/sync'
import { spacing, useTheme } from '@/theme'

interface Totals {
  items: number
  value: number
  lent: number
}

export default function Home() {
  const theme = useTheme()
  const router = useRouter()
  const user = useAuthStore((state) => state.user)
  const sync = useSyncStore()
  const [totals, setTotals] = useState<Totals>({ items: 0, value: 0, lent: 0 })
  const [recent, setRecent] = useState<LocalItem[]>([])
  const [due, setDue] = useState<MaintenanceLog[]>([])

  const load = useCallback(async () => {
    const items = await listItems({ limit: 500 })
    setTotals({
      items: items.length,
      value: items.reduce(
        (sum, item) =>
          sum + Number.parseFloat(item.current_value ?? item.purchase_price ?? '0') * item.quantity,
        0,
      ),
      lent: items.filter((item) => item.is_lent).length,
    })
    setRecent(
      [...items]
        .sort((left, right) => (right.created_at ?? '').localeCompare(left.created_at ?? ''))
        .slice(0, 5),
    )
    const logs = await listMaintenance()
    setDue(
      logs.filter((log) => {
        const days = daysUntil(log.next_due_date)
        return days !== null && days <= 30
      }),
    )
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load()
    }, [load]),
  )

  // The first sync finishes after this screen has already read the database.
  // Reading again when the sync stamp changes keeps the numbers honest.
  useEffect(() => {
    void load()
  }, [load, sync.lastSync])

  const refresh = async (): Promise<void> => {
    await sync.run()
    await load()
  }

  return (
    <Screen>
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
        refreshControl={
          <RefreshControl refreshing={sync.running} onRefresh={() => void refresh()} tintColor={theme.muted} />
        }
      >
        <View>
          <Title>Hello {user?.name?.split(' ')[0] ?? 'there'}</Title>
          <Caption>
            Synced {relativeTime(sync.lastSync)}
            {sync.pending > 0 ? ` · ${plural(sync.pending, 'change')} waiting` : ''}
            {sync.queuedPhotos > 0
              ? ` · ${plural(sync.queuedPhotos, 'photograph')} queued`
              : ''}
          </Caption>
        </View>

        {sync.lastError ? (
          <Card style={{ borderColor: theme.warn }}>
            <Caption tone={theme.warn}>{sync.lastError}</Caption>
            <Caption>Everything below still works. The phone sends the changes later.</Caption>
          </Card>
        ) : null}

        {sync.lastFailures.length > 0 ? (
          <Card style={{ borderColor: theme.danger }}>
            <Caption tone={theme.danger}>
              {plural(sync.lastFailures.length, 'change')} could not be sent.
              {' '}
              {sync.lastFailures[0]}
            </Caption>
            <Caption>
              The change is still on the phone. Correct it and sync again.
            </Caption>
          </Card>
        ) : null}

        {sync.lastConflicts > 0 ? (
          <Card style={{ borderColor: theme.warn }}>
            <Caption tone={theme.warn}>
              The server had a newer copy of {sync.lastConflicts}{' '}
              {sync.lastConflicts === 1 ? 'record' : 'records'}. Its version won.
            </Caption>
          </Card>
        ) : null}

        <View style={{ flexDirection: 'row', gap: spacing.md }}>
          <Card style={{ flex: 1 }}>
            <Caption>Items</Caption>
            <Title>{totals.items}</Title>
          </Card>
          <Card style={{ flex: 1 }}>
            <Caption>Value</Caption>
            <Title>{formatMoney(totals.value)}</Title>
          </Card>
        </View>

        <View style={{ flexDirection: 'row', gap: spacing.md }}>
          <Button
            title="Quick add"
            icon="camera"
            onPress={() => router.push('/(tabs)/scan')}
            style={{ flex: 1 }}
          />
          <Button
            title="Type one"
            icon="add"
            variant="secondary"
            onPress={() => router.push('/items/add')}
            style={{ flex: 1 }}
          />
        </View>

        {due.length > 0 ? (
          <Card style={{ padding: 0 }}>
            <View style={{ padding: spacing.lg, paddingBottom: spacing.sm }}>
              <Body weight="600">Service due</Body>
            </View>
            {due.slice(0, 4).map((log) => (
              <ListRow
                key={log.id}
                title={log.description}
                subtitle={`Due ${log.next_due_date}`}
                onPress={() => router.push(`/items/${log.item_id}`)}
                right={
                  <Badge
                    text={`${daysUntil(log.next_due_date)} d`}
                    tone={(daysUntil(log.next_due_date) ?? 0) < 0 ? theme.danger : theme.warn}
                  />
                }
              />
            ))}
          </Card>
        ) : null}

        {totals.lent > 0 ? (
          <Card>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
              <Ionicons name="hand-left" size={18} color={theme.warn} />
              <Body>{plural(totals.lent, 'item')} out on loan.</Body>
            </View>
          </Card>
        ) : null}

        <Card style={{ padding: 0 }}>
          <View style={{ padding: spacing.lg, paddingBottom: spacing.sm }}>
            <Body weight="600">Recent</Body>
          </View>
          {recent.length === 0 ? (
            <View style={{ padding: spacing.lg }}>
              <Caption>No item yet. Point the camera at something.</Caption>
            </View>
          ) : (
            recent.map((item) => (
              <ListRow
                key={item.id}
                title={item.name}
                subtitle={item.category ?? item.brand ?? undefined}
                onPress={() => router.push(`/items/${item.id}`)}
                right={<Caption>{formatMoney(item.current_value ?? item.purchase_price)}</Caption>}
              />
            ))
          )}
        </Card>
      </ScrollView>
    </Screen>
  )
}

/**
 * The spares shelf, on the phone.
 *
 * The point of this screen is the moment you fit a filter in the shed: one
 * tap takes it off the shelf. It works with no signal, like every other
 * write, and the count reaches the server on the next sync.
 */

import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from 'expo-router'
import { useCallback, useState } from 'react'
import { FlatList, Pressable, RefreshControl, View } from 'react-native'

import type { SpareWithComponent } from '@/api/types'
import { Badge, Body, Caption, EmptyState, Screen } from '@/components/ui'
import { listSpares } from '@/db'
import { formatMoney } from '@/lib/format'
import { useSpare } from '@/sync/mutations'
import { useSyncStore } from '@/store/sync'
import { spacing, useTheme } from '@/theme'

export default function SparesScreen() {
  const theme = useTheme()
  const sync = useSyncStore()
  const [rows, setRows] = useState<SpareWithComponent[]>([])

  const load = useCallback(async () => {
    setRows(await listSpares())
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load()
    }, [load]),
  )

  const take = async (spare: SpareWithComponent, count: number): Promise<void> => {
    await useSpare(spare.id, count)
    await load()
    await sync.refreshCounts()
    void sync.run()
  }

  const low = rows.filter((row) => row.is_low).length

  return (
    <Screen edges={['bottom']}>
      <FlatList
        data={rows}
        keyExtractor={(row) => row.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm }}
        refreshControl={
          <RefreshControl
            refreshing={sync.running}
            tintColor={theme.muted}
            onRefresh={async () => {
              await sync.run()
              await load()
            }}
          />
        }
        ListHeaderComponent={
          low > 0 ? (
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: spacing.sm,
                marginBottom: spacing.sm,
              }}
            >
              <Ionicons name="warning" size={18} color={theme.warn} />
              <Caption tone={theme.warn}>
                {low === 1 ? '1 row has' : `${low} rows have`} reached the level you
                set.
              </Caption>
            </View>
          ) : null
        }
        ListEmptyComponent={
          <EmptyState
            icon="cube-outline"
            title="Nothing on the shelf"
            hint="Add spares in the web interface. They appear here on the next sync."
          />
        }
        renderItem={({ item }) => (
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: spacing.md,
              backgroundColor: theme.card,
              borderColor: item.is_low ? theme.warn : theme.border,
              borderWidth: 1,
              borderRadius: 12,
              padding: spacing.md,
            }}
          >
            <View style={{ flex: 1, minWidth: 0 }}>
              <Body numberOfLines={1} weight="500">
                {item.name}
              </Body>
              <Caption>
                {[item.brand, item.model_number].filter(Boolean).join(' · ') ||
                  'No brand'}
                {item.effective_price ? ` · ${formatMoney(item.effective_price)}` : ''}
              </Caption>
              {item.is_consumable ? <Badge text="consumable" tone={theme.warn} /> : null}
            </View>

            <View style={{ alignItems: 'flex-end' }}>
              <Body weight="600">{item.quantity}</Body>
              <Caption tone={item.is_low ? theme.warn : undefined}>
                {item.minimum_quantity > 0 ? `min ${item.minimum_quantity}` : 'on hand'}
              </Caption>
            </View>

            <View style={{ flexDirection: 'row', gap: spacing.xs }}>
              <Pressable
                onPress={() => void take(item, 1)}
                disabled={item.quantity === 0}
                accessibilityLabel={`Use one ${item.name}`}
                style={{
                  padding: 8,
                  borderRadius: 999,
                  backgroundColor: item.quantity === 0 ? theme.border : `${theme.accent}22`,
                }}
              >
                <Ionicons
                  name="remove"
                  size={18}
                  color={item.quantity === 0 ? theme.muted : theme.accent}
                />
              </Pressable>
              <Pressable
                onPress={() => void take(item, -1)}
                accessibilityLabel={`Put one ${item.name} back`}
                style={{ padding: 8, borderRadius: 999, backgroundColor: `${theme.accent}22` }}
              >
                <Ionicons name="add" size={18} color={theme.accent} />
              </Pressable>
            </View>
          </View>
        )}
      />
    </Screen>
  )
}

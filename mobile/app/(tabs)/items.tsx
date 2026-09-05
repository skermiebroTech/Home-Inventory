/** The item list. It reads SQLite, so it works with no network. */

import { Ionicons } from '@expo/vector-icons'
import { Image } from 'expo-image'
import { useFocusEffect, useRouter } from 'expo-router'
import { useCallback, useState } from 'react'
import { FlatList, Pressable, RefreshControl, View } from 'react-native'

import { mediaUrl } from '@/api/client'
import { Badge, Body, Caption, EmptyState, Input, Screen } from '@/components/ui'
import { getItemPhotos, listItems, type LocalItem } from '@/db'
import { formatMoney } from '@/lib/format'
import { useSyncStore } from '@/store/sync'
import { radius, spacing, useTheme } from '@/theme'

export default function Items() {
  const theme = useTheme()
  const router = useRouter()
  const sync = useSyncStore()
  const [search, setSearch] = useState('')
  const [rows, setRows] = useState<LocalItem[]>([])
  const [thumbs, setThumbs] = useState<Record<string, string | undefined>>({})

  const load = useCallback(async (term: string) => {
    const items = await listItems({ search: term, limit: 300 })
    setRows(items)
    const map: Record<string, string | undefined> = {}
    for (const item of items.slice(0, 60)) {
      const photos = await getItemPhotos(item.id)
      const first = photos[0]
      map[item.id] = mediaUrl(first?.thumbnail_path ?? first?.file_path)
    }
    setThumbs(map)
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load(search)
    }, [load, search]),
  )

  return (
    <Screen>
      <View style={{ padding: spacing.lg, paddingBottom: spacing.sm }}>
        <Input
          value={search}
          onChangeText={(text) => {
            setSearch(text)
            void load(text)
          }}
          placeholder="Search your items"
          autoCorrect={false}
          clearButtonMode="while-editing"
        />
      </View>

      <FlatList
        data={rows}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        refreshControl={
          <RefreshControl
            refreshing={sync.running}
            tintColor={theme.muted}
            onRefresh={async () => {
              await sync.run()
              await load(search)
            }}
          />
        }
        ListEmptyComponent={
          <EmptyState
            icon="cube-outline"
            title={search ? 'Nothing matches' : 'No item yet'}
            hint={
              search
                ? 'Try a shorter word.'
                : 'Pull down to sync, or open the scan tab and photograph something.'
            }
          />
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => router.push(`/items/${item.id}`)}
            style={({ pressed }) => ({
              flexDirection: 'row',
              alignItems: 'center',
              gap: spacing.md,
              paddingHorizontal: spacing.lg,
              paddingVertical: 10,
              backgroundColor: pressed ? theme.border : 'transparent',
            })}
          >
            {thumbs[item.id] ? (
              <Image
                source={{ uri: thumbs[item.id] }}
                style={{ width: 46, height: 46, borderRadius: radius.sm }}
                contentFit="cover"
                transition={120}
              />
            ) : (
              <View
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: radius.sm,
                  backgroundColor: theme.border,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Ionicons name="cube-outline" size={20} color={theme.muted} />
              </View>
            )}

            <View style={{ flex: 1, minWidth: 0 }}>
              <Body numberOfLines={1} weight="500">
                {item.name}
              </Body>
              <Caption>
                {[item.brand, item.category].filter(Boolean).join(' · ') || 'No category'}
              </Caption>
            </View>

            <View style={{ alignItems: 'flex-end', gap: 3 }}>
              <Caption>{formatMoney(item.current_value ?? item.purchase_price)}</Caption>
              {item.pending ? <Badge text="waiting" tone={theme.warn} /> : null}
              {item.is_lent ? <Badge text="lent" tone={theme.warn} /> : null}
            </View>
          </Pressable>
        )}
      />
    </Screen>
  )
}

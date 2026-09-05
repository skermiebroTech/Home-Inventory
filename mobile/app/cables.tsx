/**
 * The cables drawer, on the phone.
 *
 * You stand at the drawer and ask one question: have I got a lead with
 * USB-C on it? The search box answers that question from the local database,
 * so it answers with no signal.
 */

import { Image } from 'expo-image'
import { useFocusEffect } from 'expo-router'
import { useCallback, useState } from 'react'
import { FlatList, Pressable, RefreshControl, View } from 'react-native'

import { api, mediaUrl } from '@/api/client'
import type { CableView, OwnerPhoto } from '@/api/types'
import { Badge, Body, Caption, EmptyState, Input, Screen } from '@/components/ui'
import PhotoViewer from '@/components/PhotoViewer'
import { listCables, listOwnerPhotos } from '@/db'
import { useSyncStore } from '@/store/sync'
import { spacing, useTheme } from '@/theme'

export default function CablesScreen() {
  const theme = useTheme()
  const sync = useSyncStore()
  const [search, setSearch] = useState('')
  const [rows, setRows] = useState<CableView[]>([])

  const load = useCallback(async (text: string) => {
    setRows(await listCables(text))
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load(search)
    }, [load, search]),
  )

  const total = rows.reduce((sum, row) => sum + row.quantity, 0)

  const [shown, setShown] = useState<OwnerPhoto[]>([])
  const [viewing, setViewing] = useState<number | null>(null)
  const [title, setTitle] = useState('')

  /** Open the pictures of one cable, from the local copy. */
  const openPhotos = async (cable: CableView): Promise<void> => {
    const photos = await listOwnerPhotos('cable', cable.id)
    if (photos.length === 0) return
    setShown(photos)
    setTitle(cable.name)
    setViewing(0)
  }

  return (
    <Screen edges={['bottom']}>
      <View style={{ padding: spacing.lg, paddingBottom: spacing.sm }}>
        <Input
          value={search}
          onChangeText={(text) => {
            setSearch(text)
            void load(text)
          }}
          placeholder="USB-C, HDMI, a name, or a brand"
          autoCapitalize="none"
          autoCorrect={false}
        />
        {rows.length > 0 ? (
          <Caption>
            {rows.length} {rows.length === 1 ? 'entry' : 'entries'}, {total} in the
            drawer.
          </Caption>
        ) : null}
      </View>

      <FlatList
        data={rows}
        keyExtractor={(row) => row.id}
        contentContainerStyle={{ padding: spacing.lg, paddingTop: 0, gap: spacing.sm }}
        keyboardShouldPersistTaps="handled"
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
            icon="git-branch-outline"
            title={search ? 'No cable answers that' : 'No cables yet'}
            hint={
              search
                ? 'Try one end alone, such as USB-C.'
                : 'Add the leads in the web interface. They appear here on the next sync.'
            }
          />
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => void openPhotos(item)}
            disabled={item.photo_count === 0}
            style={{
              backgroundColor: theme.card,
              borderColor: theme.border,
              borderWidth: 1,
              borderRadius: 12,
              padding: spacing.md,
              gap: 2,
              flexDirection: 'row',
            }}
          >
            {item.thumbnail_path ? (
              <Image
                source={{ uri: mediaUrl(item.thumbnail_path) }}
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 8,
                  marginRight: spacing.md,
                }}
                contentFit="cover"
                transition={120}
              />
            ) : null}

            <View style={{ flex: 1, minWidth: 0 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
              <Body weight="500" numberOfLines={1}>
                {item.quantity > 1 ? `${item.quantity}x ` : ''}
                {item.name}
              </Body>
              <View style={{ flex: 1 }} />
              {item.kind ? <Badge text={item.kind} /> : null}
            </View>

            <Caption>
              {[item.ends, item.length_label, item.specification, item.colour]
                .filter(Boolean)
                .join(' · ') || 'No details recorded'}
            </Caption>
            <Caption>
              {item.location_name ?? 'No place recorded'}
              {item.item_name ? ` · for the ${item.item_name}` : ''}
            </Caption>
            {item.notes ? <Caption>{item.notes}</Caption> : null}
            {item.photo_count > 1 ? (
              <Caption>{item.photo_count} photographs. Tap to see them.</Caption>
            ) : null}
            </View>
          </Pressable>
        )}
      />

      <PhotoViewer
        photos={shown}
        index={viewing}
        title={title}
        onClose={() => setViewing(null)}
        onSetPrimary={async (photoId) => {
          await api.put(`/api/photos/${photoId}/primary`, {})
          await sync.run()
          await load(search)
        }}
      />
    </Screen>
  )
}

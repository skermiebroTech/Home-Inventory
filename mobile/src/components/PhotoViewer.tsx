/**
 * The full screen photograph viewer.
 *
 * It opens on the picture you tapped, and a swipe moves to the next one. The
 * star sets the picture that every list shows for that row. The star needs
 * the server, because the picture itself lives there.
 */

import { Ionicons } from '@expo/vector-icons'
import { Image } from 'expo-image'
import { useState } from 'react'
import {
  Alert,
  Dimensions,
  FlatList,
  Modal,
  Pressable,
  View,
  useWindowDimensions,
} from 'react-native'

import { mediaUrl } from '@/api/client'
import { Body, Caption } from '@/components/ui'
import { spacing } from '@/theme'

export interface ViewablePhoto {
  id: string
  file_path: string
  is_primary: boolean
  caption?: string | null
}

export default function PhotoViewer({
  photos,
  index,
  title,
  onClose,
  onSetPrimary,
}: {
  photos: ViewablePhoto[]
  /** The picture to open on. Null closes the viewer. */
  index: number | null
  title?: string
  onClose: () => void
  /** Absent when the caller cannot change the thumbnail. */
  onSetPrimary?: (photoId: string) => Promise<void>
}) {
  const window = useWindowDimensions()
  const [current, setCurrent] = useState(index ?? 0)
  const [saving, setSaving] = useState(false)

  const open = index !== null
  const shown = photos[current] ?? photos[0]
  if (!open || !shown) return null
  // A flag out of SQLite arrives as 0 or 1, and a React prop wants a boolean.
  const photo = { ...shown, is_primary: Boolean(shown.is_primary) }

  const makeThumbnail = async (): Promise<void> => {
    if (!onSetPrimary || photo.is_primary) return
    setSaving(true)
    try {
      await onSetPrimary(photo.id)
      // The list puts the thumbnail first, so the picture under the finger
      // would change. The viewer closes instead, and the star shows on the
      // strip behind it.
      onClose()
    } catch (error) {
      Alert.alert(
        'That did not work',
        error instanceof Error
          ? error.message
          : 'The thumbnail needs the server. Try again with a connection.',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      visible
      transparent={false}
      animationType="fade"
      onRequestClose={onClose}
      // The viewer follows the phone, so a wide photograph fills a wide
      // screen.
      supportedOrientations={['portrait', 'landscape']}
      onShow={() => setCurrent(index ?? 0)}
    >
      <View style={{ flex: 1, backgroundColor: '#000000' }}>
        <FlatList
          data={photos}
          horizontal
          pagingEnabled
          initialScrollIndex={index ?? 0}
          getItemLayout={(_, position) => ({
            length: window.width,
            offset: window.width * position,
            index: position,
          })}
          keyExtractor={(row) => row.id}
          showsHorizontalScrollIndicator={false}
          onMomentumScrollEnd={(event) =>
            setCurrent(
              Math.round(event.nativeEvent.contentOffset.x / window.width),
            )
          }
          renderItem={({ item }) => (
            <Image
              source={{ uri: mediaUrl(item.file_path) }}
              style={{ width: window.width, height: window.height }}
              contentFit="contain"
              transition={120}
            />
          )}
        />

        <View
          style={{
            position: 'absolute',
            top: spacing.xl,
            left: spacing.lg,
            right: spacing.lg,
            flexDirection: 'row',
            alignItems: 'center',
            gap: spacing.md,
          }}
        >
          <Pressable
            onPress={onClose}
            accessibilityLabel="Close"
            style={{ backgroundColor: '#000000aa', borderRadius: 999, padding: 8 }}
          >
            <Ionicons name="close" size={22} color="#ffffff" />
          </Pressable>

          <View style={{ flex: 1 }}>
            {title ? (
              <Body weight="600" tone="#ffffff" numberOfLines={1}>
                {title}
              </Body>
            ) : null}
            <Caption tone="#ffffffcc">
              {current + 1} of {photos.length}
              {photo.caption ? ` · ${photo.caption}` : ''}
            </Caption>
          </View>

          {onSetPrimary ? (
            <Pressable
              onPress={() => void makeThumbnail()}
              disabled={saving || photo.is_primary}
              accessibilityLabel={
                photo.is_primary ? 'This is the thumbnail' : 'Use as the thumbnail'
              }
              style={{
                backgroundColor: photo.is_primary ? '#ffffff22' : '#000000aa',
                borderRadius: 999,
                padding: 8,
              }}
            >
              <Ionicons
                name={photo.is_primary ? 'star' : 'star-outline'}
                size={22}
                color={photo.is_primary ? '#fbbf24' : '#ffffff'}
              />
            </Pressable>
          ) : null}
        </View>

        {onSetPrimary && !photo.is_primary ? (
          <View
            style={{
              position: 'absolute',
              bottom: spacing.xl,
              left: 0,
              right: 0,
              alignItems: 'center',
            }}
          >
            <Caption tone="#ffffffcc">
              The star makes this picture the thumbnail.
            </Caption>
          </View>
        ) : null}
      </View>
    </Modal>
  )
}

/** The width of the screen, for a caller that lays a row of pictures out. */
export const screenWidth = Dimensions.get('window').width

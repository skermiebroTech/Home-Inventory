/**
 * A progress bar with a sheen that travels across it.
 *
 * The bar tells you two things at once. The width says how much is done, and
 * the light moving over it says the work is alive: a download of two
 * gigabytes can sit on the same percentage for a while, and a still bar looks
 * like a stalled one.
 *
 * The sheen runs on the native driver, so it keeps moving while JavaScript is
 * busy writing a file to disk.
 */

import { useEffect, useRef } from 'react'
import { Animated, Easing, View } from 'react-native'

import { useTheme } from '@/theme'

export default function ProgressBar({
  fraction,
  height = 8,
  /** A finished bar stops shining. */
  busy = true,
}: {
  fraction: number
  height?: number
  busy?: boolean
}) {
  const theme = useTheme()
  const width = useRef(new Animated.Value(0)).current
  const sheen = useRef(new Animated.Value(0)).current

  // The width eases to the new figure. A download reports many small steps,
  // and easing turns them into one movement.
  useEffect(() => {
    Animated.timing(width, {
      toValue: Math.max(0, Math.min(1, fraction)),
      duration: 320,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start()
  }, [fraction, width])

  useEffect(() => {
    if (!busy) {
      sheen.stopAnimation()
      return
    }
    const loop = Animated.loop(
      Animated.timing(sheen, {
        toValue: 1,
        duration: 1400,
        easing: Easing.inOut(Easing.quad),
        useNativeDriver: true,
      }),
    )
    loop.start()
    return () => loop.stop()
  }, [busy, sheen])

  return (
    <View
      style={{
        height,
        borderRadius: 999,
        backgroundColor: theme.border,
        overflow: 'hidden',
      }}
    >
      <Animated.View
        style={{
          height,
          borderRadius: 999,
          backgroundColor: theme.accent,
          overflow: 'hidden',
          width: width.interpolate({
            inputRange: [0, 1],
            outputRange: ['0%', '100%'],
          }),
        }}
      >
        {busy ? (
          <Animated.View
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              width: 90,
              backgroundColor: '#ffffff',
              opacity: 0.35,
              // From just off the left edge to well past the right one. The
              // percentage is of this block, not of the bar, so the sweep
              // suits a narrow bar and a wide one alike.
              transform: [
                {
                  translateX: sheen.interpolate({
                    inputRange: [0, 1],
                    outputRange: [-90, 400],
                  }),
                },
                { skewX: '-20deg' },
              ],
            }}
          />
        ) : null}
      </Animated.View>
    </View>
  )
}

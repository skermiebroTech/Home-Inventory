/** The shared pieces of the interface. */

import { Ionicons } from '@expo/vector-icons'
import type { ReactNode } from 'react'
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  View,
  type ViewStyle,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import { radius, spacing, useTheme } from '@/theme'

export function Screen({
  children,
  style,
  edges,
}: {
  children: ReactNode
  style?: ViewStyle
  edges?: Array<'top' | 'bottom' | 'left' | 'right'>
}) {
  const theme = useTheme()
  return (
    <SafeAreaView
      edges={edges ?? ['top']}
      style={[{ flex: 1, backgroundColor: theme.bg }, style]}
    >
      {children}
    </SafeAreaView>
  )
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  const theme = useTheme()
  return (
    <View
      style={[
        {
          backgroundColor: theme.card,
          borderColor: theme.border,
          borderWidth: StyleSheet.hairlineWidth,
          borderRadius: radius.md,
          padding: spacing.lg,
        },
        style,
      ]}
    >
      {children}
    </View>
  )
}

export function Title({ children }: { children: ReactNode }) {
  const theme = useTheme()
  return (
    <Text style={{ color: theme.text, fontSize: 22, fontWeight: '700', letterSpacing: -0.3 }}>
      {children}
    </Text>
  )
}

export function Body({
  children,
  muted,
  numberOfLines,
  weight,
}: {
  children: ReactNode
  muted?: boolean
  numberOfLines?: number
  weight?: '400' | '500' | '600'
}) {
  const theme = useTheme()
  return (
    <Text
      numberOfLines={numberOfLines}
      style={{ color: muted ? theme.muted : theme.text, fontSize: 14, fontWeight: weight ?? '400' }}
    >
      {children}
    </Text>
  )
}

export function Caption({ children, tone }: { children: ReactNode; tone?: string }) {
  const theme = useTheme()
  return <Text style={{ color: tone ?? theme.muted, fontSize: 12 }}>{children}</Text>
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  icon,
  loading,
  disabled,
  style,
}: {
  title: string
  onPress: () => void
  variant?: 'primary' | 'secondary' | 'danger'
  icon?: keyof typeof Ionicons.glyphMap
  loading?: boolean
  disabled?: boolean
  style?: ViewStyle
}) {
  const theme = useTheme()
  const background =
    variant === 'primary' ? theme.accent : variant === 'danger' ? theme.danger : 'transparent'
  const colour = variant === 'secondary' ? theme.text : theme.accentText

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        {
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: spacing.sm,
          backgroundColor: background,
          borderColor: variant === 'secondary' ? theme.border : background,
          borderWidth: variant === 'secondary' ? StyleSheet.hairlineWidth : 0,
          borderRadius: radius.sm,
          paddingVertical: 12,
          paddingHorizontal: spacing.lg,
          opacity: pressed || disabled || loading ? 0.7 : 1,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={colour} />
      ) : icon ? (
        <Ionicons name={icon} size={17} color={colour} />
      ) : null}
      <Text style={{ color: colour, fontWeight: '600', fontSize: 15 }}>{title}</Text>
    </Pressable>
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  const theme = useTheme()
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text
        style={{
          color: theme.muted,
          fontSize: 11,
          fontWeight: '600',
          textTransform: 'uppercase',
          letterSpacing: 0.5,
          marginBottom: 4,
        }}
      >
        {label}
      </Text>
      {children}
      {hint ? <Caption>{hint}</Caption> : null}
    </View>
  )
}

export function Input(props: TextInputProps) {
  const theme = useTheme()
  return (
    <TextInput
      placeholderTextColor={theme.muted}
      {...props}
      style={[
        {
          backgroundColor: theme.card,
          borderColor: theme.border,
          borderWidth: StyleSheet.hairlineWidth,
          borderRadius: radius.sm,
          paddingHorizontal: spacing.md,
          paddingVertical: 11,
          color: theme.text,
          fontSize: 15,
        },
        props.style,
      ]}
    />
  )
}

export function Badge({ text, tone }: { text: string; tone?: string }) {
  const theme = useTheme()
  const colour = tone ?? theme.muted
  return (
    <View
      style={{
        alignSelf: 'flex-start',
        backgroundColor: `${colour}22`,
        borderRadius: 999,
        paddingHorizontal: 8,
        paddingVertical: 2,
      }}
    >
      <Text style={{ color: colour, fontSize: 11, fontWeight: '600' }}>{text}</Text>
    </View>
  )
}

export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon: keyof typeof Ionicons.glyphMap
  title: string
  hint?: string
}) {
  const theme = useTheme()
  return (
    <View style={{ alignItems: 'center', paddingVertical: 48, gap: spacing.sm }}>
      <Ionicons name={icon} size={34} color={theme.muted} />
      <Body weight="600">{title}</Body>
      {hint ? (
        <Text style={{ color: theme.muted, fontSize: 13, textAlign: 'center', maxWidth: 260 }}>
          {hint}
        </Text>
      ) : null}
    </View>
  )
}

export function Loading({ label }: { label?: string }) {
  const theme = useTheme()
  return (
    <View style={{ padding: spacing.xl, alignItems: 'center', gap: spacing.sm }}>
      <ActivityIndicator color={theme.accent} />
      {label ? <Caption>{label}</Caption> : null}
    </View>
  )
}

export function ListRow({
  title,
  subtitle,
  right,
  icon,
  onPress,
}: {
  title: string
  subtitle?: string
  right?: ReactNode
  icon?: keyof typeof Ionicons.glyphMap
  onPress?: () => void
}) {
  const theme = useTheme()
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        gap: spacing.md,
        paddingVertical: 12,
        paddingHorizontal: spacing.lg,
        backgroundColor: pressed ? theme.border : 'transparent',
      })}
    >
      {icon ? <Ionicons name={icon} size={20} color={theme.muted} /> : null}
      <View style={{ flex: 1, minWidth: 0 }}>
        <Body numberOfLines={1} weight="500">
          {title}
        </Body>
        {subtitle ? <Caption>{subtitle}</Caption> : null}
      </View>
      {right ?? <Ionicons name="chevron-forward" size={16} color={theme.muted} />}
    </Pressable>
  )
}

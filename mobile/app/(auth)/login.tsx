/**
 * Sign in.
 *
 * Every household runs its own server, so the screen asks for the address
 * first. It is stored, and the next start goes straight to the password.
 */

import { Ionicons } from '@expo/vector-icons'
import { useState } from 'react'
import { KeyboardAvoidingView, Platform, ScrollView, View } from 'react-native'

import { Body, Button, Caption, Card, Field, Input, Screen, Title } from '@/components/ui'
import { useAuthStore } from '@/store/auth'
import { spacing, useTheme } from '@/theme'

export default function Login() {
  const theme = useTheme()
  const { serverUrl, signIn } = useAuthStore()
  const [server, setServer] = useState(serverUrl || 'http://homestock.local:7850')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (): Promise<void> => {
    setBusy(true)
    setError(null)
    try {
      await signIn(server.trim(), email.trim(), password)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The sign in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Screen edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', padding: spacing.lg }}>
          <View style={{ alignItems: 'center', marginBottom: spacing.xl, gap: spacing.sm }}>
            <Ionicons name="cube" size={40} color={theme.accent} />
            <Title>HomeStock</Title>
            <Caption>Your inventory, on your own server.</Caption>
          </View>

          <Card>
            <Field label="Server address" hint="For example http://192.168.1.20:7850">
              <Input
                value={server}
                onChangeText={setServer}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                placeholder="http://homestock.local:7850"
              />
            </Field>
            <Field label="Email">
              <Input
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                textContentType="username"
              />
            </Field>
            <Field label="Password">
              <Input
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                textContentType="password"
                onSubmitEditing={() => void submit()}
              />
            </Field>

            {error ? (
              <View style={{ marginBottom: spacing.md }}>
                <Body muted={false}>
                  <Caption tone={theme.danger}>{error}</Caption>
                </Body>
              </View>
            ) : null}

            <Button title="Sign in" onPress={() => void submit()} loading={busy} />
          </Card>

          <View style={{ marginTop: spacing.lg, alignItems: 'center' }}>
            <Caption>Make the first account in the web interface.</Caption>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  )
}

/**
 * The field set of an item.
 *
 * The add screen and the edit screen both use it, so a field never exists on
 * one and not on the other.
 */

import { useEffect, useState } from 'react'
import { Pressable, View } from 'react-native'

import type { Location } from '@/api/types'
import { listLocations } from '@/db'
import type { ItemDraft } from '@/sync/mutations'
import { radius, spacing, useTheme } from '@/theme'
import { Body, Caption, Field, Input } from './ui'

export const CONDITIONS = ['new', 'good', 'fair', 'poor'] as const

export interface ItemFormValues {
  name: string
  brand: string
  model: string
  serial_number: string
  category: string
  current_value: string
  quantity: string
  condition: string
  location_id: string | null
  purchase_date: string
  warranty_expires: string
  notes: string
  owner: string
}

export function emptyValues(overrides: Partial<ItemFormValues> = {}): ItemFormValues {
  return {
    name: '',
    brand: '',
    model: '',
    serial_number: '',
    category: '',
    current_value: '',
    quantity: '1',
    condition: '',
    location_id: null,
    purchase_date: '',
    warranty_expires: '',
    notes: '',
    owner: '',
    ...overrides,
  }
}

/** Turn the form values into the fields that the mutation writes. */
export function toDraft(values: ItemFormValues): ItemDraft {
  return {
    name: values.name.trim(),
    brand: values.brand.trim() || null,
    model: values.model.trim() || null,
    serial_number: values.serial_number.trim() || null,
    category: values.category.trim() || null,
    current_value: values.current_value.trim() || null,
    quantity: Number.parseInt(values.quantity, 10) || 1,
    condition: values.condition || null,
    location_id: values.location_id,
    purchase_date: values.purchase_date.trim() || null,
    warranty_expires: values.warranty_expires.trim() || null,
    notes: values.notes.trim() || null,
    owner: values.owner.trim() || null,
  }
}

export function Chip({
  label,
  active,
  onPress,
}: {
  label: string
  active: boolean
  onPress: () => void
}) {
  const theme = useTheme()
  return (
    <Pressable
      onPress={onPress}
      style={{
        paddingHorizontal: 12,
        paddingVertical: 7,
        borderRadius: radius.lg,
        borderWidth: 1,
        borderColor: active ? theme.accent : theme.border,
        backgroundColor: active ? `${theme.accent}22` : 'transparent',
      }}
    >
      <Caption tone={active ? theme.accent : theme.muted}>{label}</Caption>
    </Pressable>
  )
}

export default function ItemFields({
  values,
  onChange,
  autoFocus,
}: {
  values: ItemFormValues
  onChange: (values: ItemFormValues) => void
  autoFocus?: boolean
}) {
  const [locations, setLocations] = useState<Location[]>([])
  const [showMore, setShowMore] = useState(
    Boolean(
      values.serial_number ||
        values.model ||
        values.purchase_date ||
        values.warranty_expires,
    ),
  )

  useEffect(() => {
    void (async () => setLocations(await listLocations()))()
  }, [])

  const set = (key: keyof ItemFormValues, value: string | null) =>
    onChange({ ...values, [key]: value })

  return (
    <View>
      <Field label="Name">
        <Input
          value={values.name}
          onChangeText={(text) => set('name', text)}
          autoFocus={autoFocus}
          placeholder="Cordless drill"
        />
      </Field>

      <Field label="Brand">
        <Input value={values.brand} onChangeText={(text) => set('brand', text)} />
      </Field>

      <Field label="Category">
        <Input
          value={values.category}
          onChangeText={(text) => set('category', text)}
          placeholder="Tools"
        />
      </Field>

      <View style={{ flexDirection: 'row', gap: spacing.md }}>
        <View style={{ flex: 1 }}>
          <Field label="Value">
            <Input
              value={values.current_value}
              onChangeText={(text) => set('current_value', text)}
              keyboardType="decimal-pad"
            />
          </Field>
        </View>
        <View style={{ width: 96 }}>
          <Field label="Quantity">
            <Input
              value={values.quantity}
              onChangeText={(text) => set('quantity', text)}
              keyboardType="number-pad"
            />
          </Field>
        </View>
      </View>

      <Field label="Condition">
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm }}>
          <Chip
            label="Not stated"
            active={!values.condition}
            onPress={() => set('condition', '')}
          />
          {CONDITIONS.map((entry) => (
            <Chip
              key={entry}
              label={entry}
              active={values.condition === entry}
              onPress={() => set('condition', entry)}
            />
          ))}
        </View>
      </Field>

      <Field label="Location">
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm }}>
          <Chip
            label="None"
            active={values.location_id === null}
            onPress={() => set('location_id', null)}
          />
          {locations.map((location) => (
            <Chip
              key={location.id}
              label={location.name}
              active={values.location_id === location.id}
              onPress={() => set('location_id', location.id)}
            />
          ))}
        </View>
      </Field>

      <Pressable onPress={() => setShowMore((open) => !open)}>
        <Body weight="600">{showMore ? 'Fewer fields' : 'More fields'}</Body>
      </Pressable>

      {showMore ? (
        <View style={{ marginTop: spacing.md }}>
          <Field label="Model">
            <Input value={values.model} onChangeText={(text) => set('model', text)} />
          </Field>
          <Field label="Serial number">
            <Input
              value={values.serial_number}
              onChangeText={(text) => set('serial_number', text)}
              autoCapitalize="characters"
            />
          </Field>
          <Field label="Purchase date" hint="Write it as 2026-03-12.">
            <Input
              value={values.purchase_date}
              onChangeText={(text) => set('purchase_date', text)}
              placeholder="2026-03-12"
              keyboardType="numbers-and-punctuation"
            />
          </Field>
          <Field label="Warranty ends" hint="Write it as 2028-03-12.">
            <Input
              value={values.warranty_expires}
              onChangeText={(text) => set('warranty_expires', text)}
              placeholder="2028-03-12"
              keyboardType="numbers-and-punctuation"
            />
          </Field>
        </View>
      ) : null}

      <Field label="Owner">
        <Input
          value={values.owner}
          onChangeText={(text) => set('owner', text)}
          placeholder="The person whose thing this is"
          autoCapitalize="words"
        />
      </Field>

      <Field label="Notes">
        <Input
          value={values.notes}
          onChangeText={(text) => set('notes', text)}
          multiline
          numberOfLines={3}
        />
      </Field>
    </View>
  )
}

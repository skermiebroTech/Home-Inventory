/** The item form. The add page and the detail page both use it. */

import type { Condition, ItemDetail, ItemWrite } from '@/api/types'
import { useState } from 'react'

import { useOwners } from '@/hooks/usePhotos'

import { LocationSelect, TagPicker } from './pickers'
import { Button, Field, Input, Select, Textarea } from './ui'

const CONDITIONS: Condition[] = ['new', 'good', 'fair', 'poor']

export interface ItemFormValues extends ItemWrite {
  tag_ids: string[]
}

export function emptyItem(overrides: Partial<ItemFormValues> = {}): ItemFormValues {
  return {
    name: '',
    description: null,
    location_id: null,
    category: null,
    subcategory: null,
    brand: null,
    model: null,
    serial_number: null,
    barcode: null,
    purchase_price: null,
    current_value: null,
    purchase_date: null,
    purchase_location: null,
    warranty_expires: null,
    condition: null,
    quantity: 1,
    notes: null,
    owner: null,
    tag_ids: [],
    ...overrides,
  }
}

export function itemToValues(item: ItemDetail): ItemFormValues {
  return {
    name: item.name,
    description: item.description,
    location_id: item.location_id,
    category: item.category,
    subcategory: item.subcategory,
    brand: item.brand,
    model: item.model,
    serial_number: item.serial_number,
    barcode: item.barcode,
    purchase_price: item.purchase_price,
    current_value: item.current_value,
    purchase_date: item.purchase_date,
    purchase_location: item.purchase_location,
    warranty_expires: item.warranty_expires,
    condition: item.condition,
    quantity: item.quantity,
    notes: item.notes,
    owner: item.owner,
    tag_ids: item.tags.map((tag) => tag.id),
  }
}

export default function ItemForm({
  values,
  onChange,
  onSubmit,
  onCancel,
  saving,
  submitLabel = 'Save',
  extra,
}: {
  values: ItemFormValues
  onChange: (values: ItemFormValues) => void
  onSubmit: () => void
  onCancel?: () => void
  saving?: boolean
  submitLabel?: string
  extra?: React.ReactNode
}) {
  const [showMore, setShowMore] = useState(false)
  const { data: owners } = useOwners()
  const set = <K extends keyof ItemFormValues>(key: K, value: ItemFormValues[K]) =>
    onChange({ ...values, [key]: value })

  const text = (key: keyof ItemFormValues) => (event: { target: { value: string } }) =>
    set(key, (event.target.value || null) as ItemFormValues[typeof key])

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
      className="space-y-4"
    >
      {extra}

      <Field label="Name">
        <Input
          required
          autoFocus
          value={values.name}
          onChange={(event) => set('name', event.target.value)}
          placeholder="DeWalt DCD771 cordless drill"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Location">
          <LocationSelect
            value={values.location_id ?? null}
            onChange={(id) => set('location_id', id)}
          />
        </Field>
        <Field label="Quantity">
          <Input
            type="number"
            min={0}
            value={values.quantity ?? 1}
            onChange={(event) => set('quantity', Number(event.target.value))}
          />
        </Field>
        <Field label="Category">
          <Input value={values.category ?? ''} onChange={text('category')} placeholder="Tools" />
        </Field>
        <Field label="Owner" hint="The person in the house whose thing this is.">
          <Input
            list="item-owners"
            value={values.owner ?? ''}
            onChange={text('owner')}
            placeholder="Joel"
          />
          <datalist id="item-owners">
            {(owners ?? []).map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
        </Field>
        <Field label="Condition">
          <Select
            value={values.condition ?? ''}
            onChange={(event) => set('condition', (event.target.value || null) as Condition | null)}
          >
            <option value="">Not stated</option>
            {CONDITIONS.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Brand">
          <Input value={values.brand ?? ''} onChange={text('brand')} />
        </Field>
        <Field label="Model">
          <Input value={values.model ?? ''} onChange={text('model')} />
        </Field>
        <Field label="Purchase price">
          <Input
            inputMode="decimal"
            value={values.purchase_price ?? ''}
            onChange={text('purchase_price')}
            placeholder="199.00"
          />
        </Field>
        <Field label="Current value">
          <Input
            inputMode="decimal"
            value={values.current_value ?? ''}
            onChange={text('current_value')}
          />
        </Field>
      </div>

      <Field label="Tags">
        <TagPicker selected={values.tag_ids} onChange={(ids) => set('tag_ids', ids)} />
      </Field>

      <button
        type="button"
        onClick={() => setShowMore((open) => !open)}
        className="text-sm text-accent-600 hover:underline dark:text-accent-400"
      >
        {showMore ? 'Fewer fields' : 'More fields'}
      </button>

      {showMore ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Subcategory">
            <Input value={values.subcategory ?? ''} onChange={text('subcategory')} />
          </Field>
          <Field label="Serial number">
            <Input value={values.serial_number ?? ''} onChange={text('serial_number')} />
          </Field>
          <Field label="Barcode">
            <Input value={values.barcode ?? ''} onChange={text('barcode')} />
          </Field>
          <Field label="Bought at">
            <Input value={values.purchase_location ?? ''} onChange={text('purchase_location')} />
          </Field>
          <Field label="Purchase date">
            <Input type="date" value={values.purchase_date ?? ''} onChange={text('purchase_date')} />
          </Field>
          <Field label="Warranty ends">
            <Input
              type="date"
              value={values.warranty_expires ?? ''}
              onChange={text('warranty_expires')}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Description">
              <Textarea rows={2} value={values.description ?? ''} onChange={text('description')} />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Notes">
              <Textarea rows={3} value={values.notes ?? ''} onChange={text('notes')} />
            </Field>
          </div>
        </div>
      ) : null}

      <div className="flex justify-end gap-2 pt-2">
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" loading={saving}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

/**
 * NFC tags.
 *
 * `react-native-nfc-manager` needs a development build. Expo Go does not
 * carry it, so every call here loads the module at run time and reports a
 * clear message when it is absent.
 */

import { api } from '@/api/client'
import type { NfcLookup } from '@/api/types'

interface NfcModule {
  default: {
    start: () => Promise<void>
    isSupported: () => Promise<boolean>
    requestTechnology: (tech: unknown) => Promise<void>
    getTag: () => Promise<{ id?: string } | null>
    cancelTechnologyRequest: () => Promise<void>
  }
  NfcTech: { Ndef: unknown }
}

export class NfcUnavailableError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NfcUnavailableError'
  }
}

async function load(): Promise<NfcModule> {
  try {
    // The import is dynamic on purpose. A static import would break the
    // bundle in Expo Go, where the native module does not exist.
    return (await import('react-native-nfc-manager')) as unknown as NfcModule
  } catch {
    throw new NfcUnavailableError(
      'This build has no NFC support. Use a development build, not Expo Go.',
    )
  }
}

/** Read one tag and return its UID. */
export async function readTagUid(): Promise<string> {
  const module = await load()
  const manager = module.default

  if (!(await manager.isSupported())) {
    throw new NfcUnavailableError('This phone has no NFC reader.')
  }
  await manager.start()
  try {
    await manager.requestTechnology(module.NfcTech.Ndef)
    const tag = await manager.getTag()
    const uid = tag?.id
    if (!uid) throw new NfcUnavailableError('The tag gave no identifier.')
    return uid.replace(/[:\s-]/g, '').toUpperCase()
  } finally {
    await manager.cancelTechnologyRequest().catch(() => undefined)
  }
}

/** Read a tag, then ask the server what it points at. */
export async function scanAndLookup(): Promise<NfcLookup> {
  const uid = await readTagUid()
  return api.get<NfcLookup>(`/api/nfc/${encodeURIComponent(uid)}`)
}

/** Read a tag and bind it to one item or to one location. */
export async function scanAndRegister(target: {
  itemId?: string
  locationId?: string
  label?: string
}): Promise<string> {
  const uid = await readTagUid()
  await api.post('/api/nfc/register', {
    nfc_uid: uid,
    item_id: target.itemId,
    location_id: target.locationId,
    label: target.label,
  })
  return uid
}

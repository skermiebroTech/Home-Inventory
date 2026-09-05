/**
 * Local reminders.
 *
 * The server has no push service, and a self-hosted box should not need one.
 * The phone reads its own copy of the data after every sync and schedules the
 * reminders itself, so they work with no cloud account.
 */

import * as Notifications from 'expo-notifications'

import { listItems, listMaintenance } from '@/db'

const DAY = 24 * 60 * 60 * 1000
/** Warn this many days before the date. */
const WARNING_DAYS = 7

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    // `shouldShowAlert` is the older name. Both are sent, so the handler
    // works on either SDK version.
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
})

export async function askForPermission(): Promise<boolean> {
  const current = await Notifications.getPermissionsAsync()
  if (current.granted) return true
  const asked = await Notifications.requestPermissionsAsync()
  return asked.granted
}

/** Read the local tables and set one reminder for each due date. */
export async function scheduleReminders(): Promise<number> {
  if (!(await askForPermission())) return 0
  await Notifications.cancelAllScheduledNotificationsAsync()

  const now = Date.now()
  let count = 0

  const schedule = async (title: string, body: string, when: Date): Promise<void> => {
    if (when.getTime() <= now) return
    await Notifications.scheduleNotificationAsync({
      content: { title, body },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: when,
      },
    })
    count += 1
  }

  for (const log of await listMaintenance()) {
    if (!log.next_due_date) continue
    const due = new Date(`${log.next_due_date}T09:00:00`)
    await schedule(
      'Service is due',
      log.description,
      new Date(due.getTime() - WARNING_DAYS * DAY),
    )
  }

  for (const item of await listItems({ limit: 500 })) {
    if (item.warranty_expires) {
      const ends = new Date(`${item.warranty_expires}T09:00:00`)
      await schedule(
        'A warranty ends soon',
        `${item.name} loses its warranty on ${item.warranty_expires}.`,
        new Date(ends.getTime() - 14 * DAY),
      )
    }
    if (item.is_lent && item.lent_date) {
      const lent = new Date(`${item.lent_date}T09:00:00`)
      await schedule(
        'Still on loan',
        `${item.lent_to} has your ${item.name}.`,
        new Date(lent.getTime() + 30 * DAY),
      )
    }
  }
  return count
}

export async function clearReminders(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync()
}

/** The dashboard, the health check, the AI status, and the backups. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { ai, system } from '@/api/endpoints'
import type { AiJob, BackupSchedule } from '@/api/types'
import { keys } from './keys'

export function useDashboard() {
  return useQuery({ queryKey: keys.dashboard(), queryFn: () => system.dashboard() })
}

export function useHealth(poll = false) {
  return useQuery({
    queryKey: keys.health(),
    queryFn: () => system.health(),
    refetchInterval: poll ? 30000 : false,
    retry: 1,
  })
}

export function useAiStatus() {
  return useQuery({ queryKey: keys.aiStatus(), queryFn: () => ai.status(), retry: 1 })
}

export function useBackupStatus() {
  return useQuery({ queryKey: keys.backup(), queryFn: () => system.backupStatus() })
}

export function useSetSchedule() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: BackupSchedule) => system.setSchedule(body),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.backup() }),
  })
}

export function useRunBackup() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => system.runBackup(),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.backup() }),
  })
}

/**
 * Follow one AI job to its end.
 *
 * The server answers 200 with the result when the model was quick, and 202
 * with a running job when it was not. Both replies hold the same shape, so
 * this hook polls only while the job is unfinished.
 */
export function useAiJob(initial: AiJob | null) {
  const [job, setJob] = useState<AiJob | null>(initial)

  useEffect(() => setJob(initial), [initial])

  const finished = job === null || job.status === 'succeeded' || job.status === 'failed'

  const query = useQuery({
    queryKey: keys.aiJob(job?.id ?? ''),
    queryFn: () => ai.job(job?.id as string),
    enabled: Boolean(job) && !finished,
    refetchInterval: finished ? false : 2000,
  })

  useEffect(() => {
    if (query.data) setJob(query.data)
  }, [query.data])

  return { job, finished: Boolean(job) && finished }
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { settingsQueryOptions, updateSettings } from '@/features/settings/api'
import { describeProblem } from '@/features/shared/helpers'
import { Field, PageHeading, QueryState } from '@/features/shared/ui'
import type { SettingsOut } from '@/lib/types'

type TopicSelectionMode = 'auto' | 'manual'

function TopicSelectionModeForm({ data }: { data: SettingsOut }) {
  const initialMode: TopicSelectionMode = data.effective.topicSelectionMode === 'manual' ? 'manual' : 'auto'
  const [mode, setMode] = useState<TopicSelectionMode>(initialMode)
  const client = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => updateSettings({ ...data.values, topicSelectionMode: mode }, data.version),
    onSuccess: async () => {
      toast.success('Topic selection mode saved')
      await client.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: (error) => toast.error(describeProblem(error, 'Save failed')),
  })

  return (
    <form
      className="max-w-xl space-y-4 rounded border p-4"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <Field label="Topic selection mode">
        <select
          className="h-9 w-full rounded border bg-background px-2"
          value={mode}
          onChange={(event) => setMode(event.target.value as TopicSelectionMode)}
        >
          <option value="auto">Automatic</option>
          <option value="manual">Manual</option>
        </select>
      </Field>
      <p className="text-sm text-muted-foreground">
        Automatic mode selects researched topics automatically. Manual mode pauses discovered topics for a
        person to choose. A topic submitted on the Topics page always starts a new draft.
      </p>
      <Button disabled={mutation.isPending || mode === initialMode}>
        {mutation.isPending ? 'Saving…' : 'Save topic selection mode'}
      </Button>
    </form>
  )
}

export function SettingsPage() {
  const settings = useQuery(settingsQueryOptions())

  return (
    <section className="space-y-5">
      <PageHeading title="Settings" description="Choose how topics are selected for new blog drafts." />
      <QueryState query={settings} label="settings">
        {settings.data && <TopicSelectionModeForm key={settings.data.version} data={settings.data} />}
      </QueryState>
    </section>
  )
}

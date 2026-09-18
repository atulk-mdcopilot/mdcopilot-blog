import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Field } from './ui'
import { humanLabel } from './helpers'
const options: Record<string, string[]> = {
  headerProfile: ['default', 'browser_like'],
  fetchPolicy: ['fetch', 'metadata_only', 'never'],
  sourceType: [
    'government',
    'journal',
    'preprint',
    'trade_press',
    'company_announcement',
    'blog',
    'social',
    'other',
  ],
}
export function ConfigFields({
  values,
  onChange,
  disabled = false,
}: {
  values: Record<string, unknown>
  onChange: (values: Record<string, unknown>) => void
  disabled?: boolean
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {Object.entries(values).map(([key, value]) => {
        const set = (next: unknown) => onChange({ ...values, [key]: next })
        if (Array.isArray(value))
          return (
            <Field
              key={key}
              label={`${humanLabel(key)} (${key === 'weekdays' ? '0 = Monday, 6 = Sunday; comma separated' : 'one per line'})`}
            >
              <Textarea
                disabled={disabled}
                value={key === 'weekdays' ? value.join(', ') : value.join('\n')}
                onChange={(e) =>
                  set(
                    key === 'weekdays'
                      ? e.target.value
                          .split(',')
                          .filter((s) => s.trim())
                          .map(Number)
                      : e.target.value.split('\n'),
                  )
                }
              />
            </Field>
          )
        if (value !== null && typeof value === 'object')
          return (
            <fieldset key={key} className="col-span-full rounded border p-4">
              <legend className="px-2 text-sm font-semibold">{humanLabel(key)}</legend>
              <ConfigFields values={value as Record<string, unknown>} onChange={set} disabled={disabled} />
            </fieldset>
          )
        if (typeof value === 'boolean')
          return (
            <Field key={key} label={humanLabel(key)}>
              <Switch
                checked={value}
                onCheckedChange={set}
                disabled={disabled}
                aria-label={humanLabel(key)}
              />
            </Field>
          )
        if (options[key])
          return (
            <Field key={key} label={humanLabel(key)}>
              <select
                className="h-9 rounded border bg-background px-2"
                disabled={disabled}
                value={String(value ?? '')}
                onChange={(e) => set(e.target.value)}
              >
                {options[key].map((o) => (
                  <option key={o} value={o}>
                    {humanLabel(o)}
                  </option>
                ))}
              </select>
            </Field>
          )
        if (value === null) return null
        return (
          <Field key={key} label={humanLabel(key)}>
            {typeof value === 'number' ? (
              <Input
                type="number"
                step="any"
                disabled={disabled}
                value={value}
                onChange={(e) => set(Number(e.target.value))}
              />
            ) : (
              <Textarea
                disabled={disabled}
                rows={String(value).length > 100 ? 4 : 2}
                value={String(value)}
                onChange={(e) => set(e.target.value)}
              />
            )}
          </Field>
        )
      })}
    </div>
  )
}

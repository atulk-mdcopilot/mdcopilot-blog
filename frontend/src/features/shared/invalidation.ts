import type { QueryClient } from '@tanstack/react-query'
export async function afterChange(client: QueryClient) {
  await Promise.all(
    ['articles', 'runs', 'research', 'topics', 'dashboard'].map((key) =>
      client.invalidateQueries({ queryKey: [key] }),
    ),
  )
}

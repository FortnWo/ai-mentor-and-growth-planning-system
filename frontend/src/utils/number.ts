export function parseOptionalInteger(value: string | number | null | undefined): number | undefined {
  if (value === null || value === undefined || value === '') {
    return undefined
  }

  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isInteger(parsed) ? parsed : undefined
}
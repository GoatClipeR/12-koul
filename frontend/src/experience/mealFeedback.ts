import type { ChatResult } from '../api/chatApi'

function selections(result: ChatResult | null) {
  return Object.values(result?.meal_state.categories ?? {}).flatMap(draft => Object.values(draft.slots).flat())
}
/** Describe state differences, never unvalidated model claims. */
export function mealFeedback(previous: ChatResult | null, next: ChatResult | null): string | null {
  if (!next) return previous ? 'La table est à nouveau à vous.' : null
  if (!next.accepted) return null
  const before = selections(previous), after = selections(next)
  const added = after.filter(id => !before.includes(id))
  const removed = before.filter(id => !after.includes(id))
  const labels = next.display.facts.selected_items
  if (added.length) return `En place · ${added.map(id => labels.find(item => item.id === id)?.name.fr).filter(Boolean).join(' · ') || 'Votre composition'}`
  if (previous?.meal_state.categories.salad?.size !== next.meal_state.categories.salad?.size && next.meal_state.categories.salad?.size)
    return next.meal_state.categories.salad.size === 'large' ? 'Votre bol passe en grand.' : 'Votre bol passe en petit.'
  const newLines = next.cart?.lines.filter(line => !previous?.cart?.lines.some(old => old.id === line.id)) ?? []
  if (newLines.length) return newLines.some(line => line.items.some(item => item.id.startsWith('drink.'))) ? 'Votre boisson est servie.' : 'Votre composition rejoint le panier.'
  if (removed.length) return 'Votre composition s’allège.'
  if (next.display.facts.recommended_items.length) return 'Une suggestion à découvrir.'
  return null
}

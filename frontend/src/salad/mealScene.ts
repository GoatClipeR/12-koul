/** Read-only projection. Only pass state accepted by the deterministic meal engine. */
export interface MealState {
  active_category: string | null
  categories: Record<string, { type: string; size: string | null; slots: Record<string, string[]> }>
}
export const ingredientAssets = {
  'salad.base.lettuce': 'lettuce',
  'salad.ingredient.tomato': 'tomato',
  'salad.ingredient.cucumber': 'cucumber',
  'salad.ingredient.grilled_chicken': 'chicken',
  'salad.ingredient.corn': 'corn',
  'salad.topping.croutons': 'croutons',
  'salad.sauce.caesar': 'caesar',
} as const
export type IngredientKind = typeof ingredientAssets[keyof typeof ingredientAssets]
export function projectMeal(state: MealState) {
  const salad = state.categories.salad
  const ids = salad ? Object.values(salad.slots).flat() : []
  return {
    visible: !!salad, scale: salad?.size === 'small' ? .82 : 1,
    ingredients: [...new Set(ids.filter((id): id is keyof typeof ingredientAssets => id in ingredientAssets).map(id => ingredientAssets[id]))],
    unmapped: ids.filter(id => !(id in ingredientAssets)),
  }
}
// Valid draft, deliberately incomplete: seven visual assets, not a confirmed meal.
export const demoMeal: MealState = {
  active_category: 'salad', categories: { salad: { type: 'salad', size: 'large', slots: {
    base: ['salad.base.lettuce'],
    ingredient: ['salad.ingredient.tomato','salad.ingredient.cucumber','salad.ingredient.grilled_chicken','salad.ingredient.corn'],
    topping: ['salad.topping.croutons'], sauce: ['salad.sauce.caesar'],
  } } },
}

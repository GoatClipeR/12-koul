# 12-KOUL menu specification (Stage 0)

Source of truth: `backend/app/data/menu.json` (75 items, fictional, MAD). Validate with `python tools/validate_menu.py`.

## Composition rules

Rules are data (`min`/`max` per slot). Where `min == max` the count is **exact**.

### Salad — EXACT, incomplete salads cannot be ordered

| Size | Price | Base | Ingredients | Toppings | Sauces |
|---|---|---|---|---|---|
| small | 35 MAD | exactly 1 | exactly 2 | exactly 1 | exactly 1 |
| large | 55 MAD | exactly 2 | exactly 5 | exactly 3 | exactly 2 |

Ring display — small: 1/1 base · 2/2 ingredients · 1/1 topping · 1/1 sauce. Large: 2/2 · 5/5 · 3/3 · 2/2.

### Other categories (approved in Stage 1 takeover)

- **sandwich**: bread exactly 1, protein exactly 1, cheese 0–1, vegetable 0–3, sauce exactly 1, extra 0–2
- **plat**: protein exactly 1, side exactly 1, sauce exactly 1
- **drink**: drink exactly 1

General: no duplicate item within a slot; a drink is its own cart line (exactly 1 drink).

## Pricing (MAD)

- Salad: by size (35 / 55); every selection included.
- Sandwich: price of the protein (tuna 35, grilled chicken 38, crispy chicken 40, beef steak 50) + extras (egg 4, extra cheese 5, avocado 8, bacon 8).
- Plat: price of the protein (escalope 50, crispy chicken 52, grilled chicken 55, brochettes 58, steak 65); side and sauce included.
- Drinks: juices 14–18, sodas 10, sparkling water 8 (small) / 12 (large).
- All arithmetic is done by the backend `price_engine`; the LLM never computes totals.

## Allergens (fictional, scope = dairy, nuts, gluten, eggs, sesame)

`[]` = none of the 5 tracked allergens; `null` would mean unknown (currently no item is null). Allergens outside the scope (fish, soy, mustard, peanuts…) and cross-contamination are **not tracked** — the assistant must say so. Nutrition is unavailable.

| Item id | Allergens |
|---|---|
| `salad.ingredient.egg` | eggs |
| `salad.ingredient.mozzarella` | dairy |
| `salad.topping.croutons` | gluten |
| `salad.topping.walnuts` | nuts |
| `salad.topping.sesame_seeds` | sesame |
| `salad.topping.crispy_onions` | gluten |
| `salad.sauce.caesar` | dairy, eggs |
| `salad.sauce.algerian` | eggs |
| `salad.sauce.ranch` | dairy, eggs |
| `sandwich.bread.baguette` | gluten |
| `sandwich.bread.brioche` | gluten, dairy, eggs |
| `sandwich.bread.whole_wheat` | gluten, sesame |
| `sandwich.bread.ciabatta` | gluten |
| `sandwich.protein.crispy_chicken` | gluten, eggs |
| `sandwich.cheese.cheddar` | dairy |
| `sandwich.cheese.emmental` | dairy |
| `sandwich.cheese.mozzarella` | dairy |
| `sandwich.sauce.mayonnaise` | eggs |
| `sandwich.sauce.algerian` | eggs |
| `sandwich.sauce.andalouse` | eggs |
| `sandwich.sauce.caesar` | dairy, eggs |
| `sandwich.extra.egg` | eggs |
| `sandwich.extra.extra_cheese` | dairy |
| `plat.protein.crispy_chicken` | gluten, eggs |
| `plat.protein.escalope` | gluten, eggs |
| `plat.sauce.mushroom` | dairy |
| `plat.sauce.pepper` | dairy |
| `plat.sauce.algerian` | eggs |

## Action rejection reason codes (engine → assistant)

`UNKNOWN_ITEM`, `WRONG_CATEGORY`, `SLOT_FULL`, `DUPLICATE_ITEM`, `NOT_IN_MEAL`, `SIZE_REQUIRED`, `SIZE_CONFLICT` (SET_SIZE would leave more items than the new size allows — user must remove items first), `INCOMPLETE_MEAL` (ADD_TO_CART / CONFIRM_ORDER blocked, lists missing slots), `CART_EMPTY`, `NO_ACTIVE_MEAL`.


"""Deterministic display facts. Model prose is never the authoritative UI copy."""

def presentation(state, quote, response, menu, *, accepted, locale='fr'):
    en = locale == 'en'
    if not accepted:
        return {'message': 'No changes applied.' if en else 'Aucune modification appliquée.', 'facts': None}
    actions = response['actions']
    recommendations = [menu.item(a['item_id']) for a in actions if a['type'] == 'RECOMMEND_ITEM']
    selected = [menu.item(i) for draft in state['categories'].values()
                for ids in draft['slots'].values() for i in ids]
    meta = menu.snapshot()['meta']
    if recommendations:
        message = ('Menu suggestion: ' if en else 'Suggestion du menu : ') + ', '.join(i['name'][locale] for i in recommendations)
    elif any(a['type'] == 'CONFIRM_ORDER' for a in actions):
        message = 'Composition validated; no order submitted.' if en else 'Composition validée ; aucune commande envoyée.'
    elif any(a['type'] != 'RECOMMEND_ITEM' for a in actions):
        message = 'Composition updated.' if en else 'Composition mise à jour.'
    else:
        message = 'Choose a category or consult the menu facts.' if en else 'Choisissez une catégorie ou consultez les informations du menu.'
    if quote['total'] is not None and quote['lines']:
        message += (' Estimate: ' if en else ' Estimation : ') + str(quote['total']) + ' ' + quote['currency'] + '.'
    return {'message': message, 'facts': {
        'quote': quote, 'selected_items': selected, 'recommended_items': recommendations,
        'allergen_scope': meta['allergen_scope'], 'allergen_note': meta['allergen_note'][locale],
        'nutrition_available': meta['nutrition_available'], 'availability_tracked': meta['availability_tracked']}}

"""HTTP contracts; the existing action schema remains the source of action fields."""
from typing import Annotated, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model, field_validator, model_validator
from .actions import FIELDS


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


ConversationId = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')]
Category = Literal['salad', 'sandwich', 'plat', 'drink']

# Reuse field names/types from the domain contract instead of maintaining a second list.
Action = Annotated[Union[tuple(
    create_model(kind + 'Action', __base__=StrictModel,
                 type=(Literal[kind], ...), **{f: (str, ...) for f in fields})
    for kind, fields in FIELDS.items()
)], Field(discriminator='type')]


class ChatRequest(StrictModel):
    conversation_id: ConversationId
    message: str = Field(min_length=1, max_length=1000)
    locale: Literal['fr', 'en'] = 'fr'
    cart_mode: bool = False
    cart_command: Optional[Literal['add', 'remove', 'confirm']] = None
    cart_category: Optional[Category] = None
    cart_line_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    confirm_composition: bool = False
    remove_item_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    expected_revision: Optional[int] = Field(default=None, ge=0)

    @field_validator('message')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Message vide')
        return value.strip()

    @model_validator(mode='after')
    def confirmation_revision(self):
        if self.cart_command is not None:
            if not self.cart_mode or self.expected_revision is None or self.confirm_composition or self.remove_item_id:
                raise ValueError('Décision panier explicite requise')
            if (self.cart_command == 'add') != (self.cart_category is not None) or (self.cart_command == 'remove') != (self.cart_line_id is not None):
                raise ValueError('Cible panier invalide')
        elif self.cart_category is not None or self.cart_line_id is not None:
            raise ValueError('Commande panier requise')
        if (self.confirm_composition or self.remove_item_id is not None) and self.expected_revision is None:
            raise ValueError('La confirmation exige la révision affichée')
        if self.confirm_composition and self.remove_item_id is not None:
            raise ValueError('Une seule décision explicite par tour')
        return self


class Draft(StrictModel):
    type: Category
    size: Optional[Literal['small', 'large']]
    slots: Dict[str, List[str]]


class MealState(StrictModel):
    active_category: Optional[Category]
    categories: Dict[str, Draft]


class MissingSlot(StrictModel):
    category: str
    slot: str
    count: int


class MissingSize(StrictModel):
    category: Literal['salad']
    size_required: Literal[True]


class QuoteLine(StrictModel):
    category: Category
    meal: Draft
    amount: Optional[int]
    complete: bool


class Quote(StrictModel):
    currency: Literal['MAD']
    lines: List[QuoteLine]
    total: Optional[int]
    orderable: bool
    missing: List[Union[MissingSlot, MissingSize]]


class MenuItem(StrictModel):
    id: str
    category: Category
    slot: str
    name: Dict[str, str]
    price: int
    tags: List[str]
    allergens: List[str]
    spice: int
    vegetarian: bool
    vegan: bool
    asset: Optional[str]
    group: Optional[str] = None


class Facts(StrictModel):
    quote: Quote
    selected_items: List[MenuItem]
    recommended_items: List[MenuItem]
    allergen_scope: List[str]
    allergen_note: str
    nutrition_available: bool
    availability_tracked: bool


class Display(StrictModel):
    message: str
    facts: Facts


class Limits(StrictModel):
    fictional_menu: bool
    nutrition_available: bool
    availability_tracked: bool
    allergen_scope: List[str]
    allergen_note: str
    external_order_submitted: Literal[False] = False
    payments_supported: Literal[False] = False


class ApiError(StrictModel):
    code: str
    message: str


class ErrorEnvelope(StrictModel):
    error: ApiError


class CartLine(StrictModel):
    id: str
    meal_state: MealState
    quote: Quote
    items: List[MenuItem]


class Cart(StrictModel):
    lines: List[CartLine]
    total: int
    currency: Literal['MAD']
    confirmed: bool
    external_order_submitted: Literal[False] = False


class ChatResponse(StrictModel):
    conversation_id: ConversationId
    revision: int = Field(ge=0)
    prompt_version: Literal['v3'] = 'v3'
    provider_mode: Literal['mock', 'real']
    accepted: bool
    assistant_message: Optional[str] = Field(default=None, max_length=4000)
    cart: Optional[Cart] = None
    model_text_trusted: Literal[False] = False
    actions: List[Action] = Field(max_length=64)
    meal_state: MealState
    quote: Quote
    display: Display
    limits: Limits
    error: Optional[ApiError] = None


class HealthResponse(StrictModel):
    status: Literal['ok'] = 'ok'
    prompt_version: Literal['v3'] = 'v3'


class DeleteResponse(StrictModel):
    conversation_id: ConversationId
    deleted: bool

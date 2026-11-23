"""
Nutrients the weekly analysis may mark lacking or more than enough (source of truth, #206).

Most important first: the weekly analyst's prompt lists them in this order and says so, and code
keeps a reply's lists in it. The list is wide on purpose, so a stronger model can use all of it;
the prompt asks to mark a nutrient only when the week's meals make the model confident. Names
only, never foods: the reply's schema allows nothing else.
"""

NUTRIENTS = (
    # Energy and macros
    "energy",
    "protein",
    "fiber",
    "sugar",
    "salt",
    "saturated fat",
    "carbohydrates",
    "fat",
    "omega-3 fats",
    # Vitamins and minerals most often short or in excess
    "vitamin D",
    "vitamin B12",
    "iron",
    "calcium",
    "folate",
    "vitamin C",
    "potassium",
    "magnesium",
    "iodine",
    "zinc",
    "vitamin A",
    "vitamin E",
    "vitamin K",
    "vitamin B6",
    "riboflavin (vitamin B2)",
    "thiamin (vitamin B1)",
    "niacin (vitamin B3)",
    "selenium",
    "phosphorus",
    "choline",
    "trans fat",
    "cholesterol",
)

_ORDER = {name: i for i, name in enumerate(NUTRIENTS)}


def clean_nutrients(lacking, more_than_enough) -> tuple[list[str], list[str]]:
    """The reply's two lists with only listed nutrients, each once, most important first.

    A nutrient on both lists says nothing, so it goes from both.
    """
    def known(value) -> set[str]:
        return {n for n in value if isinstance(n, str) and n in _ORDER} if isinstance(value, list) else set()

    low, high = known(lacking), known(more_than_enough)
    both = low & high
    return (
        sorted(low - both, key=_ORDER.__getitem__),
        sorted(high - both, key=_ORDER.__getitem__),
    )

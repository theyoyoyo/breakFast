/**
 * Mock meals for the component tests, in the app's menu format (CLAUDE.md "Meal Format"):
 * a dish has ingredients and no amount of its own, a simple item has an amount, a unit and no ingredients.
 */

// A full menu: one dish with its ingredients and a method, two simple items
export const OMELETTE_MENU = {
  menu_name: 'Sunday Omelette',
  menu: [
    {
      name: 'Veggie omelette',
      method: 'Whisk the eggs, fry the pepper, pour the eggs over and fold',
      ingredients: [
        { name: 'Egg', amount: 2, unit: 'pcs', prep: 'whisked' },
        { name: 'Bell pepper', amount: 0.5, unit: 'pcs', prep: 'diced' },
        { name: 'Butter', amount: 1, unit: 'tsp' },
      ],
    },
    { name: 'Toast', amount: 2, unit: 'slice', method: 'Toast the bread', ingredients: [] },
    { name: 'Olives', amount: 6, unit: 'pcs', ingredients: [] },
  ],
  prep_time_min: 15,
}

// A small menu of simple items only
export const PLATE_MENU = {
  menu_name: 'Quick Plate',
  menu: [
    { name: 'Cheese', amount: 50, unit: 'g', ingredients: [] },
    { name: 'Tomato', amount: 1, unit: 'pcs', ingredients: [] },
  ],
  prep_time_min: 5,
}

// A suggestion reply as the server streams and saves it: the text, then the meal's ```json block
export function suggestionReply(text, meal) {
  return `${text}\n\n\`\`\`json\n${JSON.stringify(meal)}\n\`\`\``
}

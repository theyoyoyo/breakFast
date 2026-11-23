// Breakfast emojis used as meal icons (chat cards, favorites), mirrored in backend/models/meal.py (edit both).
// The server gives a suggestion one at random (#244); Favorites' picker offers only these.
export const BREAKFAST_EMOJIS = [
  '🍳', '🥐', '🧀', '🥚', '🫕', '🥞', '🧇', '🥣', '🍞', '🥯', '🫖', '☕',
  '🥗', '🥑', '🍯', '🫒', '🧈', '🥛', '🍵', '🫐', '🍓', '🍌', '🍊', '🍇',
  '🥜', '🌰', '🥒', '🍅', '🫑', '🌿', '🌶️', '🧄', '🫘', '🥕', '🌽', '🥦',
  '🍋', '🥝', '🍑', '🫚', '🥥', '🧆', '🥙', '🫓', '🥖', '🥨', '🥮', '🍠',
]

// Same emoji for the same id or text every time: the icon of a meal saved without one
// (an older favorite by its id, an older chat card by its name)
export function emojiFor(id) {
  let n = Math.abs(Number(id))
  if (!Number.isFinite(n)) n = [...String(id ?? '')].reduce((h, c) => (h * 31 + c.codePointAt(0)) % 1000003, 0)
  return BREAKFAST_EMOJIS[Math.floor(n) % BREAKFAST_EMOJIS.length]
}

// A meal's icon: its saved one, else the stable one for the fallback key
export function mealEmoji(meal, fallbackKey) {
  return meal?.emoji || emojiFor(fallbackKey)
}

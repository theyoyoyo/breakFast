// Breakfast emojis used as meal icons (chat cards, favorites)
export const BREAKFAST_EMOJIS = [
  '🍳', '🥐', '🧀', '🥚', '🫕', '🥞', '🧇', '🥣', '🍞', '🥯', '🫖', '☕',
  '🥗', '🥑', '🍯', '🫒', '🧈', '🥛', '🍵', '🫐', '🍓', '🍌', '🍊', '🍇',
  '🥜', '🌰', '🥒', '🍅', '🫑', '🌿', '🌶️', '🧄', '🫘', '🥕', '🌽', '🥦',
  '🍋', '🥝', '🍑', '🫚', '🥥', '🧆', '🥙', '🫓', '🥖', '🥨', '🥮', '🍠',
]

export function pickEmoji() {
  return BREAKFAST_EMOJIS[Math.floor(Math.random() * BREAKFAST_EMOJIS.length)]
}

// Same emoji for the same id every time (e.g. a favorite keeps its icon)
export function emojiFor(id) {
  const n = Math.abs(Number(id) || 0)
  return BREAKFAST_EMOJIS[n % BREAKFAST_EMOJIS.length]
}

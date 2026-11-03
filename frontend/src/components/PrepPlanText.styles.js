// A plan's steps and Ready line sit beside a thin bar in their dish's color (--dish-1 … --dish-4,
// index.css); the Ready line's bar is clear, so the times line up.
export const bodyLine = (color) => ({
  borderLeftWidth: 3,
  borderLeftStyle: 'solid',
  borderLeftColor: color || 'transparent',
  paddingLeft: 6,
})

export const dishName = (color) => ({
  color,
})

// A blank line, the same height as in MarkdownText
export const gap = {
  height: '0.6em',
}

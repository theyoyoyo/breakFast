// --- Inline block in chat ---

export const blockRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  alignSelf: 'flex-end',
  maxWidth: '80%',
  minWidth: 0,
  overflow: 'hidden',
}

export const checkbox = (checked) => ({
  background: 'none',
  border: 'none',
  fontSize: 22,
  cursor: 'pointer',
  color: checked ? 'var(--accent)' : 'var(--text-muted)',
  padding: 0,
  lineHeight: 1,
  flexShrink: 0,
})

export const block = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '10px 14px',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
}

export const blockIcon = {
  fontSize: 18,
  flexShrink: 0,
}

export const blockText = {
  fontSize: 13,
  color: 'var(--text)',
  flex: 1,
  minWidth: 0,
  overflowWrap: 'break-word',
  wordBreak: 'break-word',
}

export const analyzeBtn = (analyzing) => ({
  background: 'none',
  border: 'none',
  fontSize: 20,
  cursor: analyzing ? 'default' : 'pointer',
  opacity: analyzing ? 0.5 : 1,
  padding: '2px 4px',
  flexShrink: 0,
  transition: 'opacity 0.15s',
})

export const prepBadge = {
  fontSize: 11,
  color: 'var(--text-muted)',
  background: 'var(--surface)',
  borderRadius: 8,
  padding: '2px 8px',
  flexShrink: 0,
  whiteSpace: 'nowrap',
}

// --- Overlay panel ---

export const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  zIndex: 30,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  padding: 16,
}

export const panel = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 16,
  padding: '20px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
  overflowY: 'auto',
  maxHeight: '80vh',
  display: 'flex',
  flexDirection: 'column',
}

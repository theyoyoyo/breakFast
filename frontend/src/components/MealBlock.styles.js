// --- Inline block in chat ---

export const blockWrapper = {
  display: 'flex',
  flexDirection: 'column',
  alignSelf: 'flex-end',
  maxWidth: '80%',
  minWidth: 0,
}

export const titleBar = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 10px',
  background: 'var(--surface2)',
  borderRadius: '10px 10px 0 0',
  border: '1px solid var(--border)',
  borderBottom: 'none',
  cursor: 'pointer',
  overflow: 'hidden',
}

export const titleName = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--accent)',
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

export const titlePrep = {
  fontSize: 10,
  color: 'var(--text-muted)',
  flexShrink: 0,
  whiteSpace: 'nowrap',
}

export const titleId = {
  fontSize: 9,
  color: 'var(--text-muted)',
  opacity: 0.5,
  flexShrink: 0,
}

export const blockRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
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
  borderRadius: '0 0 12px 12px',
  borderTop: 'none',
  padding: '10px 14px',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
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
  fontSize: 18,
  cursor: analyzing ? 'default' : 'pointer',
  opacity: analyzing ? 0.5 : 1,
  padding: '2px 2px',
  flexShrink: 0,
  transition: 'opacity 0.15s',
})

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
  maxHeight: '80dvh',
  display: 'flex',
  flexDirection: 'column',
}

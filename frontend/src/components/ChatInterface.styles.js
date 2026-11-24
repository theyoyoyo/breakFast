import { deleteBtn } from '../styles/common'

export const container = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  background: 'var(--surface)',
  borderRadius: 'var(--radius)',
  overflow: 'hidden',
}

export const header = {
  padding: '16px 20px',
  borderBottom: '1px solid var(--border)',
  fontWeight: 600,
  fontSize: 16,
  color: 'var(--accent)',
  letterSpacing: '0.02em',
}

export const messages = {
  flex: 1,
  minHeight: 0,           // prevents flex item from overflowing and hiding the action row
  overflowY: 'auto',
  overflowX: 'hidden',
  padding: '16px 16px 24px',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

export const messageWrapper = (role) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: role === 'user' ? 'flex-end' : 'flex-start',
})

export const bubble = (role) => ({
  maxWidth: '80%',
  alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
  background: role === 'user' ? 'var(--surface2)' : 'var(--bubble)',
  color: 'var(--text)',
  border: 'none',
  borderRadius: role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
  padding: '10px 14px',
  fontSize: 14,
  lineHeight: 1.6,
  whiteSpace: 'pre-wrap',
  overflowWrap: 'break-word',
  wordBreak: 'break-word',
})

// "Thinking…" or a step's progress: on the user's side for a Suggest press, which shows no message of its own
export const thinking = (side) => ({
  alignSelf: side === 'user' ? 'flex-end' : 'flex-start',
  color: 'var(--text-muted)',
  fontSize: 13,
  padding: '6px 4px',
})

// The short notice that the user's last request still runs: on the assistant's side, apart from the chat
export const busyNote = {
  alignSelf: 'flex-start',
  color: 'var(--text-muted)',
  fontSize: 13,
  fontStyle: 'italic',
  padding: '6px 4px',
  maxWidth: '85%',
}

// The small note under a reply stopped part way
export const stoppedNote = {
  alignSelf: 'flex-start',
  color: 'var(--text-muted)',
  fontSize: 11,
  fontStyle: 'italic',
  padding: '2px 6px',
}

export const connStatus = {
  fontSize: 12,
  fontWeight: 400,
  color: 'var(--text-muted)',
}

// Session buttons in the chat header (Back, Next, New) — accent colored; Delete is red
export const newSessionBtn = {
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '4px 10px',
  fontSize: 12,
  color: 'var(--accent)',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}

export const deleteSessionBtn = {
  ...deleteBtn,
  borderRadius: 8,
  padding: '4px 10px',
  fontSize: 12,
  whiteSpace: 'nowrap',
}

// Off while another session button runs
export const sessionBtnState = (busy) => (busy ? { opacity: 0.5, cursor: 'default' } : {})

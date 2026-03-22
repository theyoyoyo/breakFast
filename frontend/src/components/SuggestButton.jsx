import u2Logo from '../assets/u2.png'
import * as s from './SuggestButton.styles'

export default function SuggestButton({ onClick, disabled }) {
  return (
    <button
      style={s.button(disabled)}
      onClick={onClick}
      disabled={disabled}
      title="Kahvaltı Öner"
    >
      <img src={u2Logo} alt="Kahvaltı Öner" style={s.logo} />
    </button>
  )
}

import { parsePrepPlan } from '../utils/prepPlan'
import * as s from './PrepPlanText.styles'

/**
 * A prep plan in #144's format with each dish in its own color (#145): a thin bar down the left
 * of the dish's lines and its name on a time line in the same color, step text in the normal
 * color. The text is shown as written, so copying it reads the same as the plain plan.
 */
export default function PrepPlanText({ text }) {
  return parsePrepPlan(text).map((line, i) => {
    if (line.kind === 'gap') return <div key={i} style={s.gap} />
    if (line.kind === 'line') return <div key={i}>{line.text}</div>
    const color = line.color ? `var(--dish-${line.color})` : null
    return (
      <div key={i} style={s.bodyLine(color)}>
        {line.dish == null ? line.text : (
          <>{line.before}<span style={s.dishName(color)}>{line.dish}</span>{line.after}</>
        )}
      </div>
    )
  })
}

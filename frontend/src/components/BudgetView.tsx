import { money } from "../lib/format";
import type { Budget } from "../types";

const COLORS = ["#0f5c63", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51", "#8d99ae", "#6d597a"];

export default function BudgetView({ budget }: { budget: Budget }) {
  const pct = Math.min(100, (budget.total / budget.budget) * 100);
  return (
    <div className="card">
      <div className="budget-head">
        <div>
          <h2>Budget</h2>
          <p className="muted">{budget.summary}</p>
        </div>
        <div className={`budget-total ${budget.within_budget ? "ok-text" : "warn-text"}`}>
          {money(budget.total, budget.currency)}
          <span className="muted small"> of {money(budget.budget, budget.currency)}</span>
        </div>
      </div>
      <div className={`budget-meter ${budget.within_budget ? "" : "over"}`}>
        <div style={{ width: `${pct}%` }} />
      </div>
      <p className="small">
        {budget.within_budget
          ? `${money(budget.budget - budget.total, budget.currency)} left for extras.`
          : `${money(budget.total - budget.budget, budget.currency)} over budget.`}
      </p>
      <div className="stacked-bar" aria-hidden>
        {budget.lines.map((l, i) => (
          <div key={l.category} style={{ flexGrow: l.amount, background: COLORS[i % COLORS.length] }} title={l.category} />
        ))}
      </div>
      <table className="table">
        <tbody>
          {budget.lines.map((l, i) => (
            <tr key={l.category}>
              <td>
                <span className="swatch" style={{ background: COLORS[i % COLORS.length] }} />
                {l.category}
              </td>
              <td className="muted small">{l.notes}</td>
              <td className="num">{money(l.amount, budget.currency)}</td>
            </tr>
          ))}
          <tr className="total-row">
            <td>Total</td>
            <td />
            <td className="num">{money(budget.total, budget.currency)}</td>
          </tr>
        </tbody>
      </table>
      <p className="muted small">Flights and accommodation use the quoted prices of the selected offers; other lines are the budget agent's estimates.</p>
      {budget.savings_tips.length > 0 && (
        <>
          <h3>Ways to save</h3>
          <ul>
            {budget.savings_tips.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

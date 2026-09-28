"""Cost (week 7): turn token counts into dollars, so a run can stop at a budget."""

from __future__ import annotations

from dataclasses import dataclass

from harnessy.types import Usage


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input_per_mtok: float
    output_per_mtok: float


# --- Given -----------------------------------------------------------------------------

PRICES_CHECKED = "2026-09-28"
PRICES: dict[str, Price] = {
    # Claude API model overview (standard tier)
    "claude-opus-5": Price(5.0, 25.0),
    "claude-fable-5-1": Price(10.0, 50.0),
    # https://developers.openai.com/api/docs/models/gpt-5.5 (standard tier). Prompts over 272K
    # input tokens cost more; this table ignores that.
    "gpt-5.5": Price(5.0, 30.0),
}


# --- Week 7 exercise -------------------------------------------------------------------


def price_for(model_name: str, prices: dict[str, Price]) -> Price | None:
    """The price for model_name: an exact key; else the longest key k where model_name starts
    with k + "-" (dated ids like "gpt-5.5-2026-04-23"); else None."""
    if model_name in prices:
        return prices[model_name]
    matches = [k for k in prices if model_name.startswith(k + "-")]
    return prices[max(matches, key=len)] if matches else None


def cost_usd(usage: Usage, price: Price) -> float:
    """(input tokens × input price + output tokens × output price) / 1,000,000."""
    return (usage.input_tokens * price.input_per_mtok + usage.output_tokens * price.output_per_mtok) / 1_000_000

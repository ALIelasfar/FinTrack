"""Turning the analysis results into advice written in plain language."""

from .models import Recommendation, format_money, round_money
from .summary import average_monthly_expenses

__all__ = ["generate_recommendations"]

#: Below this savings rate we warn the user.
LOW_SAVINGS_RATE = 0.10
#: Above this savings rate we suggest investing the surplus.
HEALTHY_SAVINGS_RATE = 0.25
#: A recurring payment up to this much per month counts as "small".
SMALL_SUBSCRIPTION = 35.00


def generate_recommendations(summaries, series_list, forecast=None):
    """Build the list of recommendations from the analysis.

    Args:
        summaries: Monthly summaries, oldest first.
        series_list: The recurring payments and incomes that were found.
        forecast: The balance projection, used for overdraft warnings.

    Returns:
        list: Recommendations, most urgent first.

    Examples:
        >>> generate_recommendations([], [])
        []
    """
    if not summaries:
        return []

    findings = []
    findings += savings_findings(summaries)
    findings += subscription_findings(series_list)
    findings += category_findings(summaries)
    if forecast is not None:
        findings += liquidity_findings(forecast, summaries)

    findings.sort(key=lambda item: (item.rank, -(item.monthly_impact or 0.0)))
    return findings


def savings_findings(summaries):
    """Look at how much of the income was kept each month.

    Args:
        summaries: Monthly summaries, oldest first.

    Returns:
        list: One recommendation about the savings rate, or an empty list.
    """
    # The first and last month are usually incomplete, so leave them out.
    complete = summaries[1:-1] if len(summaries) > 2 else list(summaries)
    complete = [summary for summary in complete if summary.income > 0]
    if not complete:
        return []

    rate = sum(summary.savings_rate for summary in complete) / len(complete)
    average_net = round_money(sum(summary.net for summary in complete) / len(complete))

    if rate < LOW_SAVINGS_RATE:
        return [
            Recommendation(
                title=f"Savings rate is only {rate:.0%}",
                detail=(
                    "Across the months we looked at, very little of your income was "
                    "left over. A common target is 10 to 20 percent; cutting your "
                    "biggest non-essential category is the quickest way there."
                ),
                severity="warning",
                monthly_impact=average_net,
            )
        ]
    if rate >= HEALTHY_SAVINGS_RATE:
        return [
            Recommendation(
                title=f"Healthy savings rate of {rate:.0%}",
                detail=(
                    "You keep a large share of your income every month. Anything "
                    "above a three to six month emergency buffer could be invested "
                    "instead of sitting in the account."
                ),
                severity="info",
                monthly_impact=average_net,
            )
        ]
    return [
        Recommendation(
            title=f"Savings rate of {rate:.0%} is on track",
            detail="You keep a reasonable share of your income each month.",
            severity="info",
            monthly_impact=average_net,
        )
    ]


def subscription_findings(series_list):
    """Look at what the recurring payments cost together.

    Args:
        series_list: The recurring series that were found.

    Returns:
        list: Recommendations about the recurring costs.
    """
    outgoing = [series for series in series_list if not series.is_income]
    if not outgoing:
        return []

    total = round_money(sum(abs(series.monthly_equivalent) for series in outgoing))
    findings = [
        Recommendation(
            title=f"{len(outgoing)} recurring payments cost {format_money(total)} per month",
            detail=(
                f"That is {format_money(total * 12)} a year that is spoken for before "
                "you buy anything else. Going through this list once a year is usually "
                "the most useful hour of budgeting you can spend."
            ),
            severity="info",
            monthly_impact=total,
        )
    ]

    small = [s for s in outgoing if abs(s.monthly_equivalent) <= SMALL_SUBSCRIPTION]
    if len(small) >= 3:
        small_total = round_money(sum(abs(series.monthly_equivalent) for series in small))
        cheapest_first = sorted(small, key=lambda series: series.monthly_equivalent)
        names = ", ".join(series.label for series in cheapest_first[:5])
        findings.append(
            Recommendation(
                title=(
                    f"{len(small)} small subscriptions add up to "
                    f"{format_money(small_total)} per month"
                ),
                detail=(
                    f"Cheap on their own, not together: {names}. Cancelling the ones "
                    "you did not actively choose this year is free money."
                ),
                severity="warning",
                monthly_impact=small_total,
            )
        )

    for series in outgoing:
        if series.period_days == 365:
            findings.append(
                Recommendation(
                    title=f"Annual charge coming: {series.label}",
                    detail=(
                        f"{format_money(abs(series.average_amount))} is due around "
                        f"{series.next_due.isoformat()}. Putting "
                        f"{format_money(abs(series.monthly_equivalent))} aside each "
                        "month avoids the spike."
                    ),
                    severity="info",
                    monthly_impact=abs(series.monthly_equivalent),
                )
            )
    return findings


def category_findings(summaries):
    """Compare the latest complete month against the months before it.

    Args:
        summaries: Monthly summaries, oldest first.

    Returns:
        list: Recommendations about categories that grew or are the largest.
    """
    if len(summaries) < 4:
        return []

    recent = summaries[-2]
    history = summaries[1:-2]
    if not history:
        return []

    findings = []
    for category, amount in list(recent.by_category.items())[:6]:
        past = [summary.by_category.get(category, 0.0) for summary in history]
        average = round_money(sum(past) / len(past))
        if average <= 0 or amount <= average:
            continue

        growth = (amount - average) / average
        if growth >= 0.35 and (amount - average) >= 25.0:
            findings.append(
                Recommendation(
                    title=f"{category} spending rose {growth:.0%} in {recent.month}",
                    detail=(
                        f"You spent {format_money(amount)} against a usual "
                        f"{format_money(average)}. If it was a one-off purchase you "
                        "can ignore it, otherwise this is the best place to cut."
                    ),
                    severity="warning",
                    monthly_impact=round_money(amount - average),
                )
            )

    if recent.by_category:
        name = next(iter(recent.by_category))
        amount = recent.by_category[name]
        findings.append(
            Recommendation(
                title=(
                    f"Largest expense category: {name} "
                    f"({format_money(amount)} in {recent.month})"
                ),
                detail=(
                    "Cutting this by ten percent would free up "
                    f"{format_money(amount / 10)} every month."
                ),
                severity="info",
                monthly_impact=round_money(amount / 10),
            )
        )
    return findings


def liquidity_findings(forecast, summaries):
    """Warn about running out of money, or about sitting on too much of it.

    Args:
        forecast: The balance projection.
        summaries: Monthly summaries, used to size the buffer.

    Returns:
        list: Recommendations about the projected balance.
    """
    findings = []
    negative = forecast.first_negative
    if negative is not None:
        findings.append(
            Recommendation(
                title=f"Projected overdraft on {negative.date.isoformat()}",
                detail=(
                    f"The projection reaches {format_money(negative.balance)} that day. "
                    "Moving a big recurring payment to just after payday, or topping "
                    "the account up beforehand, avoids overdraft interest."
                ),
                severity="critical",
            )
        )

    lowest = forecast.minimum_point
    monthly = average_monthly_expenses(summaries)
    if lowest is not None and negative is None and monthly > 0:
        buffer_months = lowest.balance / monthly
        if buffer_months < 1:
            findings.append(
                Recommendation(
                    title="Projected buffer falls below one month of expenses",
                    detail=(
                        f"The low point is {format_money(lowest.balance)} on "
                        f"{lowest.date.isoformat()}, against monthly expenses of "
                        f"{format_money(monthly)}. Three months is a common target."
                    ),
                    severity="warning",
                )
            )
        elif buffer_months >= 6:
            findings.append(
                Recommendation(
                    title=f"Cash buffer covers about {buffer_months:.1f} months",
                    detail=(
                        "That is well above a normal emergency fund. The extra is "
                        "slowly losing value to inflation in a current account."
                    ),
                    severity="info",
                )
            )
    return findings

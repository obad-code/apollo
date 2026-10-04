"""MONEYPENNY's analyst team - the shape of TauricResearch/TradingAgents
(Apache-2.0, https://github.com/TauricResearch/TradingAgents), run on
Apollo's own brains and data rather than its LangGraph stack.

    1. four analysts read the same facts, each for one thing: the chart,
       the fundamentals, the news, the sentiment (insiders, Congress, crowd);
    2. a bull and a bear researcher argue over those reports, then answer
       each other once;
    3. the research manager weighs the debate into an investment plan;
    4. the trader turns the plan into a concrete proposal;
    5. three risk analysts - aggressive, neutral, conservative - pick at it;
    6. MONEYPENNY, as portfolio manager, reads all of it and gives the call.

`debate(facts_prompt, ask, final_system, step)` returns (final answer, brain,
notes). `ask(prompt, system)` -> (text, brain) is how each role thinks.
"""

import concurrent.futures as cf
import logging

log = logging.getLogger("apollo.trading_team")

_RULE = (" Use only the facts you were given; say where a number came from. "
         "Plain, concrete, under 180 words. No disclaimers.")

ANALYSTS = {
    "Market analyst": "You are the market (technical) analyst on a trading team. Read the price action: trend, "
                      "moving averages, momentum, support and resistance, volume, volatility." + _RULE,
    "Fundamentals analyst": "You are the fundamentals analyst on a trading team. Read the business: revenue and "
                            "earnings trend, margins, valuation against peers, debt, cash flow." + _RULE,
    "News analyst": "You are the news analyst on a trading team. Read the recent news and upcoming catalysts and "
                    "what they mean for the stock." + _RULE,
    "Sentiment analyst": "You are the sentiment analyst on a trading team. Read what insiders, members of Congress, "
                         "analysts and the crowd are doing and saying about it." + _RULE,
}
BULL = ("You are the bull researcher. From the analysts' reports, make the strongest honest case FOR buying. "
        "Answer the bear's points if you have them. Under 170 words.")
BEAR = ("You are the bear researcher. From the analysts' reports, make the strongest honest case AGAINST buying "
        "or for taking money out. Answer the bull's points if you have them. Under 170 words.")
MANAGER = ("You are the research manager. Weigh the bull/bear debate - do not split the difference by default; "
           "side with the stronger argument. Give an investment plan: the stance, why, and what would change it. "
           "Under 170 words.")
TRADER = ("You are the trader. Turn the investment plan into a concrete proposal: BUY, HOLD or SELL, an entry "
          "zone, where you would be wrong (stop), and a target, from the numbers given. Under 120 words.")
RISK = {
    "Aggressive risk": "You are the aggressive risk analyst. Argue for upside the trader is leaving on the table. Under 110 words.",
    "Neutral risk": "You are the neutral risk analyst. Balance the upside against the risk; size the position sensibly. Under 110 words.",
    "Conservative risk": "You are the conservative risk analyst. Point at what could lose money and how to protect it. Under 110 words.",
}


def _par(jobs):
    """{name: (prompt, system)} asked at once -> {name: text}; a role that fails says so."""
    out, brains = {}, []
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(_ASK, p, s): n for n, (p, s) in jobs.items()}
        for f in cf.as_completed(futs):
            name = futs[f]
            try:
                text, brain = f.result()
                out[name] = (text or "").strip()
                brains.append(brain)
            except Exception as e:  # noqa: BLE001 - one quiet seat never stops the table
                log.info("%s did not answer: %s", name, e)
                out[name] = f"(no answer: {e})"
    return {n: out[n] for n in jobs}, brains


_ASK = None


def debate(facts_prompt, ask, final_system, step=lambda _t: None):
    global _ASK
    _ASK = ask
    notes = {}

    step("Analyst team: market, fundamentals, news, sentiment")
    reports, brains = _par({n: (facts_prompt, s) for n, s in ANALYSTS.items()})
    notes.update(reports)
    desk = "\n\n".join(f"## {n}\n{t}" for n, t in reports.items())

    step("Bull vs bear: opening cases")
    opening, more = _par({"Bull": (desk, BULL), "Bear": (desk, BEAR)})
    brains += more
    step("Bull vs bear: rebuttals")
    rebut, more = _par({
        "Bull": (f"{desk}\n\n## The bear said\n{opening['Bear']}\n\n## You said\n{opening['Bull']}", BULL),
        "Bear": (f"{desk}\n\n## The bull said\n{opening['Bull']}\n\n## You said\n{opening['Bear']}", BEAR)})
    brains += more
    debate_text = (f"## Bull\n{opening['Bull']}\n\n{rebut['Bull']}\n\n"
                   f"## Bear\n{opening['Bear']}\n\n{rebut['Bear']}")
    notes["Bull researcher"] = f"{opening['Bull']}\n\n{rebut['Bull']}"
    notes["Bear researcher"] = f"{opening['Bear']}\n\n{rebut['Bear']}"

    step("Research manager: the investment plan")
    plan, b = ask(f"{desk}\n\n{debate_text}", MANAGER)
    brains.append(b)
    notes["Research manager"] = plan

    step("Trader: the proposal")
    proposal, b = ask(f"{desk}\n\n## Investment plan\n{plan}", TRADER)
    brains.append(b)
    notes["Trader"] = proposal

    step("Risk team: aggressive, neutral, conservative")
    risk, more = _par({n: (f"## The trader's proposal\n{proposal}\n\n## Plan\n{plan}\n\n{desk}", s)
                       for n, s in RISK.items()})
    brains += more
    notes.update(risk)

    step("MONEYPENNY: the final call")
    team = "\n\n".join(f"## {n}\n{t}" for n, t in notes.items())
    final, b = ask(f"{facts_prompt}\n\n# Your team's work\n{team}\n\n"
                   "You are the portfolio manager: read your team's work, overrule it where the facts say so, "
                   "and give the final call in your usual shape.", final_system)
    brains.append(b)
    brain = max(set(brains), key=brains.count) if brains else b
    return final, f"{brain} · team", notes


def appendix(notes):
    """The team's notes, for the end of the report - read them in full in the reader."""
    if not notes:
        return ""
    return "\n\n## The team's notes\n\n" + "\n\n".join(f"### {n}\n{t}" for n, t in notes.items())

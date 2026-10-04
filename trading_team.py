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


# -- the real TradingAgents, when it is installed ------------------------------------------
# pip install "git+https://github.com/TauricResearch/TradingAgents" (update.bat does it).
# It reads its own data (Yahoo, SEC EDGAR) and runs its own LangGraph team; MONEYPENNY
# then reads everything it wrote and makes the call.

def installed():
    try:
        import tradingagents.graph.trading_graph  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - not installed, or a broken install: the built-in team runs
        return False


def _config():
    import os
    from tradingagents.default_config import build_default_config
    config = build_default_config()
    if not os.environ.get("TRADINGAGENTS_LLM_PROVIDER"):          # your own choice wins
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
            config.update(llm_provider="google",
                          quick_think_llm=os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM") or "gemini-flash-latest",
                          deep_think_llm=os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM") or "gemini-pro-latest")
        elif os.environ.get("ANTHROPIC_API_KEY"):
            config.update(llm_provider="anthropic",
                          quick_think_llm=os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM") or "claude-sonnet-5-5",
                          deep_think_llm=os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM") or "claude-opus-5-5")
    return config


def _text(value):
    if isinstance(value, dict):
        return "\n\n".join(_text(v) for v in value.values() if v)
    return str(value or "").strip()


def run_real(symbol, step=lambda _t: None, graph=None, today=None):
    """TradingAgents on one ticker -> (signal, notes) - notes in the same shape as `debate`'s."""
    import datetime as dt
    if graph is None:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        graph = TradingAgentsGraph(debug=False, config=_config())
    step(f"TradingAgents on {symbol}: analysts, bull/bear debate, trader, risk team (a few minutes)")
    state, signal = graph.propagate(symbol, (today or dt.date.today()).isoformat())
    debate_s = state.get("investment_debate_state") or {}
    risk_s = state.get("risk_debate_state") or {}
    notes = {
        "Market analyst": _text(state.get("market_report")),
        "Fundamentals analyst": _text(state.get("fundamentals_report")),
        "News analyst": _text(state.get("news_report")),
        "Sentiment analyst": _text(state.get("sentiment_report")),
        "Bull researcher": _text(debate_s.get("bull_history")),
        "Bear researcher": _text(debate_s.get("bear_history")),
        "Research manager": _text(state.get("investment_plan")),
        "Trader": _text(state.get("trader_investment_plan")),
        "Aggressive risk": _text(risk_s.get("aggressive_history")),
        "Neutral risk": _text(risk_s.get("neutral_history")),
        "Conservative risk": _text(risk_s.get("conservative_history")),
        "TradingAgents' portfolio manager": f"Rating: {signal}\n\n" + _text(state.get("final_trade_decision")),
    }
    return signal, {k: v for k, v in notes.items() if v}


def with_real(symbol, facts_prompt, ask, final_system, step=lambda _t: None, graph=None):
    """The real team's work, then MONEYPENNY's call on it."""
    signal, notes = run_real(symbol, step, graph)
    step("MONEYPENNY: reading the team's work for the final call")
    team = "\n\n".join(f"## {n}\n{t}" for n, t in notes.items())
    final, brain = ask(f"{facts_prompt}\n\n# Your team's work (TradingAgents)\n{team}\n\n"
                       f"Their rating: {signal}. You are the portfolio manager over this team: read their "
                       "work, overrule it where the facts say so, and give the final call in your usual shape.",
                       final_system)
    return final, f"{brain} · TradingAgents", notes

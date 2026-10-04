import trading_team


def test_the_whole_table_sits_and_moneypenny_has_the_last_word():
    seen = []

    def ask(prompt, system):
        seen.append((prompt, system))
        if system == "FINAL":
            return "SUMMARY: Hold it.\nVERDICT: HOLD", "Gemini"
        return f"note from {system[:20]}", "Gemini"

    steps = []
    final, brain, notes = trading_team.debate("FACTS", ask, "FINAL", steps.append)
    assert final.startswith("SUMMARY: Hold it.")
    assert brain == "Gemini · team"
    assert len(seen) == 14                       # 4 analysts, 2+2 debate, manager, trader, 3 risk, final
    assert seen[-1][1] == "FINAL" and "Your team's work" in seen[-1][0]
    assert set(trading_team.ANALYSTS) <= set(notes) and "Trader" in notes
    assert "## The team's notes" in trading_team.appendix(notes)


def test_a_seat_that_fails_never_stops_the_call():
    def ask(prompt, system):
        if system.startswith("You are the news"):
            raise RuntimeError("down")
        return ("SUMMARY: ok." if system == "F" else "x"), "Gemini"

    final, _brain, notes = trading_team.debate("FACTS", ask, "F")
    assert final == "SUMMARY: ok."
    assert notes["News analyst"].startswith("(no answer")

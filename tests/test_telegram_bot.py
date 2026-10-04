import telegram_bot as tb


def run(text):
    calls = []
    out = tb.handle(text, make_short=lambda t: calls.append(("short", t)), make_batch=lambda: calls.append(("batch",)),
                    choose=lambda n: calls.append(("choose", n)) or {"result": "ok"}, status=lambda: "s")
    return out, calls


def test_commands():
    assert run("short about octopuses")[1] == [("short", "octopuses")]
    assert run("شورت عن الاخطبوط")[1] == [("short", "الاخطبوط")]
    assert run("نزل رقم ٢")[1] == [("choose", 2)]
    assert run("post 1")[1] == [("choose", 1)]
    assert run("لا تنزل شي")[1] == [("choose", 0)]
    assert run("today")[1] == [("batch",)]
    assert run("hello")[0] == tb.HELP

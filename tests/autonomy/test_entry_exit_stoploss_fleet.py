import datetime as dt
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import study_entry_exit_stoploss_fleet as audit  # noqa: E402


def _row(bot, reason, pnl, pct, o, c):
    z = dt.timezone.utc
    t0 = dt.datetime(2026, 1, 1, tzinfo=z)
    return {
        "bot": bot,
        "reason": reason,
        "pnl_abs": pnl,
        "pnl_pct": pct,
        "opened_at": (t0 + dt.timedelta(hours=o)).isoformat(),
        "closed_at": (t0 + dt.timedelta(hours=c)).isoformat(),
    }


def test_stop_suffix_detection_and_reason_parsing():
    assert audit.is_stop_reason("long-breakoutup_trailing_stop_loss")
    assert audit.is_stop_reason("short-divergence_sl")
    assert not audit.is_stop_reason("long-breakoutup_tp")
    assert audit.exit_reason({"reason": "", "tag": "short-divergence_tp"}) == "tp"


def test_far_close_and_advisories():
    rows = []
    for i in range(20):
        rows.append(_row("b1", "decay_paid", 2.0, 0.01, i, i + 60))
    for i in range(30):
        rows.append(_row("b1", "short_flip", -1.0, -0.004, i, i + 8))
    for i in range(12):
        rows.append(_row("b1", "short_sl", -0.5, -0.003, i, i + 1))
    rows.append(_row("b2", "only_exit", -1.0, -0.01, 0, 12))

    pnl = {"bots": [{"bot": "b1"}, {"bot": "b2"}, {"bot": "b3"}]}
    out = audit.run_audit(pnl, rows, close_n=10)
    by = {r["bot"]: r for r in out}

    assert by["b1"]["far"]["n"] == 62
    assert by["b1"]["close"]["n"] == 10
    assert by["b1"]["far"]["stop_n"] == 12
    assert by["b1"]["far"]["stop_usd"] < 0
    assert by["b1"]["far"]["best_reason"] == "decay_paid"
    assert by["b1"]["far"]["worst_reason"] == "short_flip"
    assert by["b1"]["far"]["hold_ratio"] is not None and by["b1"]["far"]["hold_ratio"] >= 3.0
    assert by["b1"]["impact"] > 0
    assert any("stops are net negative" in a for a in by["b1"]["advisories"])
    assert any("top loser exits far earlier" in a for a in by["b1"]["advisories"])

    assert by["b2"]["far"]["single_exit"] is True
    assert any("single-exit losing profile" in a for a in by["b2"]["advisories"])

    assert by["b3"]["far"]["n"] == 0
    assert by["b3"]["advisories"][0].startswith("no closes yet")
    tops = audit.top_issues(out, limit=2)
    assert tops[0]["bot"] == "b1"


def test_cli_json_output_and_selftest(tmp_path):
    pnl = tmp_path / "pnl.json"
    trades = tmp_path / "trades.json"
    out = tmp_path / "out.json"
    pnl.write_text(json.dumps({"bots": [{"bot": "b1"}]}))
    trades.write_text(json.dumps({"trades": [_row("b1", "long_tp", 1.0, 0.01, 0, 2)]}))

    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "study_entry_exit_stoploss_fleet.py"),
            "--pnl-json",
            str(pnl),
            "--trades-json",
            str(trades),
            "--json-out",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert "| b1 |" in r.stdout
    payload = json.loads(out.read_text())
    assert payload["rows"][0]["bot"] == "b1"

    s = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "study_entry_exit_stoploss_fleet.py"), "--selftest"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert s.returncode == 0, s.stderr
    assert "selftest OK" in s.stdout


def test_cli_compare_before_after(tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "bot": "b1",
                        "impact": 3.0,
                        "far": {"usd": -10.0},
                        "close": {"mean_pct": -0.2},
                    }
                ]
            }
        )
    )
    after.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "bot": "b1",
                        "impact": 1.0,
                        "far": {"usd": -2.0},
                        "close": {"mean_pct": 0.1},
                    }
                ]
            }
        )
    )
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "study_entry_exit_stoploss_fleet.py"),
            "--compare-before",
            str(before),
            "--compare-after",
            str(after),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert "# Before vs after" in r.stdout
    assert "| b1 | 3.00 | 1.00 | -2.00 | -10.00 | -2.00 | +8.00 | -0.200 | +0.100 |" in r.stdout


def test_cli_edge_report_mode(tmp_path):
    pnl = tmp_path / "pnl.json"
    trades = tmp_path / "trades.json"
    pnl.write_text(json.dumps({"bots": [{"bot": "b1"}]}))
    trades.write_text(
        json.dumps(
            {
                "trades": [
                    _row("b1", "long_tp", 2.0, 0.02, 0, 2),
                    _row("b1", "long_sl", -1.0, -0.01, 3, 4),
                ]
            }
        )
    )
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "study_entry_exit_stoploss_fleet.py"),
            "--pnl-json",
            str(pnl),
            "--trades-json",
            str(trades),
            "--edge-report",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert "# What's each bot's edge" in r.stdout
    assert "| b1 | 2 | +1.00 | tp | tp ($+2.00); main drag: sl ($-1.00) |" in r.stdout

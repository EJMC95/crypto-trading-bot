"""[2026-08-19] Every workflow `run:` block must be valid shell.

WHY THIS EXISTS, measured: the 🧭 nav-cook birth `(ri)` shipped its deploy rule
COMMENTED OUT — the standard `(lr)`/`(mk)` pre-provision pattern — but commented
the `if` and its body while leaving the **`fi` uncommented**:

    # if echo "$changed" | grep -qE "..."; then
    #   svcs="${svcs:+$svcs,}nav-cook-shadow"
    fi                                   <-- stray, no opening `if`

`railway-redeploy.yml`'s decide step then died with
`line 265: syntax error near unexpected token 'fi'` — and because the decide
step runs BEFORE any deploy, **every service stopped receiving code**. Three
hours and three merges landed on main and reached no container; the runs went
red in a way that reads like any other CI failure, so nothing said "your fleet
is frozen".

`audit_deploy_coverage` could not catch this: it reasons about which PATHS map
to which services, not about whether the script it lives in can execute. The
born-dark guard is the same shape one level up — a rule that cannot RUN is
exactly as dark as a file that was never COPY'd.
"""
import pathlib
import subprocess
import sys

import pytest

try:
    import yaml
except ImportError:                      # pragma: no cover
    yaml = None

ROOT = pathlib.Path(__file__).resolve().parents[2]
WF = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def _run_blocks(path):
    """[(step_name, shell_source)] for every `run:` in the file."""
    doc = yaml.safe_load(path.read_text())
    out = []
    for job_name, job in ((doc or {}).get("jobs") or {}).items():
        for i, step in enumerate(job.get("steps") or []):
            src = step.get("run")
            if not isinstance(src, str) or not src.strip():
                continue
            # a non-bash shell (python, pwsh) is not ours to parse
            if str(step.get("shell", "bash")).split()[0] not in ("bash", "sh"):
                continue
            out.append((f"{path.name}:{job_name}[{i}] "
                        f"{step.get('name') or 'unnamed'}", src))
    return out


@pytest.mark.skipif(yaml is None, reason="pyyaml not installed")
@pytest.mark.parametrize("wf", WF, ids=lambda p: p.name)
def test_every_run_block_is_valid_shell(wf, tmp_path):
    blocks = _run_blocks(wf)
    for label, src in blocks:
        f = tmp_path / "step.sh"
        f.write_text(src)
        r = subprocess.run(["bash", "-n", str(f)],
                           capture_output=True, text=True)
        assert r.returncode == 0, (
            f"{label} is not valid shell — it will die at runtime BEFORE doing "
            f"anything, and for a deploy workflow that means every service "
            f"silently stops receiving code:\n{r.stderr.strip()}")


@pytest.mark.skipif(yaml is None, reason="pyyaml not installed")
def test_the_guard_actually_inspects_the_deploy_decider():
    """A check that inspects nothing reports clean ((po)). Prove this guard
    reaches the specific step that broke — the biggest block in the repo."""
    wf = ROOT / ".github" / "workflows" / "railway-redeploy.yml"
    assert wf.exists()
    blocks = _run_blocks(wf)
    assert blocks, "no run blocks found in railway-redeploy.yml"
    biggest = max(len(src.splitlines()) for _, src in blocks)
    assert biggest > 100, (
        f"expected the decide step (~268 lines); biggest found {biggest} — "
        "the parser is probably not reaching it")


@pytest.mark.skipif(yaml is None, reason="pyyaml not installed")
def test_it_would_have_caught_the_nav_cook_stray_fi(tmp_path):
    """The positive control: the exact shape that broke, must fail."""
    bad = tmp_path / "bad.sh"
    bad.write_text('if [ 1 = 1 ]; then\n  echo a\nfi\n'
                   '# if [ 2 = 2 ]; then\n#   echo b\nfi\n')
    r = subprocess.run(["bash", "-n", str(bad)], capture_output=True, text=True)
    assert r.returncode != 0, "the control must be rejected, or the test is vacuous"
    assert "fi" in r.stderr

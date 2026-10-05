"""Run every test suite in order on a fresh test database and print the totals.

Usage (from the project folder):  python tests/run_all.py

Suites 1-5 share one test database and must run in order (each continues from the
data the previous one left). Suites 1-6 drive the terminal program the way a person
would, so they need macOS or Linux (on Windows, getpass reads the keyboard directly
and cannot be fed test input). Suites 7 and 8 test the service functions and the CLI
compatibility. Test files are written to tests/_work/, which is deleted and recreated
on every run.
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = [
    "suite_1_core_and_cancel.py",
    "suite_2_add_item.py",
    "suite_3_remove_item.py",
    "suite_4_transfer.py",
    "suite_5_employees.py",
    "suite_6_seed.py",
    "suite_7_services.py",
    "suite_8_cli_compat.py",
]


def main():
    work = os.path.join(HERE, "_work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    env = dict(os.environ, RESTAURANT_TEST_WORK=work)
    passed = total = 0
    problems = []
    for suite in SUITES:
        proc = subprocess.run([sys.executable, os.path.join(HERE, suite)], capture_output=True, text=True, env=env)
        out = proc.stdout + proc.stderr
        found = re.search(r"(\d+)/(\d+) checks passed", out)
        if found:
            ok, n = int(found.group(1)), int(found.group(2))
            passed, total = passed + ok, total + n
            print(f"{suite:<28} {ok:>4}/{n:<4} {'ok' if ok == n else 'FAILED'}")
            problems += [f"{suite}: {line}" for line in out.splitlines() if line.startswith("[FAIL]")]
        elif "SKIPPED" in out:
            print(f"{suite:<28} skipped: {out.strip().splitlines()[-1]}")
        else:
            print(f"{suite:<28} CRASHED")
            problems.append(f"{suite} crashed:\n{out[-2000:]}")
    print(f"\nTotal: {passed}/{total} checks passed")
    for p in problems:
        print(p)
    sys.exit(0 if passed == total and not problems else 1)


if __name__ == "__main__":
    main()

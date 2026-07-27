# Suite evidence: proving the tests passed without running them again

**Component:** `enforcement/scripts/verify_suite.py`
**Event:** `suite_green` (restricted)
**Gates:** `fix_commit`, `iteration_boundary`, `set complete perspective`, `converge`

This is the mechanism that lets a gate *know* the test suite passed instead of
running it to find out. It has two halves that are easy to confuse, and the
distinction matters more than any implementation detail here:

| Half | Question it answers | What it is |
|---|---|---|
| **Tree hash** | *Was this exact code proven green?* | an integrity claim |
| **Impact graph selection** | *Which tests are worth running?* | a cost optimisation |

Getting those backwards is how a test-selection tool becomes a false-green
generator. The rest of this document is mostly about keeping them apart.

---

## The problem

The fix loop used to run the target's full test suite **three times per
finding**, and only one of those runs was enforced:

| Where | Enforced? |
|---|---|
| Fix subagent, after writing the fix | prose only |
| Orchestrator, after committing | prose only |
| The `fix_commit` gate | yes |

The last two ran on a byte-identical working tree — `git commit` does not touch
working-tree contents — so at least one was pure waste. On the eval harness's
own numbers (90 fixes, a 60-second suite) that is roughly **4.7 hours** of
pytest where 1.5 hours was budgeted.

The fix is not "run it less" but "run it once and *record* the result in a form
a gate can verify". That record is the `suite_green` event.

---

## Part 1 — The tree hash

`suite_green` carries a `tree_hash`. A gate recomputes that hash and asks the
ledger whether a green already names it. Same hash means the code is
byte-for-byte what was proven; anything else blocks.

### It names content, and nothing else

The hash is `sha256("tree:" + <git tree oid of the working tree>)`. It is
invariant under every operation that leaves file *contents* alone:

```
git add          -> same hash
git commit       -> same hash
git commit --amend -> same hash
```

That invariance is the point. Because `git commit` cannot change the hash, the
green a subagent records before the commit is still valid at the `fix_commit`
gate after it — so the loop needs **one** recorded suite run per fix, not one on
each side of the commit.

An earlier version mixed `HEAD`'s commit oid into the hash. It was *stricter*
than "same content", and the cost of that strictness was a whole extra suite run
on every single fix to restore evidence the commit had invalidated without
changing a byte.

### How it is computed, and why it looks convoluted

```
copy .git/index  ->  scratch index   (preserving mtime — see below)
GIT_INDEX_FILE=scratch  git add -A -- ':(exclude)docs/holtz'
GIT_INDEX_FILE=scratch  git rm --cached -r --ignore-unmatch docs/holtz
GIT_INDEX_FILE=scratch  git write-tree
```

Three deliberate choices:

**The index is a copy, so `--check` never touches staging state.** A gate is a
predicate; it must not reorganise the repository it is inspecting.

**The object directory is redirected.** `git add` writes blobs, and a gate that
grew the target's `.git/objects` on every check would leave unreferenced garbage
in a repo it was only supposed to read. `GIT_OBJECT_DIRECTORY` points at a temp
dir with the real store as `GIT_ALTERNATE_OBJECT_DIRECTORIES`, so dedup still
works — existing objects are found through the alternate and not rewritten —
and everything new is discarded on the way out. Measured effect on the target's
object count: zero.

**The copy preserves the index's mtime (`shutil.copy2`, not `copyfile`), and
this one is a genuine trap.** Git answers "has this file changed?" from the
index's stat cache: same size and same mtime is taken as unchanged *without
reading a byte*. Git stores whole seconds, so a file rewritten in the same
second it was staged is indistinguishable that way — the classic "racy git"
problem. Git's own guard is to distrust any entry whose mtime is not older than
the **index file's own mtime** and re-read its content.

A copy stamped with the current time silently disables that guard: every entry
then looks safely older than the index. A same-second, same-size edit —
`return a + b` → `return b + a` is exactly that — would be read off the stale
cached oid, and the hash would name a tree that no longer exists. That is a
green for code nobody ran.

This is not theoretical. It reproduced **5 times in 12** in the project's own
test suite before the fix. `TestTreeHash::test_a_same_second_same_size_edit_is_not_missed`
forces the condition deterministically (via `core.trustctime = false`, so the
changed ctime does not mask the mtime question) rather than racing for it.

### Cost

Seeding from the real index preserves git's stat cache, so only files whose stat
data actually changed get re-hashed. This keeps the hash O(changed files) rather
than O(repo):

| Repo | Hash cost |
|---|---:|
| 8,000 files / 63 MB | ~40 ms |
| A cold (uncached) index, same repo | ~190 ms |

Against the seconds of test execution it replaces, this is free.

### What it covers, and what it does not

**Excluded:** everything under `docs/holtz/`. STATUS.md and PUNCHLIST.md are
rewritten on every fix, and the ledger itself is appended to by `--record` —
counting them would invalidate the hash the instant it was written. None of them
can affect the target's tests. Files git ignores (`.venv`, `__pycache__`, build
output) are excluded too, which is what stops a byte-compile from invalidating a
green suite.

**Included:** tracked files, tracked-and-deleted files (so "delete the failing
test" cannot reuse a green), and untracked-but-not-ignored files.

**Two stated limitations, accepted deliberately:**

1. **The interpreter and installed dependencies are not covered.** Upgrading a
   package without touching a lockfile leaves a stale green valid. Lockfiles are
   tracked, so the ordinary case is covered; a bare `pip install -U` is not.

2. **A green survives a change to git history.** Amending a commit message does
   not change content, so it does not change the hash. For a target whose suite
   *lints commit messages* that is a false green. It is accepted because the
   alternative — mixing `HEAD` into the hash — imposes a universal cost (an
   extra full suite run per fix) to defend against a rare case.

### Why the agent cannot forge one

Four independent layers:

1. `suite_green` is declared `restricted`, so the daemon refuses a bare
   `sahjhan event suite_green`.
2. The writer lives under `enforcement/`, a managed path the pre-edit hook and
   `bash_guard` refuse to let the agent modify.
3. `enforcement/trusted-callers.toml` pins the script's SHA-256, so a modified
   copy fails peer authentication.
4. The script accepts **no** caller-supplied hash or result. It computes the
   hash itself, runs the suite itself, and writes only on an observed exit 0.

> **Maintenance note.** Editing `verify_suite.py` invalidates its pinned hash.
> Run `scripts/hash-trusted-callers.sh` afterwards or the daemon rejects the
> writer with "caller not authenticated" — and only `real_daemon` tests catch it.

---

## Part 2 — The impact graph, and why it is *only* a cost optimisation

`--scope affected` runs the tests the impact graph says cover what changed,
instead of the whole suite. `docs/holtz/impact-graph.json` is **agent-authored**,
which bounds hard what an affected green may claim:

> An `affected` green is a statement about **cost**, not about **integrity**. A
> bogus `tests` edge can narrow one `fix_commit`. It cannot survive the next
> `iteration_boundary`, which accepts `full` and nothing else.

That layering is the whole safety argument, and it is why the boundary gates
must stay strict:

| Transition | Scope demanded |
|---|---|
| `fix_commit` | `affected` |
| `iteration_boundary` | `full` |
| `set complete perspective` | `full` |
| `converge` | `full` |

The graph is read as **data**. `impact_graph.py` is never imported, because this
process is the one the daemon authenticates to write a restricted event, and
`skills/holtz/scripts/` is not a protected path — importing agent-authored
*code* into the trusted identity would let an import-time monkeypatch forge
greens outright. Reading agent-authored *data* is a strictly smaller hole, and it
is the hole the design already accepts.

### Measured from the last *full* green

"Changed files" needs a "since when", and the obvious answers are both wrong.
`git diff HEAD` is empty at record time. `HEAD~1` is a heuristic ("one fix, one
commit") standing in for a fact.

So `suite_green` carries `commit_hash`, and the baseline is the newest
**`scope='full'`** green's commit. `git diff --name-only <baseline>` then spans
committed *and* uncommitted work in one command.

Baselining on the last **full** green rather than the last green of any scope is
the substantive half. Chaining affected runs off each other is only sound if the
selection is complete, and a hand-authored graph is not — a file nobody drew a
`tests` edge for would drop out of every window forever. Measuring from the last
full green bounds the gap to one iteration, and `iteration_boundary` re-bases it.

### Narrowing is earned per file, then earned again at run time

Every uncertainty widens back to the full suite. The grain is **per changed
file**, because one unaccounted-for file must widen the whole run rather than
quietly drop out of it:

| Changed file | Result |
|---|---|
| a test file (`test_*.py` / `*_test.py`) | selects itself |
| any `conftest.py` | **widens** — its reach is every test below it, and no edge says so |
| a source file with a `tests` edge | selects the covering tests |
| a source file with no `tests` edge | **widens** |
| an edge naming a test file that no longer exists | **widens** |
| no readable graph | **widens** |
| nothing changed since the baseline | **widens** (never "run zero tests") |

Then a second guard *after* the run: pytest exits **4** on a usage error and **5**
on an empty collection, and neither is a statement about the code. A narrowed run
ending that way re-runs the full suite instead of recording. **Zero tests executed
must never satisfy a gate.** This is also what keeps exotic `$HOLTZ_PYTEST`
overrides working — one that rejects trailing paths widens instead of wedging.

### The recorded scope is what *ran*

A request for `affected` that widened records `full`. That is true, and strictly
stronger, since a `full` green satisfies an `affected` check. Recording the
request instead would understate the run and waste the stronger evidence.

---

## The per-fix shape

One recorded suite run per fix, consumed twice:

| Step | Command | Consumer |
|---|---|---|
| subagent, **last** | `--record --scope affected` | orchestrator step 10 |
| orchestrator 10 | `--check --scope affected` | — (free ledger read) |
| `fix_commit` gate | `--check --scope affected` | — (free ledger read) |

Orchestrator step 10 is *stronger* than the full-suite re-run it replaced: it
proves the subagent really ran the suite **and** that the tree has not drifted
since, where a re-run only ever proved the second.

**The record must be the subagent's last step.** The green is bound to a hash of
the working tree, so any later edit invalidates it — the hardening test
especially. v0.141.2 shipped with the record at subagent step 5 and the hardening
write at step 8, which meant step 10's check could never pass and the orchestrator
was told to reject every good fix. Pinned now by
`test_the_subagent_records_the_green_last`.

Cost, on the eval harness's numbers: 2 affected runs per fix became 1, and the
full-suite runs are confined to iteration boundaries — roughly **4.7 h → ~20 min**.

---

## Operating it

```bash
# Agent path: run the suite, record the green.
python3 enforcement/scripts/verify_suite.py --record --scope affected
python3 enforcement/scripts/verify_suite.py --record --scope full

# Gate path: pure predicate, exit 0/1, no daemon socket.
python3 enforcement/scripts/verify_suite.py --check --scope affected

# Diagnostics.
python3 enforcement/scripts/verify_suite.py --print-tree-hash
python3 enforcement/scripts/verify_suite.py --print-affected   # empty => would run everything
```

`--print-affected` exists because a selection that has quietly degraded to the
full suite forever is otherwise indistinguishable from one that works, and the
cost this mechanism removes would come back unnoticed.

**Non-standard test commands.** `$HOLTZ_PYTEST` overrides the suite command
(default `python3 -m pytest -x --ff --tb=short -q`, defined once, in
`DEFAULT_PYTEST`). Export it at run start if the target's tests need a
venv/tox/poetry wrapper.

Two flags are banned from the default and should stay that way:

- **`--lf` / `--last-failed`** runs *only* the previously-failing tests, so a
  gate using it can pass having executed a two-test subset. `--ff`
  (`--failed-first`) gives the same fail-fast benefit and still runs everything.
- **`--no-cov`** is a pytest-cov option; on a target without that plugin pytest
  exits 4 on the unrecognised argument, breaking every such target.

**Reading the ledger.** `--check` goes through `sahjhan query`, which opens the
ledger file directly — there is no socket anywhere in that path, so a gate
running inside a transition cannot re-enter the daemon that is evaluating it.
Delegating rather than parsing `ledger.jsonl` also means the block condition and
the evidence resolve to the same file by construction, instead of through a
reimplementation of the engine's ledger-resolution chain that could drift.

**Every block prints its escape.** A project whose ledger was never initialised
makes the query fail with an I/O error; to the agent that means the same thing an
empty result does, and is cleared by the same command. So a block prints the
underlying reason *and* the exact `--record` line. The one exception is a broken
toolchain (no sahjhan binary, unhashable tree): there `--record` would fail
identically, and a printed escape that cannot run is worse than none.

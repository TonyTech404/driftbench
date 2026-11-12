## What this changes

<!-- One or two sentences. Link the issue it closes, e.g. "Closes #12". -->

## Checklist

- [ ] `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` pass

**If you added or changed questions:**

- [ ] Each change is confirmed in a primary source, linked in `source_url`
- [ ] The old API is deprecated or removed in the latest release
- [ ] Each question has an outdated and a current sample in `tests/test_questions.py`

**If you added a tool:**

- [ ] Offline tests in `tests/test_tools.py` check the request it sends and how it reads replies
- [ ] It's added to `tests/test_live.py`, and the live test passes (say so below)
- [ ] It's listed in the README's Tools table

**If you changed labeling:**

- [ ] I re-labeled the saved results with `driftbench relabel` and explain any changed labels below

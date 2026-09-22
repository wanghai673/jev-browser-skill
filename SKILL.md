---
name: jev-browser
description: Execute browser tasks in the user's Chrome, including navigation, search, forms, filtering and media. Use for website operations, even without a Jev mention. Excludes research-only questions and browser explanations. Respect an explicitly requested browser or tool.
---

# Jev Browser

Before a task that may require typing, **Codex must prepare candidate text** and pass it through `--inputs`. Each candidate has a literal `value` and its intended `purpose`. **Jev chooses whether to fill, which field and which candidate; code inserts that literal unchanged.** Candidates are options, not mandatory steps. No text-generation model is used.

Run the entire confirmed task in one call, including the prepared candidates:

```sh
python3 <skill-dir>/scripts/jev.py run \
  --url 'https://www.bilibili.com' \
  --goal 'Search Bilibili for machine learning and open the search results.' \
  --inputs '[{"value":"machine learning","purpose":"Bilibili search query"}]' \
  --show
```

- Resolve only material target ambiguity before starting. Use a known starting URL; do not invent account IDs.
- Every call starts fresh. No old task, session, history or resume state is retained. Browser pages and login remain.
- Within a call, Jev receives bounded earlier page observations and navigation evidence so it can finish cross-page tasks without repeating established checks. This context is discarded on exit.
- Let Jev run until DONE or failure. Wait on the same shell process if the tool yields; do not inspect intermediate state, redelegate, supervise clicks or correct ordinary mistakes.
- Use `--show` only when the user asks to open, see or play the page; otherwise work in the background.
- Omit `--inputs` only for tasks without typing. Missing candidate text returns an input error. Never pass credentials or invent missing personal details.
- Only for an explicitly selected existing tab, use `tabs` to find its ID, then replace `--url` with `--target-id ID`. A new call still has fresh task context.
- The result includes final page evidence, recent actions and timings. Review it once after DONE or failure. No separate show, finish, state or close calls. Do not treat DONE alone as proof of success.
- Login, human verification, unavailable input/control, crash or the whole-call limit returns an error. Explain the blocker; user-only steps stay with the user. After their requested continuation, start a fresh call on their selected tab.

Python 3, `uv` and Chrome remote debugging are required. `run --help` lists options. Defaults are 200 actions / 300 seconds for the whole call, with no periodic handoff.

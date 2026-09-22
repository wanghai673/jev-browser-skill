---
name: jev-browser
description: Execute browser tasks in the user's Chrome, including navigation, search, forms, filtering and media. Use for website operations, even without a Jev mention. Excludes research-only questions and browser explanations. Also use when the user asks to configure the Jev API. Respect an explicitly requested browser or tool.
---

# Jev Browser

## Configure Jev

When asked to configure the API, handle setup directly through local file tools; do not start a browser task.

- Use `JEV_CONFIG_DIR/.env` when set, otherwise `~/.config/jev-browser/.env`. Inspect only whether `TYPESAFE_API_KEY` and `TYPESAFE_MODEL` are configured; never print existing secrets.
- Reuse existing configuration unless the user requests a change. For a missing key, ask the user to provide it through a local file or secret input available in their client. If the user already supplied a key for this setup, write it without echoing it; never recover keys from conversation history.
- Set `TYPESAFE_API_KEY` to the supplied value and default `TYPESAFE_MODEL` to `jev-latest`. Preserve unrelated settings and any existing model unless a change was requested. The file uses literal `KEY=value` lines without quotes; reject embedded newlines in supplied values.
- Keep the configuration outside the repository, create its directory with mode `700`, and write the file with mode `600`. Do not put keys in command-line arguments, logs, browser inputs, or replies.
- Verify locally that the runtime loader resolves a nonempty key and the intended model, reporting only configuration status, path, and model. Process environment variables override the file. This check does not establish API validity; make an API request only when the user asks to test it or starts a browser task.

## Run a browser task

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
- When Jev returns a result, stop browser work and report that result directly. Accept DONE as the end of the task; do not independently check completion, inspect the browser again, or start a second call to verify, correct, or improve the result. Report only what the returned result supports.
- A further browser call requires a new explicit user request to continue, retry, or change the task. No separate show, finish, state or close calls after the result.
- Login, human verification, unavailable input/control, crash or the whole-call limit returns an error. Explain the blocker; user-only steps stay with the user. After their requested continuation, start a fresh call on their selected tab.

Python 3, `uv` and Chrome remote debugging are required. `run --help` lists options. Defaults are 200 actions / 300 seconds for the whole call, with no periodic handoff.

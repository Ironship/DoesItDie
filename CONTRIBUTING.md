# Contributing to DoesItDie

Thanks for helping. Pull requests are welcome; here's what happens to them.

## Review

Every pull request from outside the project gets a full written review before it's merged: each changed line is
read, and the review is posted on the pull request. Nothing merges on a green check alone. Expect questions.

The owner reviews every change (see `.github/CODEOWNERS`). Changes to the release workflow (`.github/`), `.pkgmeta`,
the `.toc` or the `tools/` scripts get extra scrutiny and may be asked to move to their own pull request.

## Before you open one

- Keep it to one fix or feature. Big pull requests that mix several are slow to review and may be split.
- Run the tests: `pip install lupa`, then every `tools/test_*.py`. They also run on your pull request; a maintainer
  may need to approve that run first.
- Read `CLAUDE.md`: it explains why the addon works the way it does (Forever's secret values) and lists what's
  verified in game and what isn't. Update it if your change makes it wrong.
- Say what you tested in game and what you didn't.

## Not accepted

- Code that's minified, encoded, obfuscated or downloaded at run time.
- Chat output, whispers, addon messages or anything else sent to other players, unless it's the point of the change,
  opt-in, and described in the pull request.
- Changes to the release workflow or its secrets bundled with an unrelated change.

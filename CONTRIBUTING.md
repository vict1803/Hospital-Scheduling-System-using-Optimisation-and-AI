# Working agreement

1. Do not commit directly to `main`.
2. Work on your own branch, named `<name>-<topic>` (for example `cha-tests`, `victoria-checker`).
3. One owner per folder under `src/`. Change someone else's folder only through a pull request they review.
4. Tests go in `tests/`. One file per person per area, named `test_<area>_<name>.py`. Never edit another person's test file.
5. Open a pull request into `main`. One other team member reviews it before it is merged.
6. Once the engine exists, tests must pass before merging.
7. Keep `main` in a working state. Before merging, run `git merge main` into your branch and re-run the tests.
8. Never commit patient data, passwords or API keys.

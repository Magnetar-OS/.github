# Magnetar-OS/.github

The organisation profile shown at [github.com/Magnetar-OS](https://github.com/Magnetar-OS):
[`profile/README.md`](profile/README.md) and the images it embeds — plus the art every
other repository's README shares: a banner per repository (`profile/assets/repos/`), the
link buttons, and the app icons in the suite strip at the foot of each one.

Every image in `profile/assets/` is drawn by [`tools/build.py`](tools/build.py) from
`magnetar-brand` (the logo and app icons) and the fonts `magnetar-web` ships, with all text
converted to outlines so it renders in the brand's typefaces on any machine. Edit the script,
not the SVGs:

```sh
python3 tools/build.py   # expects ../magnetar-brand and ../magnetar-web (after pnpm install)
```

It needs Python 3.12+ with `fonttools` and `brotli`. App summaries, benchmarks and the measured
figures are copied from `magnetar-web/src/data/suite.ts`; change them there first.

Art and text are [CC BY-SA 4.0](LICENSE), as in `magnetar-brand`. The fonts drawn into the
images — Anybody, Atkinson Hyperlegible Next and Martian Mono — are under the SIL Open Font License.

## Repository READMEs

[`tools/readmes.py`](tools/readmes.py) writes the shared header (banner and buttons) and footer
(suite strip) into the README of each checkout beside this one, between
`<!-- magnetar:header -->` and `<!-- magnetar:footer -->` markers, so rerunning it updates them in
place. It edits files only; commit in each repository yourself. A new repository needs an entry
in `REPOS` in `build.py`, and a new app one in `APPS` too.


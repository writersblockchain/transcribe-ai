# Cadence

Turn YouTube podcasts into searchable, timestamped transcripts organized by speaker. Create an account, save conversations, rename speakers, and export transcripts as text.

**Live app:** https://cadence-transcribe-tau.vercel.app



## Visual tests

Storybook renders the production HTML, CSS, and JavaScript with fictional data,
mocked API responses, and bundled fonts. Ten screen states are captured at 390px
and 1280px widths. No real accounts, transcripts, or AssemblyAI requests are used.

```sh
npm ci
npm run storybook                 # http://localhost:6006
npm run build-storybook
npx playwright install chromium  # first-time browser setup
npm run test:visual-fixtures
```

To run Chromatic, add `CHROMATIC_PROJECT_TOKEN` to your ignored `.env`, then run
`npm run chromatic`. The first build establishes baselines; later builds report
visual changes for review. Never commit the token or pass it as a command argument.

For GitHub Actions, add `CHROMATIC_PROJECT_TOKEN` under repository Settings →
Secrets and variables → Actions. The visual-test workflow runs on pull requests
and pushes to `main`. Without the secret (including fork PRs), local fixture checks
and the Storybook build still run, but Chromatic upload is skipped. Changes are
not automatically accepted. Storybook is separate from the production deployment.

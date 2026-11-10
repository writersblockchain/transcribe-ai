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


### Hosted YouTube downloads

Set `YOINKU_API_KEY` in the local `.env` or Railway variables to retrieve audio
through Yoinku instead of downloading directly from YouTube on Railway. AssemblyAI
still performs transcription and speaker diarization. Without this setting, the
app uses yt-dlp, which YouTube may block on cloud IPs.

Yoinku’s documented free allowance is **five downloads per day per account**,
shared by everyone using this app. It also limits requests per minute. No paid
plan or automatic recharge is enabled by this integration. The provider receives
the submitted YouTube URL, while AssemblyAI receives the downloaded audio.

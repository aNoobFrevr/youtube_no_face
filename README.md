# youtube_no_face

Phone-controlled, GitHub Actions-executed faceless short-video pipeline.

## Operating model

The phone is only a remote control. GitHub Actions runs tests, Python, model inference, asset acquisition, ffmpeg rendering, and artifact creation.

## Current milestone

The bootstrap milestone provides:

- red-first contract tests
- deterministic run directories under `runs/<run_id>/`
- ordered, resumable stage orchestration
- failure manifests and artifact preservation
- a GitHub Actions test/smoke workflow
- a Termux controller that only invokes GitHub CLI commands

The current smoke pipeline intentionally produces JSON artifacts rather than a real video. Rendering will be implemented in its own TDD cycle.

## Trigger from Termux

Install only the control-plane tools:

```bash
pkg update
pkg install git gh
termux-setup-storage
gh auth login
```

Clone the repository once:

```bash
git clone git@github.com:aNoobFrevr/youtube_no_face.git
cd youtube_no_face
chmod +x phone/generate.sh
```

After this branch is merged to `main`, trigger and download a run with:

```bash
./phone/generate.sh "Why airplane windows are round"
```

The script calls only:

- `gh workflow run`
- `gh run watch`
- `gh run download`

## TDD policy

Every capability follows red → green → refactor:

1. Commit a failing contract test.
2. Add the smallest implementation that satisfies it.
3. Refactor only while the suite remains green.
4. Never merge a failing state into `main`.

# Version 1.0.0 release preparation

Version `1.0.0` is the initial public release, authorized by the maintainer on 2026-10-18. The live maintainer HA instance remains on the previously deployed development build until explicitly updated.

## Approval gate

Do not create/push tags, publish a repository or create/publish a release without maintainer approval. Local validation and packaging create none of those external changes.

## Before tagging v1.0.0

- Complete the observation period and review docs/VERIFICATION.md, especially actual publication/reconciliation, reauthentication and recovery behavior.
- Run CI, hassfest and HACS validation on the final repository; locally added workflows are not evidence of successful GitHub validation.
- Confirm repository ownership/visibility, private vulnerability reporting and release limitations.
- Review docs/RELEASE_NOTES.md and CHANGELOG.md; approve the tested support scope and remaining gaps explicitly.
- Inspect the archive, run the documented local checks and `python scripts/validate.py --release-tag v1.0.0`.
- Commit the reviewed, secret-free files. No commits or tags are created by packaging.

## After approval

Push the agreed tag only after the repository checks pass. The release workflow validates the version, runs tests/lint/hassfest and creates a **draft** release. Development/alpha/beta/RC tags are marked as prereleases; v1.0.0 is a stable draft. Nothing is automatically published. Inspect the asset/notes, then obtain approval for publication.

The ZIP contains allowlisted integration files at its root plus LICENSE. Development tools, tests, caches, raw account captures and credentials are excluded.

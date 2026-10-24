# Code signing policy

## Current status

The maintainer is applying to the SignPath Foundation open-source signing program.
Approval and a production signing certificate have not yet been granted. Releases
remain unsigned until this page explicitly records approval and the release's
Authenticode signatures verify successfully. A clean antivirus scan is not a
code-signing certificate and does not establish SmartScreen reputation.

Planned service after approval: Free code signing provided by [SignPath.io](https://signpath.io),
certificate by [SignPath Foundation](https://signpath.org).

Committer, reviewer and signing approver: [Roman Ilyin](https://github.com/Rom4nIlyin).
Contributions from other authors require maintainer review. Production signing
requires manual maintainer approval in SignPath. Account MFA is a prerequisite
that the account owner must verify; this repository does not claim to have checked it.

## Scope and integrity

Only binaries compiled from this repository are submitted: AFTERPLAY.exe,
Updater.exe, ProcessAudio.dll and ReplayNotification.dll. Bundled Python, FFmpeg,
Microsoft WebView2 and other third-party binaries are not signed with the project's
certificate. Their original licenses and signatures remain unchanged.

The GitHub-hosted Windows workflow uploads the four unsigned binaries as a GitHub
Actions artifact. SignPath verifies build provenance and returns the signed files.
Every returned file must have a valid Authenticode signature. SHA256SUMS.json and
the portable ZIP are regenerated after signing. Signing failures must stop a build
when signing is enabled; they must never silently produce an unsigned release.

## Configuration after approval

Set repository variable SIGNPATH_ENABLED=true only after the application is approved.
Provide SIGNPATH_ORGANIZATION_ID, SIGNPATH_PROJECT_SLUG and SIGNPATH_SIGNING_POLICY_SLUG
as repository variables, and SIGNPATH_API_TOKEN as a GitHub Actions secret. Do not
put API tokens, certificates or private keys in repository files or chat messages.
The optional SIGNPATH_ARTIFACT_CONFIGURATION_SLUG defaults to the project's
configuration. Import docs/signpath-artifact.xml as the artifact configuration.
Use the production policy requiring manual approval, not a test certificate policy.

A local build can instead use an already-installed trusted code-signing certificate:
set AFTERPLAY_SIGN_THUMBPRINT to its SHA-1 thumbprint in CurrentUser/My before building.
The build signs its own four PE files and verifies all signatures before packaging.
It never creates certificates, adds roots to Windows trust stores or changes Defender.

## Privacy policy

AFTERPLAY keeps recordings, thumbnails, notes and settings on the user's computer.
It does not upload recordings, screen content, application lists or library data.
The local UI server binds only to 127.0.0.1 and uses a per-launch token.
Manual update checks contact GitHub Releases; enabling auto-update explicitly
allows scheduled GitHub checks and release downloads. GitHub receives normal
HTTP connection metadata for those requests. See [GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).
No telemetry or advertising service is included.

Developer signing builds send only the four compiled application binaries and
GitHub build provenance to SignPath. User data is excluded from release artifacts.

## SmartScreen

A Microsoft Defender scan and a SmartScreen reputation check are different.
Even valid new publisher signatures can initially display reputation warnings.
See [Microsoft's explanation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).
The project does not disable SmartScreen or Defender, install self-signed trusted
roots, or promise that a new certificate immediately eliminates every warning.

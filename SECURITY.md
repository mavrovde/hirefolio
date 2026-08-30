# Security Policy

## Supported Versions

Only the latest release line receives security updates. The current version is
tracked in [`VERSION`](./VERSION).

| Version | Supported          |
| ------- | ------------------ |
| 1.8.x   | :white_check_mark: |
| < 1.8   | :x:                |

## Reporting a Vulnerability

Please report vulnerabilities **privately** via GitHub Security Advisories:
open the repository's **Security** tab → **Report a vulnerability**
(<https://github.com/mavrovde/mavrov.de/security/advisories/new>).

Do **not** open a public issue for a security problem, and never include
credentials, tokens, or step-by-step live-exploit instructions in public
issues or pull requests.

What to expect:

- An acknowledgement within a few days (this is a single-maintainer project).
- Triage against the current release; confirmed issues are fixed forward on
  `main` and shipped in the next release.
- Credit in the release notes if you would like it.

Dependency and code-scanning findings (Dependabot, CodeQL) are triaged as part
of every release (see `CLAUDE.md`, engineering rule 8).

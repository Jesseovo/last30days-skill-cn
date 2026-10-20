# Security policy

## Supported versions

Security fixes target the latest release and the `main` branch. Older releases
may require an upgrade to receive a fix.

## Reporting a vulnerability

Please do not publish vulnerability details, exploit code, cookies, API keys,
browser sessions, or other credentials in a public issue or pull request.

If GitHub offers **Report a vulnerability** on this repository's
[Security page](https://github.com/Jesseovo/last30days-skill-cn/security), use it
to send a private report. Private reporting is not currently enabled. Until it
is available, open a [security contact request](https://github.com/Jesseovo/last30days-skill-cn/issues/new?title=Security%20contact%20request)
containing only a request for a private reporting channel. Wait for the
maintainer to arrange a channel before sending sensitive details.

In the private report, include the affected version or commit, the impact,
reproduction steps, and a minimal example with credentials removed. The
maintainer will assess the report and coordinate a fix and disclosure.

## Dependency and automation maintenance

The runtime uses the Python standard library. `jieba` and `playwright` are
optional enhancements, and `requirements.txt` contains only installation notes.
There are no required third-party runtime dependencies to lock.

GitHub Actions are pinned to full commit hashes and tracked by Dependabot.
Pull requests run the existing test suite and a plugin security scan with the
same minimum score of 80 used by the plugin directory. The scanner also runs
on pushes to `main`.

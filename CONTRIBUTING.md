# Contributing

Thanks for your interest. everkeep is a small one-person project, so a few rules keep it manageable.

## Before you open a pull request

- **Open an issue first** for anything bigger than a typo or an obvious bug fix, and wait for a reply. Pull requests for changes nobody asked for (refactors, reformatting, renames, new features) are closed.
- **One concern per pull request**, with a test in `tests/` that fails without your change.
- Run `python -m unittest discover -s tests -t tests` and `python scripts/size_check.py`. Both must pass.
- No new runtime dependencies: the CLI is standard-library Python on purpose.
- A new hosting provider (GitLab, Forgejo, Gitea, Bitbucket, Azure DevOps) starts with the [provider request template](.github/ISSUE_TEMPLATE/provider.md) and follows `ai-docs/plans/providers-roadmap.md`.

## AI-assisted contributions

You may use AI tools. You are the author, and you must be able to explain every line of your change and why it is right. In the pull request, say which parts an AI tool wrote. Pull requests that look generated and unreviewed (code that calls APIs that do not exist, tests mocked so they cannot fail, descriptions that restate the diff, the same change sprayed across many repositories) are closed with a pointer to this section. Repeat cases may be blocked.

## Security problems

See [SECURITY.md](SECURITY.md). Please report anything that gets a merge or close past everkeep's guards privately.

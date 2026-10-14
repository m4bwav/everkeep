"""Remote URL and repo-argument parsing for every provider's forms; unbuilt providers refuse with exit 3."""

import unittest

import helpers  # noqa: F401
from everkeep.providers.base import ProviderNotSupported, RepoId
from everkeep.providers.registry import UnknownHost, get_provider, parse_remote, parse_repo_arg

CASES = [
    # GitHub
    ("https://github.com/m4bwav/chartwright", "github:m4bwav/chartwright"),
    ("https://github.com/m4bwav/chartwright.git", "github:m4bwav/chartwright"),
    ("https://github.com/m4bwav/chartwright/", "github:m4bwav/chartwright"),
    ("git@github.com:m4bwav/chartwright.git", "github:m4bwav/chartwright"),
    ("ssh://git@github.com/m4bwav/chartwright.git", "github:m4bwav/chartwright"),
    ("https://user:token@github.com/m4bwav/x.git", "github:m4bwav/x"),
    # GitLab, nested groups and self-managed with a port
    ("https://gitlab.com/group/sub/project.git", "gitlab:group/sub/project"),
    ("git@gitlab.com:group/sub/deeper/project.git", "gitlab:group/sub/deeper/project"),
    # Bitbucket Cloud with a user prefix
    ("https://someone@bitbucket.org/workspace/repo.git", "bitbucket:workspace/repo"),
    ("git@bitbucket.org:workspace/repo.git", "bitbucket:workspace/repo"),
    # Azure DevOps in all its forms
    ("https://org@dev.azure.com/org/My%20Project/_git/repo", "azure:org/My Project/repo"),
    ("https://dev.azure.com/org/project/_git/repo", "azure:org/project/repo"),
    ("https://org.visualstudio.com/DefaultCollection/project/_git/repo", "azure:org/project/repo"),
    ("https://org.visualstudio.com/project/_git/repo", "azure:org/project/repo"),
    ("git@ssh.dev.azure.com:v3/org/project/repo", "azure:org/project/repo"),
    ("org@vs-ssh.visualstudio.com:v3/org/project/repo", "azure:org/project/repo"),
    # Codeberg
    ("https://codeberg.org/user/repo.git", "codeberg:user/repo"),
    ("git@codeberg.org:user/repo.git", "codeberg:user/repo"),
]


class RemoteParsing(unittest.TestCase):
    def test_table(self):
        for url, want in CASES:
            with self.subTest(url=url):
                self.assertEqual(str(parse_remote(url)), want)

    def test_pinned_self_hosted_hosts_keep_their_host(self):
        hosts = {"git.example.com": "gitea", "ghe.example.com": "github", "gl.example.com": "gitlab"}
        self.assertEqual(str(parse_remote("https://git.example.com/user/repo.git", hosts)), "gitea@git.example.com:user/repo")
        self.assertEqual(str(parse_remote("ssh://git@gl.example.com:2222/a/b/c.git", hosts)), "gitlab@gl.example.com:a/b/c")
        self.assertEqual(parse_remote("git@ghe.example.com:org/repo.git", hosts), RepoId("github", "org/repo", "ghe.example.com"))

    def test_unknown_host_says_how_to_pin_it(self):
        with self.assertRaises(UnknownHost) as e:
            parse_remote("https://git.unknown.example/user/repo.git")
        self.assertIn('"hosts"', str(e.exception))

    def test_repo_arguments(self):
        self.assertEqual(str(parse_repo_arg("github:m4bwav/x")), "github:m4bwav/x")
        self.assertEqual(str(parse_repo_arg("m4bwav/x")), "github:m4bwav/x")
        self.assertEqual(str(parse_repo_arg("x", default_owner="m4bwav")), "github:m4bwav/x")
        self.assertEqual(str(parse_repo_arg("gitea@git.example.com:user/repo")), "gitea@git.example.com:user/repo")
        self.assertEqual(str(parse_repo_arg("git@github.com:m4bwav/x.git")), "github:m4bwav/x")
        self.assertEqual(str(parse_repo_arg("gitlab:group/sub/project")), "gitlab:group/sub/project")

    def test_unbuilt_providers_refuse_with_the_issue_link_and_exit_3(self):
        for rid in ("gitlab:group/project", "codeberg:user/repo", "bitbucket:ws/repo", "azure:o/p/r",
                    "gitea@git.example.com:u/r"):
            with self.subTest(rid=rid):
                with self.assertRaises(ProviderNotSupported) as e:
                    get_provider(parse_repo_arg(rid))
                self.assertEqual(e.exception.exit_code, 3)
                self.assertIn("isn't supported yet", str(e.exception))
                self.assertIn("template=provider.md", str(e.exception))


if __name__ == "__main__":
    unittest.main()

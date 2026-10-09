import httpx

from app.services.github import GitHubClient


def test_issue_fetch():
    def handler(request):
        assert request.url.path == "/repos/example/project/issues/42"
        return httpx.Response(
            200,
            json={
                "title": "Fix it",
                "body": "Details",
                "html_url": "https://github.com/example/project/issues/42",
                "state": "open",
            },
        )

    issue = GitHubClient("token", transport=httpx.MockTransport(handler)).issue(
        "example/project", 42
    )
    assert issue.title == "Fix it"

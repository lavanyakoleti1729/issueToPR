from urllib.parse import quote

import httpx

from app.models.schemas import Issue


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str, transport: httpx.BaseTransport | None = None):
        self.token = token
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
            timeout=30,
            transport=transport,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            raise GitHubError(f"GitHub {response.status_code}: {response.text[:500]}")
        return response.json()

    def issue(self, repository: str, number: int) -> Issue:
        data = self._request("GET", f"/repos/{repository}/issues/{number}")
        if "pull_request" in data:
            raise GitHubError("The requested number is a pull request, not an issue")
        return Issue(
            title=data["title"],
            body=data.get("body") or "",
            html_url=data["html_url"],
            state=data["state"],
        )

    def repository(self, repository: str) -> dict:
        return self._request("GET", f"/repos/{repository}")

    def create_pr(self, repository: str, branch: str, base: str, title: str, body: str) -> str:
        data = self._request(
            "POST",
            f"/repos/{repository}/pulls",
            json={
                "title": title[:255],
                "head": branch,
                "base": base,
                "body": body,
            },
        )
        return data["html_url"]

    def branch_exists(self, repository: str, branch: str) -> bool:
        response = self.client.get(f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}")
        if response.status_code == 404:
            return False
        if response.is_error:
            raise GitHubError(f"GitHub {response.status_code}: {response.text[:500]}")
        return True

"""Q's outbox: a request for Apollo, filed as a GitHub issue for Claude.

"قل لكلاود يضيف..." - you ask Apollo for a feature or a fix, Q writes it up,
and it lands as an issue on Apollo's own repository, where Claude picks it
up. The issue mentions @claude, so if the Claude GitHub app is installed on
the repository it starts on it by itself; if not, it waits there for the
next session.

Needs a GitHub token that can write issues on the repository:

    setx GITHUB_TOKEN "github_pat_..."        (fine-grained: Issues read/write)
    setx APOLLO_REPO "obad-code/apollo"       (optional, this is the default)

The token is read from the environment and sent only to api.github.com.
"""

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger("apollo.github")

API = "https://api.github.com"
DEFAULT_REPO = "obad-code/apollo"
LABEL = "apollo-request"


def settings():
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    repo = (os.environ.get("APOLLO_REPO") or DEFAULT_REPO).strip()
    return {"token": token, "repo": repo} if token else None


def _post(url, payload, token):
    """The one call to GitHub. Tests replace this."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Apollo"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def file_issue(title, body, mention=True):
    """Open the issue. Returns {number, url}. Raises with a sentence if it cannot."""
    found = settings()
    if found is None:
        raise RuntimeError("Q needs a GitHub token to file it (GITHUB_TOKEN).")
    title = " ".join(str(title or "").split())[:120] or "Request from Apollo"
    text = str(body or "").strip()
    if mention:
        text += ("\n\n---\n@claude please build this. Filed by Apollo's Q from a "
                 "voice request; the user's own words are above.")
    try:
        made = _post(f"{API}/repos/{found['repo']}/issues",
                     {"title": title, "body": text, "labels": [LABEL]}, found["token"])
    except urllib.error.HTTPError as e:
        if e.code == 422:            # the label may not exist and cannot be made
            made = _post(f"{API}/repos/{found['repo']}/issues",
                         {"title": title, "body": text}, found["token"])
        elif e.code in (401, 403):
            raise RuntimeError("GitHub refused the token - it needs Issues: write "
                               f"on {found['repo']}.") from e
        else:
            raise RuntimeError(f"GitHub answered {e.code}.") from e
    return {"number": made.get("number"), "url": made.get("html_url", "")}

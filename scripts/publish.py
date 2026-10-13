#!/usr/bin/env python3
"""Publishes the packaged extension as a Gitea release.

Usage: publish.py [--tag vX.Y.Z[-rc.N]] [--wasm PATH] [--out-dir DIR]

Needs ZED_TERRAPHIM_RELEASE_TOKEN (a Gitea token with write:repository on
terraphim/zed-terraphim). GITEA_URL defaults to https://git.terraphim.cloud.

Without --tag, publishes every vX.Y.Z[-rc.N] tag on Gitea that points at
HEAD and matches extension.toml (the terraphim-native runner checks out a
bare commit and passes no ref name to steps). --tag publishes one of those
tags only. Tags are never created here: a tag that is not on Gitea at HEAD
is an error, so a release always describes the commit it was built from.
Rerunning is safe: a release that already has both assets is left alone,
and a release with a partial upload has its assets replaced.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import package  # noqa: E402

REPO = "terraphim/zed-terraphim"
TOKEN_VAR = "ZED_TERRAPHIM_RELEASE_TOKEN"


def release_tags_at(commit, api_tags, version):
    """Release tags for `version` on `commit`: release candidates in order,
    then the final tag."""
    names = {t["name"] for t in api_tags if t.get("commit", {}).get("sha") == commit}
    selected = []
    for name in names:
        try:
            package.check_tag(name, version)
        except package.PackageError:
            continue
        selected.append(name)
    def order(name):
        rc = name.partition("-rc.")[2]
        return (0, int(rc)) if rc else (1, 0)

    return sorted(selected, key=order)


def asset_plan(existing, names):
    """Return (attachment ids to delete, asset names to upload)."""
    present = {a["name"] for a in existing}
    if all(n in present for n in names):
        return [], []
    return [a["id"] for a in existing if a["name"] in names], list(names)


def multipart(field, filename, data):
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    body = head + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


class Gitea:
    def __init__(self, base, token, repo=REPO):
        self.api = f"{base.rstrip('/')}/api/v1/repos/{repo}"
        self.token = token

    def call(self, method, path, body=None, content_type="application/json"):
        if body is not None and content_type == "application/json":
            body = json.dumps(body).encode()
        req = urllib.request.Request(self.api + path, data=body, method=method)
        req.add_header("Authorization", f"token {self.token}")
        req.add_header("Accept", "application/json")
        if body is not None:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as err:
            if err.code == 404 and method == "GET":
                return None
            detail = err.read().decode(errors="replace")[:500]
            raise SystemExit(f"publish.py: {method} {path} failed: HTTP {err.code} {detail}")
        return json.loads(raw) if raw else None

    def tags(self):
        found, page = [], 1
        while True:
            batch = self.call("GET", f"/tags?limit=50&page={page}") or []
            found.extend(batch)
            if len(batch) < 50:
                return found
            page += 1


def git(*args):
    out = subprocess.run(["git", *args], cwd=package.ROOT, check=True, capture_output=True, text=True)
    return out.stdout.strip()


def publish(gitea, tag, result, commit):
    release = gitea.call("GET", f"/releases/tags/{urllib.parse.quote(tag)}")
    if release is None:
        release = gitea.call(
            "POST",
            "/releases",
            {
                "tag_name": tag,
                "target_commitish": commit,
                "name": tag,
                "body": "Zed extension package. Install and verify as described in docs/release.md.",
                "draft": False,
                "prerelease": result.prerelease,
            },
        )
        print(f"created release {tag} (prerelease={result.prerelease})")
    files = [result.tarball, result.sums]
    delete, upload = asset_plan(release.get("assets") or [], [f.name for f in files])
    for attachment in delete:
        gitea.call("DELETE", f"/releases/{release['id']}/assets/{attachment}")
    for path in files:
        if path.name not in upload:
            continue
        body, content_type = multipart("attachment", path.name, path.read_bytes())
        query = urllib.parse.urlencode({"name": path.name})
        gitea.call("POST", f"/releases/{release['id']}/assets?{query}", body, content_type)
        print(f"uploaded {path.name} to {tag}")
    if not upload:
        print(f"release {tag} already has its assets; nothing to do")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="publish this tag instead of the tags at HEAD")
    parser.add_argument("--wasm", type=pathlib.Path, help="use this built wasm instead of building")
    parser.add_argument("--out-dir", type=pathlib.Path, default=package.ROOT / "dist")
    args = parser.parse_args(argv)

    token = os.environ.get(TOKEN_VAR, "").strip()
    if not token:
        print(
            f"publish.py: {TOKEN_VAR} is not set. The native Gitea runner does not pass the job "
            "token to steps; see docs/release.md, 'Release token'.",
            file=sys.stderr,
        )
        return 1
    gitea = Gitea(os.environ.get("GITEA_URL", "https://git.terraphim.cloud"), token)
    version = package.read_version((package.ROOT / "extension.toml").read_text())
    commit = git("rev-parse", "HEAD")
    try:
        if args.tag:
            package.check_tag(args.tag, version)
        tags = release_tags_at(commit, gitea.tags(), version)
        if args.tag:
            tags = [t for t in tags if t == args.tag]
        if not tags:
            wanted = args.tag or f"v{version} or v{version}-rc.N"
            raise package.PackageError(f"no tag {wanted} on Gitea points at {commit}")
        wasm = args.wasm or package.build_wasm(package.ROOT)
        for tag in tags:
            result = package.package(package.ROOT, wasm, args.out_dir, tag)
            publish(gitea, tag, result, commit)
    except package.PackageError as err:
        print(f"publish.py: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

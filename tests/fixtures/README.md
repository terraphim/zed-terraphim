# Provisioning fixtures

`checksums.txt` and `release_assets.json` are captured from the internal Gitea
pre-release `terraphim_lsp-v1.22.0-rc.3` of the release-only repository
`terraphim/terraphim-lsp-releases` (git.terraphim.cloud, tailnet only, public
so no credentials are needed): the release's `checksums.txt`
(`sha256sum -- *` format) and its asset list (`name`, `download_url` = Gitea's
`browser_download_url`, the `releases/download/<tag>/<asset>` scheme the
extension reproduces in `gitea_asset_url`). These files remain an immutable
historical RC3 capture. They are not RC4 checksums or public-install evidence.
The live release gate downloads and verifies the current pin independently.

The original capture used:

```sh
TAG=terraphim_lsp-v1.22.0-rc.3
REPO=https://git.terraphim.cloud/terraphim/terraphim-lsp-releases
curl -sfL "$REPO/releases/download/$TAG/checksums.txt" -o tests/fixtures/checksums.txt
curl -sf "https://git.terraphim.cloud/api/v1/repos/terraphim/terraphim-lsp-releases/releases/tags/$TAG" \
  | jq '[.assets[]|{name:.name,download_url:.browser_download_url}]|sort_by(.name)' \
  > tests/fixtures/release_assets.json
```

`mcp_checksums.txt` and `mcp_release_assets.json` are captured the same way
from the published pre-release `terraphim_mcp_server-v1.21.18-rc.1` of
`terraphim/terraphim-clients` (2026-10-06; macOS and Linux assets only):

```sh
TAG=terraphim_mcp_server-v1.21.18-rc.1
gh release download "$TAG" -R terraphim/terraphim-clients -p checksums.txt -O tests/fixtures/mcp_checksums.txt --clobber
gh api "repos/terraphim/terraphim-clients/releases/tags/$TAG" \
  -q '[.assets[]|{name:.name,download_url:.browser_download_url}]' > tests/fixtures/mcp_release_assets.json
```

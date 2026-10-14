//! Emit the actual provisioner's pinned public LSP download contract for CI.
use std::collections::BTreeSet;
use zed_terraphim::provision::{
    candidate_assets, configured_lsp, Arch, GithubDiscovery, Os, Platform,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let spec = configured_lsp();
    let mut assets = BTreeSet::new();
    for (os, arch) in [
        (Os::Mac, Arch::Aarch64),
        (Os::Mac, Arch::X8664),
        (Os::Linux, Arch::Aarch64),
        (Os::Linux, Arch::X8664),
    ] {
        assets.extend(candidate_assets(&spec, Platform { os, arch })?);
    }
    println!(
        "{}",
        serde_json::json!({
            "repo": spec.repo,
            "tag": spec.tag,
            "checksum_file": spec.checksum_file,
            "assets": assets,
            "public_catalog": cfg!(feature = "public-catalog"),
            "gitea": spec.gitea,
            "path_fallback": spec.path_fallback,
            "github_discovery": match spec.github_discovery {
                GithubDiscovery::ApiListing => "api_listing",
                GithubDiscovery::PinnedChecksums => "pinned_checksums",
            },
        })
    );
    Ok(())
}

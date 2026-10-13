//! Emit the actual provisioner's pinned public LSP download contract for CI.
use std::collections::BTreeSet;
use zed_terraphim::provision::{candidate_assets, Arch, Os, Platform, LSP};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut assets = BTreeSet::new();
    for (os, arch) in [
        (Os::Mac, Arch::Aarch64),
        (Os::Mac, Arch::X8664),
        (Os::Linux, Arch::Aarch64),
        (Os::Linux, Arch::X8664),
    ] {
        assets.extend(candidate_assets(&LSP, Platform { os, arch })?);
    }
    println!(
        "{}",
        serde_json::json!({
            "repo": LSP.repo,
            "tag": LSP.tag,
            "checksum_file": LSP.checksum_file,
            "assets": assets,
        })
    );
    Ok(())
}

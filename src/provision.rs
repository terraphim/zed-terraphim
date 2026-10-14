//! Provisioning of the language-server (and, later, MCP server) binaries.
//!
//! The extension starts a pinned, checksummed release of a Terraphim binary.
//! Every decision lives here as host-free code, so it is unit-tested natively:
//! platform to asset name, checksum-file parsing, versioned directory and
//! marker naming, stale-directory selection, the resolution order (explicit
//! path, verified cache, download, `PATH` fallback, failure) and the
//! user-facing messages. The Zed host calls are reached only through the
//! [`Host`] trait, implemented in `host.rs`.
//!
//! Invariants (see `docs/design/z2-z4-remaining-design.md`):
//!
//! - I1: a download is made executable only after its SHA-256 matches the
//!   entry for exactly that asset name in the release's checksum file.
//! - I2: the version marker is written last; a directory without a valid
//!   marker is never used and is overwritten on the next attempt.
//! - I6: with a verified install present, resolution performs no network
//!   request.
//!
//! Only raw (uncompressed) release assets are supported: the host extracts
//! archives before the extension could hash them.
//!
//! # Release sources
//!
//! The public catalog uses GitHub only for the shared rc.5 pin. Its release
//! must exist and pass anonymous download checks before extension publication.
//! The combined legacy adapter retains its Gitea-first source order, then
//! GitHub and finally `PATH`; a missing internal release falls through to
//! GitHub. Each source is checked against its own `checksums.txt`.
//!
//! The captured rc.3 Gitea fixtures remain historical parser/provisioning
//! evidence. They are not checksums or installation evidence for rc.5.

use sha2::{Digest, Sha256};
use std::fmt;
use std::fs;
use std::io::Read;
use std::path::Path;

/// A pinned release of one binary.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BinarySpec {
    /// GitHub repository, `owner/name` (also the repository path on Gitea).
    pub repo: &'static str,
    /// URL of the internal Gitea repository that holds the release assets
    /// (public on the tailnet, assets only), tried before GitHub; `None` for
    /// binaries published on GitHub only.
    pub gitea: Option<&'static str>,
    /// Release tag the extension is built to start.
    pub tag: &'static str,
    /// Asset name stem and installed file name, e.g. `terraphim-lsp`.
    pub asset_stem: &'static str,
    /// Name of the release's `sha256sum` output file.
    pub checksum_file: &'static str,
    /// Prefix of the versioned install directory `<dir_prefix>-<tag>`.
    pub dir_prefix: &'static str,
    /// Settings key naming the explicit-path override, for messages.
    pub path_setting: &'static str,
    /// Whether the host can look the binary up on `PATH` (language servers
    /// can, context servers have no worktree to ask).
    pub path_fallback: bool,
}

/// The internal Gitea repository (tailnet only, public, release assets only)
/// retained by the combined legacy adapter. The catalog never contacts it.
pub const GITEA_RELEASES: &str = "https://git.terraphim.cloud/terraphim/terraphim-lsp-releases";

/// The `terraphim-lsp` language server from terraphim-ai.
pub const LSP: BinarySpec = BinarySpec {
    repo: "terraphim/terraphim-ai",
    gitea: Some(GITEA_RELEASES),
    tag: "terraphim_lsp-v1.22.0-rc.5",
    asset_stem: "terraphim-lsp",
    checksum_file: "checksums.txt",
    dir_prefix: "terraphim-lsp",
    path_setting: "lsp.terraphim-lsp.binary.path",
    path_fallback: true,
};

/// Select the same release pin for legacy and public catalog installations.
///
/// The public catalog package avoids the private-network Gitea attempt; the
/// existing combined adapter retains its original source order.
pub const fn configured_lsp() -> BinarySpec {
    if cfg!(feature = "public-catalog") {
        BinarySpec { gitea: None, ..LSP }
    } else {
        LSP
    }
}

/// The `terraphim_mcp_server` context server from terraphim-clients.
pub const MCP: BinarySpec = BinarySpec {
    repo: "terraphim/terraphim-clients",
    gitea: None,
    tag: "terraphim_mcp_server-v1.21.18-rc.1",
    asset_stem: "terraphim_mcp_server",
    checksum_file: "checksums.txt",
    dir_prefix: "terraphim_mcp_server",
    path_setting: "context_servers.terraphim.command.path",
    path_fallback: false,
};

/// Name of the file recording a verified install inside its directory.
pub const MARKER_FILE: &str = ".verified";

/// Operating system, as reported by the host.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Os {
    Mac,
    Linux,
    Windows,
}

/// CPU architecture, as reported by the host.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Arch {
    Aarch64,
    X86,
    X8664,
}

/// The platform the extension runs on.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Platform {
    pub os: Os,
    pub arch: Arch,
}

impl fmt::Display for Platform {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let os = match self.os {
            Os::Mac => "macOS",
            Os::Linux => "Linux",
            Os::Windows => "Windows",
        };
        let arch = match self.arch {
            Arch::Aarch64 => "aarch64",
            Arch::X86 => "x86",
            Arch::X8664 => "x86_64",
        };
        write!(f, "{os} {arch}")
    }
}

/// A file attached to a release.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Asset {
    pub name: String,
    pub download_url: String,
}

/// Installation status shown by Zed for the server.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Status {
    None,
    CheckingForUpdate,
    Downloading,
    Failed(String),
}

/// Why provisioning could not produce a verified binary.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProvisionError {
    /// No release asset exists for this platform.
    UnsupportedPlatform { platform: Platform },
    /// The release carries none of the expected assets.
    NoMatchingAsset { candidates: Vec<String> },
    /// The release has no checksum file, or it could not be read.
    ChecksumFileMissing { name: String, detail: String },
    /// A checksum-file line is not `<64 hex>  <name>`.
    ChecksumMalformed { line: usize, reason: &'static str },
    /// The checksum file has no entry for the asset.
    ChecksumEntryMissing { asset: String },
    /// The checksum file lists the asset twice with different hashes.
    ChecksumAmbiguous { asset: String },
    /// The downloaded asset does not match its checksum entry.
    ChecksumMismatch {
        asset: String,
        expected: String,
        actual: String,
    },
    /// A host call or file operation failed.
    Host(String),
    /// The Gitea release and then the GitHub release both failed.
    Sources {
        gitea_base: String,
        gitea: Box<ProvisionError>,
        github: Box<ProvisionError>,
    },
}

impl fmt::Display for ProvisionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnsupportedPlatform { platform } => {
                write!(f, "no prebuilt release for {platform}")
            }
            Self::NoMatchingAsset { candidates } => write!(
                f,
                "the release has none of the expected assets ({})",
                candidates.join(", ")
            ),
            Self::ChecksumFileMissing { name, detail } => {
                write!(f, "checksum file {name} unavailable: {detail}")
            }
            Self::ChecksumMalformed { line, reason } => {
                write!(f, "malformed checksum file, line {line}: {reason}")
            }
            Self::ChecksumEntryMissing { asset } => {
                write!(f, "checksum file has no entry for {asset}")
            }
            Self::ChecksumAmbiguous { asset } => {
                write!(f, "checksum file lists {asset} with conflicting hashes")
            }
            Self::ChecksumMismatch {
                asset,
                expected,
                actual,
            } => write!(
                f,
                "checksum mismatch for {asset}: expected {expected}, downloaded file has {actual}"
            ),
            Self::Host(detail) => f.write_str(detail),
            Self::Sources {
                gitea_base,
                gitea,
                github,
            } => write!(f, "Gitea ({gitea_base}): {gitea}; GitHub: {github}"),
        }
    }
}

impl std::error::Error for ProvisionError {}

// ---------------------------------------------------------------------------
// Pure decisions
// ---------------------------------------------------------------------------

/// Release asset names for `platform`, most preferred first.
///
/// macOS prefers the universal binary, then the per-architecture one
/// (signing is release-dependent; verify the selected release manifest);
/// Linux prefers glibc on x86_64 and musl elsewhere. Windows is deferred
/// (issue #16) and reported as unsupported.
pub fn candidate_assets(
    spec: &BinarySpec,
    platform: Platform,
) -> Result<Vec<String>, ProvisionError> {
    let stem = spec.asset_stem;
    let targets: &[&str] = match (platform.os, platform.arch) {
        (Os::Mac, Arch::Aarch64) => &["universal-apple-darwin", "aarch64-apple-darwin"],
        (Os::Mac, Arch::X8664) => &["universal-apple-darwin", "x86_64-apple-darwin"],
        (Os::Linux, Arch::X8664) => &["x86_64-unknown-linux-gnu", "x86_64-unknown-linux-musl"],
        (Os::Linux, Arch::Aarch64) => &["aarch64-unknown-linux-musl"],
        _ => return Err(ProvisionError::UnsupportedPlatform { platform }),
    };
    Ok(targets
        .iter()
        .map(|target| format!("{stem}-{target}"))
        .collect())
}

/// Download URL of `name` on the Gitea release `tag` of the release
/// repository `repo_url`; the same `browser_download_url` the Gitea API
/// reports.
pub fn gitea_asset_url(repo_url: &str, tag: &str, name: &str) -> String {
    format!(
        "{}/releases/download/{tag}/{name}",
        repo_url.trim_end_matches('/')
    )
}

/// The assets to try on the Gitea release: the platform's candidates, then
/// the checksum file. Which of them exist is learnt from the checksum file,
/// not from an API listing.
pub fn gitea_release(spec: &BinarySpec, platform: Platform) -> Result<Vec<Asset>, ProvisionError> {
    let base = spec
        .gitea
        .ok_or_else(|| ProvisionError::Host("no Gitea source for this binary".to_string()))?;
    let mut names = candidate_assets(spec, platform)?;
    names.push(spec.checksum_file.to_string());
    Ok(names
        .into_iter()
        .map(|name| Asset {
            download_url: gitea_asset_url(base, spec.tag, &name),
            name,
        })
        .collect())
}

/// The first candidate present in the release's asset list.
pub fn pick_asset<'a>(
    candidates: &[String],
    assets: &'a [Asset],
) -> Result<&'a Asset, ProvisionError> {
    candidates
        .iter()
        .find_map(|candidate| assets.iter().find(|asset| &asset.name == candidate))
        .ok_or_else(|| ProvisionError::NoMatchingAsset {
            candidates: candidates.to_vec(),
        })
}

fn is_sha256_hex(text: &str) -> bool {
    text.len() == 64 && text.bytes().all(|byte| byte.is_ascii_hexdigit())
}

/// Parses `sha256sum` output into `(lowercase hash, name)` pairs.
///
/// Lines are `<64 hex><two spaces><name>`; the `*name` binary marker and CRLF
/// line endings are tolerated and blank lines skipped. Any other line is an
/// error, so a damaged file fails closed instead of being half-trusted.
pub fn parse_checksums(text: &str) -> Result<Vec<(String, String)>, ProvisionError> {
    let mut entries = Vec::new();
    for (index, raw) in text.lines().enumerate() {
        let line = raw.trim_end_matches('\r');
        if line.trim().is_empty() {
            continue;
        }
        let number = index + 1;
        let malformed = |reason| ProvisionError::ChecksumMalformed {
            line: number,
            reason,
        };
        let Some((hash, rest)) = line.split_at_checked(64) else {
            return Err(malformed("line shorter than a SHA-256 digest"));
        };
        if !is_sha256_hex(hash) {
            return Err(malformed("digest is not 64 hexadecimal characters"));
        }
        let name = rest
            .strip_prefix("  ")
            .or_else(|| rest.strip_prefix(" *"))
            .ok_or_else(|| malformed("digest not followed by two spaces and a name"))?;
        if name.is_empty() {
            return Err(malformed("missing file name"));
        }
        entries.push((hash.to_ascii_lowercase(), name.to_string()));
    }
    Ok(entries)
}

/// The expected SHA-256 for exactly `asset` (never a prefix or suffix match).
pub fn lookup_checksum(text: &str, asset: &str) -> Result<String, ProvisionError> {
    let entries = parse_checksums(text)?;
    let mut hashes = entries
        .iter()
        .filter(|(_, name)| name == asset)
        .map(|(hash, _)| hash);
    let first = hashes
        .next()
        .ok_or_else(|| ProvisionError::ChecksumEntryMissing {
            asset: asset.to_string(),
        })?;
    if hashes.any(|other| other != first) {
        return Err(ProvisionError::ChecksumAmbiguous {
            asset: asset.to_string(),
        });
    }
    Ok(first.clone())
}

/// Lowercase hexadecimal encoding.
pub fn hex_encode(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(DIGITS[usize::from(byte >> 4)] as char);
        out.push(DIGITS[usize::from(byte & 0x0f)] as char);
    }
    out
}

/// SHA-256 of a file, read in chunks.
pub fn sha256_file(path: &Path) -> std::io::Result<String> {
    let mut file = fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(hex_encode(&hasher.finalize()))
}

/// Versioned install directory, relative to the extension work directory.
pub fn install_dir(spec: &BinarySpec) -> String {
    format!("{}-{}", spec.dir_prefix, spec.tag)
}

/// Path of the installed binary, relative to the extension work directory.
pub fn binary_path(spec: &BinarySpec) -> String {
    format!("{}/{}", install_dir(spec), spec.asset_stem)
}

/// Marker contents recording what was verified.
pub fn marker_content(spec: &BinarySpec, asset: &str, sha256: &str) -> String {
    format!("tag={}\nasset={asset}\nsha256={sha256}\n", spec.tag)
}

/// The fields of a marker file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Marker<'a> {
    pub tag: &'a str,
    pub asset: &'a str,
    pub sha256: &'a str,
}

/// Parses a marker; `None` when a field is missing, empty or malformed.
pub fn parse_marker(content: &str) -> Option<Marker<'_>> {
    let field = |key: &str| {
        content
            .lines()
            .find_map(|line| line.strip_prefix(key)?.strip_prefix('='))
    };
    let marker = Marker {
        tag: field("tag")?,
        asset: field("asset")?,
        sha256: field("sha256")?,
    };
    (!marker.asset.is_empty() && is_sha256_hex(marker.sha256)).then_some(marker)
}

/// Whether `content` is a marker for exactly the pinned tag with a digest.
pub fn marker_is_valid(spec: &BinarySpec, content: &str) -> bool {
    parse_marker(content).is_some_and(|marker| marker.tag == spec.tag)
}

/// Whether the install on disk is trustworthy: the marker names the pinned
/// tag and an asset valid for this platform, and the binary's SHA-256 still
/// equals the recorded digest. Local hashing only, so no network (I6).
pub fn cached_install_is_verified(
    spec: &BinarySpec,
    platform: Platform,
    root: &Path,
    marker: Option<&str>,
) -> bool {
    let Some(marker) = marker.and_then(parse_marker) else {
        return false;
    };
    if marker.tag != spec.tag {
        return false;
    }
    let Ok(candidates) = candidate_assets(spec, platform) else {
        return false;
    };
    if !candidates.iter().any(|name| name == marker.asset) {
        return false;
    }
    let path = root.join(binary_path(spec));
    path.is_file() && sha256_file(&path).is_ok_and(|actual| actual == marker.sha256)
}

/// Directories to delete: same prefix, different tag. Every other name,
/// including the current install and the bare prefix, is left alone.
pub fn stale_dirs(spec: &BinarySpec, existing: &[String]) -> Vec<String> {
    let current = install_dir(spec);
    let prefix = format!("{}-", spec.dir_prefix);
    existing
        .iter()
        .filter(|name| **name != current)
        .filter(|name| {
            name.strip_prefix(&prefix)
                .is_some_and(|rest| !rest.is_empty())
        })
        .cloned()
        .collect()
}

/// What to do before touching the network.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Plan {
    /// Use the user's explicit path; no network, no install.
    Override(String),
    /// Use the verified install already on disk.
    Cached(String),
    /// Download, verify and install the pinned release.
    Download,
}

/// Resolution order: explicit path, verified cache, download.
///
/// `cache_verified` is the result of [`cached_install_is_verified`].
pub fn decide(spec: &BinarySpec, setting_path: Option<&str>, cache_verified: bool) -> Plan {
    if let Some(path) = setting_path.map(str::trim).filter(|path| !path.is_empty()) {
        return Plan::Override(path.to_string());
    }
    if cache_verified {
        return Plan::Cached(binary_path(spec));
    }
    Plan::Download
}

/// Final failure message: what failed, for which asset and platform, and
/// the remedies (the path setting, and `PATH` where the host can search it).
pub fn failure_message(spec: &BinarySpec, platform: Platform, error: &ProvisionError) -> String {
    let remedy = if spec.path_fallback {
        format!(", or put {} on your PATH", spec.asset_stem)
    } else {
        String::new()
    };
    format!(
        "{stem}: could not install {tag} for {platform}: {error}. Set \"{setting}\" to an \
         absolute path of a {stem} binary{remedy}",
        stem = spec.asset_stem,
        tag = spec.tag,
        setting = spec.path_setting,
    )
}

/// Status text when provisioning failed but a `PATH` binary is used.
pub fn path_fallback_message(
    spec: &BinarySpec,
    platform: Platform,
    error: &ProvisionError,
    path: &str,
) -> String {
    format!(
        "{stem}: could not install {tag} for {platform}: {error}. Using {path} from PATH instead",
        stem = spec.asset_stem,
        tag = spec.tag,
    )
}

// ---------------------------------------------------------------------------
// Orchestration over the host
// ---------------------------------------------------------------------------

/// The Zed host operations provisioning needs. Paths are relative to the
/// extension work directory.
pub trait Host {
    /// Assets of the release `tag` in `repo`.
    fn release_assets(&mut self, repo: &str, tag: &str) -> Result<Vec<Asset>, String>;
    /// Downloads `url` to `path` without extraction.
    fn download(&mut self, url: &str, path: &str) -> Result<(), String>;
    /// Marks the file executable.
    fn make_executable(&mut self, path: &str) -> Result<(), String>;
    /// Shows `status` for the server.
    fn set_status(&mut self, status: Status);
    /// Looks `name` up on the worktree's `PATH`.
    fn which(&self, name: &str) -> Option<String>;
}

/// Resolves the command to start for `spec`.
///
/// `root` is the extension work directory; returned paths are relative to
/// it (or the user's explicit path). Order: explicit `setting_path`, a
/// verified install of the pinned tag, a fresh verified install, a `PATH`
/// binary (reported through the status), else an error naming both remedies.
pub fn resolve(
    spec: &BinarySpec,
    platform: Platform,
    setting_path: Option<&str>,
    root: &Path,
    host: &mut impl Host,
) -> Result<String, String> {
    // An explicit path wins before anything is read from disk.
    let cache_verified = setting_path.is_none_or(|path| path.trim().is_empty()) && {
        let marker = fs::read_to_string(root.join(install_dir(spec)).join(MARKER_FILE)).ok();
        cached_install_is_verified(spec, platform, root, marker.as_deref())
    };
    match decide(spec, setting_path, cache_verified) {
        Plan::Override(path) => return Ok(path),
        Plan::Cached(path) => {
            remove_stale(spec, root);
            return Ok(path);
        }
        Plan::Download => {}
    }

    host.set_status(Status::CheckingForUpdate);
    match install_from_sources(spec, platform, root, host) {
        Ok(path) => {
            host.set_status(Status::None);
            remove_stale(spec, root);
            Ok(path)
        }
        Err(error) => {
            // Leave nothing executable or half-written behind (I2).
            let _ = fs::remove_dir_all(root.join(install_dir(spec)));
            match host.which(spec.asset_stem).filter(|p| !p.trim().is_empty()) {
                Some(path) => {
                    host.set_status(Status::Failed(path_fallback_message(
                        spec, platform, &error, &path,
                    )));
                    Ok(path)
                }
                None => {
                    let message = failure_message(spec, platform, &error);
                    host.set_status(Status::Failed(message.clone()));
                    Err(message)
                }
            }
        }
    }
}

/// Where the asset list of a release comes from, and so how the asset is
/// chosen.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Pick {
    /// The host listed the release: the first candidate attached to it.
    Listed,
    /// Nothing was listed: the first candidate the checksum file has an
    /// entry for.
    ByChecksums,
}

/// Installs from the Gitea release, then the GitHub release.
fn install_from_sources(
    spec: &BinarySpec,
    platform: Platform,
    root: &Path,
    host: &mut impl Host,
) -> Result<String, ProvisionError> {
    // An unsupported platform fails before any request.
    candidate_assets(spec, platform)?;
    let mut announced = false;
    let Some(base) = spec.gitea else {
        return install_listed(spec, platform, root, host, &mut announced);
    };
    let from_gitea = gitea_release(spec, platform).and_then(|assets| {
        install(
            spec,
            platform,
            root,
            host,
            assets,
            Pick::ByChecksums,
            &mut announced,
        )
    });
    let gitea = match from_gitea {
        Ok(path) => return Ok(path),
        Err(error) => error,
    };
    install_listed(spec, platform, root, host, &mut announced).map_err(|github| {
        ProvisionError::Sources {
            gitea_base: base.to_string(),
            gitea: Box::new(gitea),
            github: Box::new(github),
        }
    })
}

/// Installs from the GitHub release the host lists.
fn install_listed(
    spec: &BinarySpec,
    platform: Platform,
    root: &Path,
    host: &mut impl Host,
    announced: &mut bool,
) -> Result<String, ProvisionError> {
    let assets = host
        .release_assets(spec.repo, spec.tag)
        .map_err(ProvisionError::Host)?;
    install(spec, platform, root, host, assets, Pick::Listed, announced)
}

/// Downloads, verifies and installs the pinned release from `assets`;
/// returns the binary path relative to `root`. The marker is written last
/// (I2). `announced` makes the "downloading" status appear once per
/// resolution, not once per source.
fn install(
    spec: &BinarySpec,
    platform: Platform,
    root: &Path,
    host: &mut impl Host,
    assets: Vec<Asset>,
    pick: Pick,
    announced: &mut bool,
) -> Result<String, ProvisionError> {
    let candidates = candidate_assets(spec, platform)?;
    let listed = match pick {
        Pick::Listed => Some(pick_asset(&candidates, &assets)?),
        Pick::ByChecksums => None,
    };
    let checksum_asset = assets
        .iter()
        .find(|candidate| candidate.name == spec.checksum_file)
        .ok_or_else(|| ProvisionError::ChecksumFileMissing {
            name: spec.checksum_file.to_string(),
            detail: "not attached to the release".to_string(),
        })?;

    let dir = install_dir(spec);
    let dir_path = root.join(&dir);
    // A directory without a valid marker is never used: start clean.
    let _ = fs::remove_dir_all(&dir_path);
    fs::create_dir_all(&dir_path)
        .map_err(|error| ProvisionError::Host(format!("cannot create {dir}: {error}")))?;

    if !*announced {
        host.set_status(Status::Downloading);
        *announced = true;
    }

    // The small checksum file first, so a bad release fails before the
    // large download.
    let checksum_rel = format!("{dir}/{}", spec.checksum_file);
    host.download(&checksum_asset.download_url, &checksum_rel)
        .map_err(|detail| ProvisionError::ChecksumFileMissing {
            name: spec.checksum_file.to_string(),
            detail,
        })?;
    let checksum_text = fs::read_to_string(root.join(&checksum_rel)).map_err(|error| {
        ProvisionError::ChecksumFileMissing {
            name: spec.checksum_file.to_string(),
            detail: error.to_string(),
        }
    })?;
    let (asset, expected) = match listed {
        Some(asset) => (asset, lookup_checksum(&checksum_text, &asset.name)?),
        None => {
            // Only a missing entry moves on to the next candidate; every
            // other checksum error (a malformed file, conflicting entries)
            // fails closed rather than installing a lower-priority asset.
            let mut chosen = None;
            for name in &candidates {
                match lookup_checksum(&checksum_text, name) {
                    Ok(expected) => {
                        let asset =
                            assets
                                .iter()
                                .find(|asset| &asset.name == name)
                                .ok_or_else(|| ProvisionError::NoMatchingAsset {
                                    candidates: candidates.clone(),
                                })?;
                        chosen = Some((asset, expected));
                        break;
                    }
                    // No listing exists on Gitea, so `checksums.txt` is the
                    // listing: like `pick_asset` on a GitHub release, the first
                    // candidate present wins. Whichever is chosen is verified
                    // against its own entry before it is installed.
                    Err(ProvisionError::ChecksumEntryMissing { .. }) => continue,
                    Err(error) => return Err(error),
                }
            }
            chosen.ok_or_else(|| ProvisionError::NoMatchingAsset {
                candidates: candidates.clone(),
            })?
        }
    };

    let temporary_rel = format!("{dir}/{}.download", asset.name);
    host.download(&asset.download_url, &temporary_rel)
        .map_err(|detail| {
            ProvisionError::Host(format!("download of {} failed: {detail}", asset.name))
        })?;
    let actual = sha256_file(&root.join(&temporary_rel)).map_err(|error| {
        ProvisionError::Host(format!("cannot read downloaded {}: {error}", asset.name))
    })?;
    if actual != expected {
        return Err(ProvisionError::ChecksumMismatch {
            asset: asset.name.clone(),
            expected,
            actual,
        });
    }

    let final_rel = binary_path(spec);
    fs::rename(root.join(&temporary_rel), root.join(&final_rel))
        .map_err(|error| ProvisionError::Host(format!("cannot install {}: {error}", asset.name)))?;
    host.make_executable(&final_rel).map_err(|detail| {
        ProvisionError::Host(format!("cannot make {final_rel} executable: {detail}"))
    })?;
    let _ = fs::remove_file(root.join(&checksum_rel));
    fs::write(
        dir_path.join(MARKER_FILE),
        marker_content(spec, &asset.name, &actual),
    )
    .map_err(|error| ProvisionError::Host(format!("cannot write install marker: {error}")))?;
    Ok(final_rel)
}

/// Best-effort removal of directories from other pinned versions.
fn remove_stale(spec: &BinarySpec, root: &Path) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    let directories: Vec<String> = entries
        .flatten()
        .filter(|entry| entry.file_type().is_ok_and(|kind| kind.is_dir()))
        .filter_map(|entry| entry.file_name().into_string().ok())
        .collect();
    for name in stale_dirs(spec, &directories) {
        let _ = fs::remove_dir_all(root.join(name));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicUsize, Ordering};

    const CHECKSUMS: &str = include_str!("../tests/fixtures/checksums.txt");
    const ASSETS_JSON: &str = include_str!("../tests/fixtures/release_assets.json");
    // Immutable historical fixture identity, not the current release pin.
    const HISTORICAL_RC3: BinarySpec = BinarySpec {
        tag: "terraphim_lsp-v1.22.0-rc.3",
        ..LSP
    };

    /// `LSP` without the Gitea source: the GitHub-only flow.
    const GH: BinarySpec = BinarySpec { gitea: None, ..LSP };

    const MAC_ARM: Platform = Platform {
        os: Os::Mac,
        arch: Arch::Aarch64,
    };
    const LINUX_X64: Platform = Platform {
        os: Os::Linux,
        arch: Arch::X8664,
    };
    const LINUX_ARM: Platform = Platform {
        os: Os::Linux,
        arch: Arch::Aarch64,
    };
    const WINDOWS_X64: Platform = Platform {
        os: Os::Windows,
        arch: Arch::X8664,
    };
    const WINDOWS_ARM: Platform = Platform {
        os: Os::Windows,
        arch: Arch::Aarch64,
    };

    fn fixture_assets() -> Vec<Asset> {
        let value: serde_json::Value = serde_json::from_str(ASSETS_JSON).unwrap();
        value
            .as_array()
            .unwrap()
            .iter()
            .map(|asset| Asset {
                name: asset["name"].as_str().unwrap().to_string(),
                download_url: asset["download_url"].as_str().unwrap().to_string(),
            })
            .collect()
    }

    fn names(list: &[&str]) -> Vec<String> {
        list.iter().map(|name| name.to_string()).collect()
    }

    // --- platform mapping (AC6) -------------------------------------------

    #[test]
    fn candidates_per_platform() {
        assert_eq!(
            candidate_assets(&LSP, MAC_ARM).unwrap(),
            names(&[
                "terraphim-lsp-universal-apple-darwin",
                "terraphim-lsp-aarch64-apple-darwin"
            ])
        );
        let mac_intel = Platform {
            os: Os::Mac,
            arch: Arch::X8664,
        };
        assert_eq!(
            candidate_assets(&LSP, mac_intel).unwrap(),
            names(&[
                "terraphim-lsp-universal-apple-darwin",
                "terraphim-lsp-x86_64-apple-darwin"
            ])
        );
        assert_eq!(
            candidate_assets(&LSP, LINUX_X64).unwrap(),
            names(&[
                "terraphim-lsp-x86_64-unknown-linux-gnu",
                "terraphim-lsp-x86_64-unknown-linux-musl"
            ])
        );
        assert_eq!(
            candidate_assets(&LSP, LINUX_ARM).unwrap(),
            names(&["terraphim-lsp-aarch64-unknown-linux-musl"])
        );
    }

    #[test]
    fn unsupported_platforms_are_errors() {
        for platform in [
            WINDOWS_X64,
            WINDOWS_ARM,
            Platform {
                os: Os::Linux,
                arch: Arch::X86,
            },
            Platform {
                os: Os::Mac,
                arch: Arch::X86,
            },
        ] {
            assert_eq!(
                candidate_assets(&LSP, platform),
                Err(ProvisionError::UnsupportedPlatform { platform })
            );
        }
    }

    #[test]
    fn candidate_names_follow_the_spec_stem() {
        let mcp = BinarySpec {
            asset_stem: "terraphim_mcp_server",
            ..LSP
        };
        assert_eq!(
            candidate_assets(&mcp, LINUX_ARM).unwrap(),
            names(&["terraphim_mcp_server-aarch64-unknown-linux-musl"])
        );
        assert_eq!(
            binary_path(&mcp),
            "terraphim-lsp-terraphim_lsp-v1.22.0-rc.5/terraphim_mcp_server"
        );
    }

    #[test]
    fn pick_asset_prefers_universal_then_falls_back() {
        let assets = fixture_assets();
        let candidates = candidate_assets(&LSP, MAC_ARM).unwrap();
        assert_eq!(
            pick_asset(&candidates, &assets).unwrap().name,
            "terraphim-lsp-universal-apple-darwin"
        );
        let without_universal: Vec<Asset> = assets
            .into_iter()
            .filter(|asset| !asset.name.contains("universal"))
            .collect();
        assert_eq!(
            pick_asset(&candidates, &without_universal).unwrap().name,
            "terraphim-lsp-aarch64-apple-darwin"
        );
    }

    #[test]
    fn pick_asset_reports_candidates_when_none_match() {
        let candidates = candidate_assets(&LSP, LINUX_ARM).unwrap();
        let only_x64: Vec<Asset> = fixture_assets()
            .into_iter()
            .filter(|asset| asset.name.contains("x86_64"))
            .collect();
        let error = pick_asset(&candidates, &only_x64).unwrap_err();
        assert!(error.to_string().contains("aarch64-unknown-linux-musl"));
    }

    // --- checksum parsing (AC2) -------------------------------------------

    #[test]
    fn fixture_checksums_resolve_every_platform_asset() {
        let assets = fixture_assets();
        for platform in [MAC_ARM, LINUX_X64, LINUX_ARM] {
            let candidates = candidate_assets(&LSP, platform).unwrap();
            let asset = pick_asset(&candidates, &assets).unwrap();
            let hash = lookup_checksum(CHECKSUMS, &asset.name).unwrap();
            assert!(is_sha256_hex(&hash), "{hash}");
        }
    }

    /// Preserve the real historical capture without re-labelling it as rc.5.
    #[test]
    fn fixture_is_the_historical_rc3_release() {
        assert_eq!(HISTORICAL_RC3.tag, "terraphim_lsp-v1.22.0-rc.3");
        assert_ne!(HISTORICAL_RC3.tag, LSP.tag);
        let assets = fixture_assets();
        let candidates = candidate_assets(&HISTORICAL_RC3, MAC_ARM).unwrap();
        let asset = pick_asset(&candidates, &assets).unwrap();
        assert_eq!(asset.name, "terraphim-lsp-universal-apple-darwin");
        assert!(asset.download_url.starts_with(
            "https://git.terraphim.cloud/terraphim/terraphim-lsp-releases/releases/download/terraphim_lsp-v1.22.0-rc.3/"
        ));
        assert_eq!(
            lookup_checksum(CHECKSUMS, &asset.name).unwrap(),
            "e3488ea18e9c9502c243c57fd6feb90e4f06b8e4d63767e349def479ae4b652d"
        );
    }

    #[test]
    fn lookup_is_exact_not_prefix_or_suffix() {
        let text = format!(
            "{}  terraphim-lsp-x86_64-unknown-linux-gnu.sig\n",
            "a".repeat(64)
        );
        assert_eq!(
            lookup_checksum(&text, "terraphim-lsp-x86_64-unknown-linux-gnu"),
            Err(ProvisionError::ChecksumEntryMissing {
                asset: "terraphim-lsp-x86_64-unknown-linux-gnu".into()
            })
        );
        assert_eq!(
            lookup_checksum(&text, "gnu.sig"),
            Err(ProvisionError::ChecksumEntryMissing {
                asset: "gnu.sig".into()
            })
        );
    }

    #[test]
    fn missing_entry_is_an_error() {
        assert_eq!(
            lookup_checksum(CHECKSUMS, "terraphim-lsp-riscv64"),
            Err(ProvisionError::ChecksumEntryMissing {
                asset: "terraphim-lsp-riscv64".into()
            })
        );
    }

    #[test]
    fn crlf_binary_marker_and_uppercase_are_tolerated() {
        let upper = "ABCDEF0123456789".repeat(4);
        let text = format!("{upper} *tool-a\r\n\r\n{}  tool-b\r\n", "0".repeat(64));
        assert_eq!(
            lookup_checksum(&text, "tool-a").unwrap(),
            upper.to_ascii_lowercase()
        );
        assert_eq!(lookup_checksum(&text, "tool-b").unwrap(), "0".repeat(64));
    }

    #[test]
    fn malformed_lines_are_rejected_with_their_number() {
        let good = format!("{}  ok", "1".repeat(64));
        let cases: [(&str, &str); 6] = [
            ("short", "shorter than"),
            (&format!("{} x", "1".repeat(64)), "two spaces"),
            (&format!("{}  ", "1".repeat(64)), "file name"),
            (&format!("{}  name", "g".repeat(64)), "hexadecimal"),
            (&format!("{}name", "1".repeat(64)), "two spaces"),
            (&format!("{}   ", "1".repeat(63)), "hexadecimal"),
        ];
        for (bad, reason) in cases {
            let text = format!("{good}\n{bad}\n");
            let error = lookup_checksum(&text, "ok").unwrap_err();
            match error {
                ProvisionError::ChecksumMalformed { line, .. } => assert_eq!(line, 2, "{bad}"),
                other => panic!("{bad}: unexpected {other:?}"),
            }
            assert!(error.to_string().contains(reason), "{bad}: {error}");
        }
    }

    #[test]
    fn multibyte_garbage_does_not_panic() {
        let text = "é".repeat(40);
        assert!(matches!(
            parse_checksums(&text),
            Err(ProvisionError::ChecksumMalformed { line: 1, .. })
        ));
    }

    #[test]
    fn empty_file_has_no_entries() {
        assert_eq!(
            lookup_checksum("", "x"),
            Err(ProvisionError::ChecksumEntryMissing { asset: "x".into() })
        );
    }

    #[test]
    fn conflicting_duplicates_are_ambiguous_identical_ones_are_fine() {
        let text = format!("{0}  a\n{1}  a\n", "1".repeat(64), "2".repeat(64));
        assert_eq!(
            lookup_checksum(&text, "a"),
            Err(ProvisionError::ChecksumAmbiguous { asset: "a".into() })
        );
        let same = format!("{0}  a\n{0}  a\n", "1".repeat(64));
        assert_eq!(lookup_checksum(&same, "a").unwrap(), "1".repeat(64));
    }

    #[test]
    fn hex_encoding_and_sha256_known_answer() {
        assert_eq!(hex_encode(&[0x00, 0x0f, 0xa5, 0xff]), "000fa5ff");
        // SHA-256 of the empty input.
        assert_eq!(
            hex_encode(&Sha256::digest(b"")),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    // --- naming, marker, cleanup (AC4) ------------------------------------

    #[test]
    fn install_layout_is_versioned() {
        assert_eq!(
            install_dir(&LSP),
            "terraphim-lsp-terraphim_lsp-v1.22.0-rc.5"
        );
        assert_eq!(
            binary_path(&LSP),
            "terraphim-lsp-terraphim_lsp-v1.22.0-rc.5/terraphim-lsp"
        );
    }

    #[test]
    fn marker_round_trips_and_checks_the_tag() {
        let sha = "ab".repeat(32);
        let content = marker_content(&LSP, "terraphim-lsp-x", &sha);
        assert!(marker_is_valid(&LSP, &content));
        let other_tag = BinarySpec {
            tag: "terraphim_lsp-v9.9.9",
            ..LSP
        };
        assert!(!marker_is_valid(&other_tag, &content));
    }

    #[test]
    fn damaged_markers_are_invalid() {
        let sha = "ab".repeat(32);
        for content in [
            String::new(),
            "garbage".to_string(),
            format!("tag={}\n", LSP.tag),
            format!("tag={}\nasset=a\nsha256=short\n", LSP.tag),
            format!("tag={}x\nasset=a\nsha256={sha}\n", LSP.tag),
            format!("tag={}\nasset=\nsha256={sha}\n", LSP.tag),
        ] {
            assert!(!marker_is_valid(&LSP, &content), "{content:?}");
        }
    }

    #[test]
    fn stale_selection_never_touches_unrelated_names() {
        let current = install_dir(&LSP);
        let existing = names(&[
            &current,
            "terraphim-lsp-terraphim_lsp-v1.21.0",
            "terraphim-lsp-v0.1.0",
            "terraphim-lsp",
            "terraphim-lsp-",
            "terraphim_mcp_server-terraphim_mcp_server-v1.0.0",
            "grammars",
            "other-terraphim-lsp-v1",
            "work",
        ]);
        assert_eq!(
            stale_dirs(&LSP, &existing),
            names(&[
                "terraphim-lsp-terraphim_lsp-v1.21.0",
                "terraphim-lsp-v0.1.0"
            ])
        );
        assert!(stale_dirs(&LSP, &[]).is_empty());
    }

    // --- decision table (AC5, I2) -----------------------------------------

    #[test]
    fn override_beats_everything() {
        assert_eq!(
            decide(&LSP, Some("/opt/lsp"), true),
            Plan::Override("/opt/lsp".into())
        );
        assert_eq!(
            decide(&LSP, Some("  /opt/lsp \n"), false),
            Plan::Override("/opt/lsp".into())
        );
    }

    #[test]
    fn blank_override_is_ignored() {
        for setting in [None, Some(""), Some("   ")] {
            assert_eq!(decide(&LSP, setting, false), Plan::Download);
        }
    }

    #[test]
    fn verified_install_is_cached() {
        assert_eq!(decide(&LSP, None, true), Plan::Cached(binary_path(&LSP)));
    }

    fn install_fresh(dir: &TempDir) {
        let mut host = FakeHost::serving(&GH, &dir.0);
        resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap();
    }

    fn marker_text(dir: &TempDir) -> String {
        fs::read_to_string(marker_path(&dir.0)).unwrap()
    }

    fn verified(dir: &TempDir, spec: &BinarySpec, platform: Platform) -> bool {
        let marker = fs::read_to_string(dir.0.join(install_dir(spec)).join(MARKER_FILE)).ok();
        cached_install_is_verified(spec, platform, &dir.0, marker.as_deref())
    }

    #[test]
    fn cache_is_verified_only_when_marker_platform_and_hash_agree() {
        let dir = TempDir::new();
        install_fresh(&dir);
        assert!(verified(&dir, &LSP, LINUX_X64));
        // a marker for another platform's asset is not accepted
        assert!(!verified(&dir, &LSP, LINUX_ARM));
        assert!(!verified(&dir, &LSP, MAC_ARM));
        // wrong tag
        let other = BinarySpec {
            tag: "terraphim_lsp-v2",
            ..LSP
        };
        assert!(!verified(&dir, &other, LINUX_X64));
    }

    #[test]
    fn tampered_cached_binary_is_not_trusted_and_is_reinstalled() {
        let dir = TempDir::new();
        install_fresh(&dir);
        let binary = dir.0.join(binary_path(&LSP));
        fs::write(&binary, b"evil").unwrap();
        assert!(!verified(&dir, &LSP, LINUX_X64));

        let mut host = FakeHost::serving(&GH, &dir.0);
        resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(host.downloads.len(), 2, "reinstalled from the release");
        assert_eq!(
            fs::read(&binary).unwrap(),
            b"binary:terraphim-lsp-x86_64-unknown-linux-gnu"
        );
    }

    #[test]
    fn missing_binary_or_marker_is_not_verified() {
        let dir = TempDir::new();
        install_fresh(&dir);
        let marker = marker_text(&dir);
        assert!(!cached_install_is_verified(&LSP, LINUX_X64, &dir.0, None));
        assert!(!cached_install_is_verified(
            &LSP,
            LINUX_X64,
            &dir.0,
            Some("garbage")
        ));
        fs::remove_file(dir.0.join(binary_path(&LSP))).unwrap();
        assert!(!cached_install_is_verified(
            &LSP,
            LINUX_X64,
            &dir.0,
            Some(&marker)
        ));
    }

    #[test]
    fn failure_message_names_asset_platform_and_both_remedies() {
        let message = failure_message(
            &LSP,
            WINDOWS_ARM,
            &ProvisionError::UnsupportedPlatform {
                platform: WINDOWS_ARM,
            },
        );
        assert!(message.contains("Windows aarch64"), "{message}");
        assert!(
            message.contains("lsp.terraphim-lsp.binary.path"),
            "{message}"
        );
        assert!(message.contains("PATH"), "{message}");
        assert!(message.contains(LSP.tag), "{message}");

        let mismatch = failure_message(
            &LSP,
            LINUX_X64,
            &ProvisionError::ChecksumMismatch {
                asset: "terraphim-lsp-x86_64-unknown-linux-gnu".into(),
                expected: "a".into(),
                actual: "b".into(),
            },
        );
        assert!(mismatch.contains("terraphim-lsp-x86_64-unknown-linux-gnu"));
    }

    // --- end to end over a real directory and a fake host -----------------

    static COUNTER: AtomicUsize = AtomicUsize::new(0);

    struct TempDir(PathBuf);

    impl TempDir {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "zed-terraphim-provision-{}-{}",
                std::process::id(),
                COUNTER.fetch_add(1, Ordering::SeqCst)
            ));
            let _ = fs::remove_dir_all(&path);
            fs::create_dir_all(&path).unwrap();
            TempDir(path)
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    /// An in-process release server writing real files under `root`.
    struct FakeHost {
        root: PathBuf,
        bodies: HashMap<String, Vec<u8>>,
        release: Result<Vec<Asset>, String>,
        path_binary: Option<String>,
        release_calls: usize,
        downloads: Vec<String>,
        executable: Vec<String>,
        statuses: Vec<Status>,
    }

    impl FakeHost {
        /// A release for `spec` carrying every asset of the fixture list,
        /// with a checksum file consistent with the served bodies.
        fn serving(spec: &BinarySpec, root: &Path) -> Self {
            let mut assets = fixture_assets();
            let mut bodies = HashMap::new();
            let mut checksums = String::new();
            for asset in &mut assets {
                asset.download_url = format!("https://example.invalid/{}/{}", spec.tag, asset.name);
                if asset.name == spec.checksum_file {
                    continue;
                }
                let body = format!("binary:{}", asset.name).into_bytes();
                checksums.push_str(&format!(
                    "{}  {}\n",
                    hex_encode(&Sha256::digest(&body)),
                    asset.name
                ));
                bodies.insert(asset.download_url.clone(), body);
            }
            let checksum_url = assets
                .iter()
                .find(|asset| asset.name == spec.checksum_file)
                .unwrap()
                .download_url
                .clone();
            bodies.insert(checksum_url, checksums.into_bytes());
            FakeHost {
                root: root.to_path_buf(),
                bodies,
                release: Ok(assets),
                path_binary: None,
                release_calls: 0,
                downloads: Vec::new(),
                executable: Vec::new(),
                statuses: Vec::new(),
            }
        }

        /// The Gitea release of `spec`: every fixture asset and the checksum
        /// file at their `releases/download` URLs, consistent with the
        /// GitHub bodies. `gitea_asset_url` is the extension's own scheme.
        fn with_gitea(mut self, spec: &BinarySpec) -> Self {
            let repo_url = spec.gitea.expect("a spec with a Gitea source");
            let bodies: Vec<(String, Vec<u8>)> = self
                .bodies
                .iter()
                .map(|(url, body)| {
                    let name = url.rsplit('/').next().unwrap();
                    (gitea_asset_url(repo_url, spec.tag, name), body.clone())
                })
                .collect();
            self.bodies.extend(bodies);
            self
        }

        /// Tamper with `asset` on the Gitea release only.
        fn corrupt_gitea(&mut self, asset: &str) {
            for (url, body) in &mut self.bodies {
                if url.starts_with("https://git.terraphim.cloud/")
                    && url.ends_with(&format!("/{asset}"))
                {
                    body.extend_from_slice(b" tampered");
                }
            }
        }

        fn gitea_downloads(&self) -> Vec<&String> {
            self.downloads
                .iter()
                .filter(|url| url.starts_with(GITEA_RELEASES))
                .collect()
        }

        fn corrupt(&mut self, asset: &str) {
            for (url, body) in &mut self.bodies {
                if url.ends_with(&format!("/{asset}")) {
                    body.extend_from_slice(b" tampered");
                }
            }
        }

        fn network_calls(&self) -> usize {
            self.release_calls + self.downloads.len()
        }
    }

    impl Host for FakeHost {
        fn release_assets(&mut self, _repo: &str, _tag: &str) -> Result<Vec<Asset>, String> {
            self.release_calls += 1;
            self.release.clone()
        }
        fn download(&mut self, url: &str, path: &str) -> Result<(), String> {
            self.downloads.push(url.to_string());
            let body = self
                .bodies
                .get(url)
                .ok_or_else(|| format!("404 for {url}"))?;
            let target = self.root.join(path);
            fs::create_dir_all(target.parent().unwrap()).map_err(|e| e.to_string())?;
            fs::write(target, body).map_err(|e| e.to_string())
        }
        fn make_executable(&mut self, path: &str) -> Result<(), String> {
            assert!(self.root.join(path).is_file(), "{path} must exist");
            self.executable.push(path.to_string());
            Ok(())
        }
        fn set_status(&mut self, status: Status) {
            self.statuses.push(status);
        }
        fn which(&self, _name: &str) -> Option<String> {
            self.path_binary.clone()
        }
    }

    fn marker_path(root: &Path) -> PathBuf {
        root.join(install_dir(&LSP)).join(MARKER_FILE)
    }

    #[test]
    fn fresh_install_downloads_verifies_and_marks_last() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        let path = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(path, binary_path(&LSP));
        assert!(dir.0.join(&path).is_file());
        assert_eq!(host.executable, vec![path.clone()]);
        assert_eq!(
            host.statuses,
            vec![Status::CheckingForUpdate, Status::Downloading, Status::None]
        );
        let marker = fs::read_to_string(marker_path(&dir.0)).unwrap();
        assert!(marker_is_valid(&LSP, &marker));
        assert!(marker.contains("asset=terraphim-lsp-x86_64-unknown-linux-gnu"));
        // Temporary and checksum files are gone; only binary and marker remain.
        let mut left: Vec<String> = fs::read_dir(dir.0.join(install_dir(&LSP)))
            .unwrap()
            .map(|entry| entry.unwrap().file_name().into_string().unwrap())
            .collect();
        left.sort();
        assert_eq!(
            left,
            vec![".verified".to_string(), "terraphim-lsp".to_string()]
        );
    }

    #[test]
    fn verified_install_starts_offline() {
        // AC3 (offline with install) and I6.
        let dir = TempDir::new();
        let mut first = FakeHost::serving(&GH, &dir.0);
        resolve(&GH, LINUX_X64, None, &dir.0, &mut first).unwrap();

        let mut offline = FakeHost::serving(&GH, &dir.0);
        offline.release = Err("network unreachable".into());
        let path = resolve(&GH, LINUX_X64, None, &dir.0, &mut offline).unwrap();
        assert_eq!(path, binary_path(&LSP));
        assert_eq!(offline.network_calls(), 0);
        assert!(offline.statuses.is_empty());
        assert!(offline.executable.is_empty());
    }

    #[test]
    fn checksum_mismatch_installs_nothing() {
        // AC2 and I1.
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        host.corrupt("terraphim-lsp-x86_64-unknown-linux-gnu");
        let error = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("checksum mismatch"), "{error}");
        assert!(
            error.contains("terraphim-lsp-x86_64-unknown-linux-gnu"),
            "{error}"
        );
        assert!(host.executable.is_empty());
        assert!(!dir.0.join(install_dir(&LSP)).exists());
        assert!(matches!(host.statuses.last(), Some(Status::Failed(m)) if m == &error));
    }

    #[test]
    fn mismatch_falls_back_to_path_binary_with_a_status() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        host.corrupt("terraphim-lsp-x86_64-unknown-linux-gnu");
        host.path_binary = Some("/usr/local/bin/terraphim-lsp".into());
        let path = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(path, "/usr/local/bin/terraphim-lsp");
        assert!(host.executable.is_empty());
        let Some(Status::Failed(message)) = host.statuses.last() else {
            panic!("expected a failure status: {:?}", host.statuses);
        };
        assert!(
            message.contains("Using /usr/local/bin/terraphim-lsp from PATH"),
            "{message}"
        );
    }

    #[test]
    fn offline_without_install_falls_back_or_explains() {
        // AC3.
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        host.release = Err("network unreachable".into());
        host.path_binary = Some("/bin/terraphim-lsp".into());
        assert_eq!(
            resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap(),
            "/bin/terraphim-lsp"
        );

        host.path_binary = None;
        let error = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("network unreachable"), "{error}");
        assert!(error.contains("lsp.terraphim-lsp.binary.path"), "{error}");
        assert!(error.contains("PATH"), "{error}");
    }

    #[test]
    fn blank_path_binary_is_not_a_fallback() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        host.release = Err("offline".into());
        host.path_binary = Some("  ".into());
        assert!(resolve(&GH, LINUX_X64, None, &dir.0, &mut host).is_err());
    }

    #[test]
    fn explicit_path_makes_no_network_request() {
        // AC5.
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        let path = resolve(&GH, LINUX_X64, Some("/opt/my-lsp"), &dir.0, &mut host).unwrap();
        assert_eq!(path, "/opt/my-lsp");
        assert_eq!(host.network_calls(), 0);
        assert!(host.statuses.is_empty());
        assert!(!dir.0.join(install_dir(&LSP)).exists());
    }

    #[test]
    fn unsupported_platform_fails_before_the_network() {
        // AC6.
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        let error = resolve(&GH, WINDOWS_ARM, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("Windows aarch64"), "{error}");
        assert!(error.contains("lsp.terraphim-lsp.binary.path"), "{error}");
        assert_eq!(host.network_calls(), 0);
    }

    #[test]
    fn release_without_a_matching_asset_fails() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        host.release = Ok(fixture_assets()
            .into_iter()
            .filter(|asset| !asset.name.contains("linux"))
            .collect());
        let error = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("none of the expected assets"), "{error}");
        assert!(host.executable.is_empty());
    }

    #[test]
    fn release_without_checksum_file_fails_before_downloading_the_binary() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        host.release = Ok(fixture_assets()
            .into_iter()
            .filter(|asset| asset.name != LSP.checksum_file)
            .collect());
        let error = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("checksums.txt"), "{error}");
        assert!(host.downloads.is_empty());
    }

    #[test]
    fn missing_checksum_entry_fails_before_downloading_the_binary() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        let checksum_url = format!("https://example.invalid/{}/checksums.txt", LSP.tag);
        host.bodies.insert(
            checksum_url,
            format!("{}  unrelated\n", "1".repeat(64)).into_bytes(),
        );
        let error = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(
            error.contains("no entry for terraphim-lsp-x86_64-unknown-linux-gnu"),
            "{error}"
        );
        assert_eq!(host.downloads.len(), 1, "only the checksum file");
        assert!(host.executable.is_empty());
    }

    #[test]
    fn malformed_checksum_file_fails_closed() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        let checksum_url = format!("https://example.invalid/{}/checksums.txt", LSP.tag);
        host.bodies
            .insert(checksum_url, b"not a checksum file\n".to_vec());
        let error = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("malformed checksum file"), "{error}");
        assert!(host.executable.is_empty());
    }

    #[test]
    fn partial_directory_without_marker_is_overwritten() {
        // I2: a crash after the binary landed but before the marker.
        let dir = TempDir::new();
        let partial = dir.0.join(install_dir(&LSP));
        fs::create_dir_all(&partial).unwrap();
        fs::write(partial.join("terraphim-lsp"), b"half-written").unwrap();

        let mut host = FakeHost::serving(&GH, &dir.0);
        let path = resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(host.downloads.len(), 2);
        assert_eq!(
            fs::read(dir.0.join(path)).unwrap(),
            b"binary:terraphim-lsp-x86_64-unknown-linux-gnu"
        );
    }

    #[test]
    fn tag_change_installs_the_new_version_and_removes_old_ones() {
        // AC4.
        let dir = TempDir::new();
        let old = BinarySpec {
            tag: "terraphim_lsp-v1.21.0",
            ..LSP
        };
        let mut old_host = FakeHost::serving(&old, &dir.0);
        resolve(&old, LINUX_X64, None, &dir.0, &mut old_host).unwrap();
        let old_dir = dir.0.join(install_dir(&old));
        assert!(old_dir.is_dir());
        fs::create_dir_all(dir.0.join("grammars")).unwrap();
        fs::create_dir_all(dir.0.join("terraphim_mcp_server-v1")).unwrap();
        fs::write(
            dir.0.join("terraphim-lsp-notes.txt"),
            b"a file, not a directory",
        )
        .unwrap();

        let mut host = FakeHost::serving(&GH, &dir.0);
        resolve(&GH, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert!(!old_dir.exists());
        assert!(dir.0.join(install_dir(&LSP)).is_dir());
        assert!(dir.0.join("grammars").is_dir());
        assert!(dir.0.join("terraphim_mcp_server-v1").is_dir());
        assert!(dir.0.join("terraphim-lsp-notes.txt").is_file());
    }

    #[test]
    fn failed_install_keeps_older_versions() {
        let dir = TempDir::new();
        let old = BinarySpec {
            tag: "terraphim_lsp-v1.21.0",
            ..LSP
        };
        let mut old_host = FakeHost::serving(&old, &dir.0);
        resolve(&old, LINUX_X64, None, &dir.0, &mut old_host).unwrap();

        let mut host = FakeHost::serving(&GH, &dir.0);
        host.release = Err("offline".into());
        assert!(resolve(&GH, LINUX_X64, None, &dir.0, &mut host).is_err());
        assert!(dir.0.join(install_dir(&old)).is_dir());
    }

    #[test]
    fn windows_is_unsupported_and_points_to_the_path_setting() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        let error = resolve(&GH, WINDOWS_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("Windows x86_64"), "{error}");
        assert!(error.contains("lsp.terraphim-lsp.binary.path"), "{error}");
        assert_eq!(host.network_calls(), 0);
    }

    #[test]
    fn mac_install_prefers_the_universal_binary() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&GH, &dir.0);
        resolve(&GH, MAC_ARM, None, &dir.0, &mut host).unwrap();
        let marker = fs::read_to_string(marker_path(&dir.0)).unwrap();
        assert!(marker.contains("asset=terraphim-lsp-universal-apple-darwin"));
    }

    // --- the internal Gitea channel (rc.3) ---------------------------------

    #[test]
    fn gitea_urls_have_the_release_download_shape_of_the_captured_release() {
        // The fixture is the Gitea release's own asset list.
        for asset in fixture_assets() {
            assert_eq!(
                gitea_asset_url(
                    HISTORICAL_RC3.gitea.unwrap(),
                    HISTORICAL_RC3.tag,
                    &asset.name
                ),
                asset.download_url
            );
        }
    }

    #[test]
    fn gitea_release_lists_the_candidates_and_the_checksum_file() {
        let assets = gitea_release(&LSP, LINUX_X64).unwrap();
        let names: Vec<&str> = assets.iter().map(|a| a.name.as_str()).collect();
        assert_eq!(
            names,
            [
                "terraphim-lsp-x86_64-unknown-linux-gnu",
                "terraphim-lsp-x86_64-unknown-linux-musl",
                "checksums.txt"
            ]
        );
        assert!(assets[0].download_url.starts_with(
            "https://git.terraphim.cloud/terraphim/terraphim-lsp-releases/releases/download/"
        ));
        assert_eq!(
            gitea_release(&LSP, WINDOWS_X64),
            Err(ProvisionError::UnsupportedPlatform {
                platform: WINDOWS_X64
            })
        );
    }

    #[test]
    fn the_lsp_prefers_gitea_and_the_mcp_server_has_no_gitea_source() {
        assert_eq!(
            LSP.gitea,
            Some("https://git.terraphim.cloud/terraphim/terraphim-lsp-releases")
        );
        assert_eq!(MCP.gitea, None);
    }

    #[test]
    fn gitea_is_tried_first_and_needs_no_github_request() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0).with_gitea(&LSP);
        let path = resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(path, binary_path(&LSP));
        assert_eq!(host.release_calls, 0, "no GitHub release lookup");
        assert_eq!(host.gitea_downloads().len(), 2, "checksum file and binary");
        assert_eq!(host.downloads.len(), 2);
        assert_eq!(host.executable, vec![path.clone()]);
        assert_eq!(
            host.statuses,
            vec![Status::CheckingForUpdate, Status::Downloading, Status::None]
        );
        let marker = fs::read_to_string(marker_path(&dir.0)).unwrap();
        assert!(marker.contains("asset=terraphim-lsp-x86_64-unknown-linux-gnu"));
    }

    #[test]
    fn gitea_downloads_are_verified_against_the_gitea_checksums() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0).with_gitea(&LSP);
        host.corrupt_gitea("terraphim-lsp-x86_64-unknown-linux-gnu");
        // The GitHub copy is intact, so the mismatch falls through to it.
        let path = resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(
            fs::read(dir.0.join(&path)).unwrap(),
            b"binary:terraphim-lsp-x86_64-unknown-linux-gnu"
        );
        assert_eq!(host.release_calls, 1, "GitHub consulted after the mismatch");
        assert!(host.gitea_downloads().len() == 2);
        // With GitHub also tampered, nothing is installed.
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0).with_gitea(&LSP);
        host.corrupt_gitea("terraphim-lsp-x86_64-unknown-linux-gnu");
        host.corrupt("terraphim-lsp-x86_64-unknown-linux-gnu");
        let error = resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("checksum mismatch"), "{error}");
        assert!(host.executable.is_empty());
        assert!(!dir.0.join(install_dir(&LSP)).exists());
    }

    #[test]
    fn an_unreachable_gitea_release_falls_back_to_the_github_release() {
        // Off the tailnet no Gitea body is served: the download fails.
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0);
        let path = resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(path, binary_path(&LSP));
        assert_eq!(host.release_calls, 1);
        assert_eq!(
            host.gitea_downloads().len(),
            1,
            "only the checksum file was tried"
        );
        assert!(dir.0.join(&path).is_file());
        assert_eq!(
            host.statuses,
            vec![Status::CheckingForUpdate, Status::Downloading, Status::None],
            "one downloading status, not one per source"
        );
    }

    #[test]
    fn gitea_picks_the_first_candidate_its_checksums_list() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0).with_gitea(&LSP);
        // Gitea's checksum file has the musl build only.
        let url = gitea_asset_url(LSP.gitea.unwrap(), LSP.tag, "checksums.txt");
        let musl = host.bodies[&gitea_asset_url(
            LSP.gitea.unwrap(),
            LSP.tag,
            "terraphim-lsp-x86_64-unknown-linux-musl",
        )]
            .clone();
        host.bodies.insert(
            url,
            format!(
                "{}  terraphim-lsp-x86_64-unknown-linux-musl\n",
                hex_encode(&Sha256::digest(&musl))
            )
            .into_bytes(),
        );
        let path = resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap();
        assert_eq!(host.release_calls, 0);
        assert_eq!(fs::read(dir.0.join(path)).unwrap(), musl);
        let marker = fs::read_to_string(marker_path(&dir.0)).unwrap();
        assert!(marker.contains("asset=terraphim-lsp-x86_64-unknown-linux-musl"));
    }

    #[test]
    fn both_sources_failing_fall_back_to_path_and_the_message_names_both() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0);
        host.release = Err("github unreachable".into());
        host.path_binary = Some("/usr/bin/terraphim-lsp".into());
        assert_eq!(
            resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap(),
            "/usr/bin/terraphim-lsp"
        );
        let Some(Status::Failed(message)) = host.statuses.last() else {
            panic!("expected a failure status: {:?}", host.statuses);
        };
        assert!(message.contains("git.terraphim.cloud"), "{message}");
        assert!(message.contains("github unreachable"), "{message}");
        assert!(message.contains("from PATH"), "{message}");

        host.path_binary = None;
        let error = resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("Gitea"), "{error}");
        assert!(error.contains("GitHub"), "{error}");
        assert!(error.contains("github unreachable"), "{error}");
        assert!(error.contains("lsp.terraphim-lsp.binary.path"), "{error}");
    }

    #[test]
    fn a_verified_install_makes_no_request_to_either_source() {
        let dir = TempDir::new();
        let mut first = FakeHost::serving(&LSP, &dir.0).with_gitea(&LSP);
        resolve(&LSP, LINUX_X64, None, &dir.0, &mut first).unwrap();
        let mut offline = FakeHost::serving(&LSP, &dir.0);
        offline.release = Err("offline".into());
        resolve(&LSP, LINUX_X64, None, &dir.0, &mut offline).unwrap();
        assert_eq!(offline.network_calls(), 0);
    }

    #[test]
    fn unsupported_platform_still_fails_before_any_request() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0).with_gitea(&LSP);
        assert!(resolve(&LSP, WINDOWS_X64, None, &dir.0, &mut host).is_err());
        assert_eq!(host.network_calls(), 0);
    }

    #[test]
    fn conflicting_gitea_checksum_entries_fail_closed_not_to_the_next_candidate() {
        let dir = TempDir::new();
        let mut host = FakeHost::serving(&LSP, &dir.0).with_gitea(&LSP);
        let url = gitea_asset_url(LSP.gitea.unwrap(), LSP.tag, "checksums.txt");
        // The first candidate (glibc) is listed twice with different hashes;
        // the musl one is fine. The musl build must not be installed instead.
        let musl = hex_encode(&Sha256::digest(
            b"binary:terraphim-lsp-x86_64-unknown-linux-musl",
        ));
        host.bodies.insert(
            url,
            format!(
                "{a}  terraphim-lsp-x86_64-unknown-linux-gnu\n{b}  terraphim-lsp-x86_64-unknown-linux-gnu\n{musl}  terraphim-lsp-x86_64-unknown-linux-musl\n",
                a = "1".repeat(64),
                b = "2".repeat(64),
            )
            .into_bytes(),
        );
        // GitHub is down too, so the Gitea error is what the user sees.
        host.release = Err("github unreachable".into());
        let error = resolve(&LSP, LINUX_X64, None, &dir.0, &mut host).unwrap_err();
        assert!(error.contains("conflicting hashes"), "{error}");
        assert!(host.executable.is_empty());
        assert!(!dir.0.join(install_dir(&LSP)).exists());
    }
}

#[cfg(test)]
mod catalog_configuration_tests {
    use super::*;

    #[test]
    fn shared_public_release_pin_targets_rc5() {
        assert_eq!(LSP.tag, "terraphim_lsp-v1.22.0-rc.5");
        assert_eq!(LSP.repo, "terraphim/terraphim-ai");
        assert_eq!(LSP.checksum_file, "checksums.txt");
        if cfg!(feature = "public-catalog") {
            assert_eq!(configured_lsp().gitea, None);
        }
    }

    #[test]
    fn configured_lsp_changes_only_the_private_network_source() {
        let selected = configured_lsp();
        assert_eq!(
            BinarySpec {
                gitea: LSP.gitea,
                ..selected
            },
            LSP
        );
        assert_eq!(
            selected.gitea,
            if cfg!(feature = "public-catalog") {
                None
            } else {
                LSP.gitea
            }
        );
    }
}

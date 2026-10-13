//! Zed host glue for provisioning: the only place that calls the host.
//!
//! Everything it forwards is decided in [`crate::provision`], which is tested
//! natively; this adapter just maps host types and calls.

use crate::provision::{Arch, Asset, Host, Os, Platform, Status};
use zed_extension_api::{
    self as zed, DownloadedFileType, LanguageServerId, LanguageServerInstallationStatus, Worktree,
};

/// The Zed host as seen by provisioning, for one language server.
pub struct ZedHost<'a> {
    pub server_id: &'a LanguageServerId,
    pub worktree: &'a Worktree,
}

/// The platform Zed runs on.
pub fn current_platform() -> Platform {
    let (os, arch) = zed::current_platform();
    Platform {
        os: match os {
            zed::Os::Mac => Os::Mac,
            zed::Os::Linux => Os::Linux,
            zed::Os::Windows => Os::Windows,
        },
        arch: match arch {
            zed::Architecture::Aarch64 => Arch::Aarch64,
            zed::Architecture::X86 => Arch::X86,
            zed::Architecture::X8664 => Arch::X8664,
        },
    }
}

impl Host for ZedHost<'_> {
    fn release_assets(&mut self, repo: &str, tag: &str) -> Result<Vec<Asset>, String> {
        let release = zed::github_release_by_tag_name(repo, tag)?;
        Ok(release
            .assets
            .into_iter()
            .map(|asset| Asset {
                name: asset.name,
                download_url: asset.download_url,
            })
            .collect())
    }

    fn download(&mut self, url: &str, path: &str) -> Result<(), String> {
        zed::download_file(url, path, DownloadedFileType::Uncompressed)
    }

    fn make_executable(&mut self, path: &str) -> Result<(), String> {
        zed::make_file_executable(path)
    }

    fn set_status(&mut self, status: Status) {
        let status = match status {
            Status::None => LanguageServerInstallationStatus::None,
            Status::CheckingForUpdate => LanguageServerInstallationStatus::CheckingForUpdate,
            Status::Downloading => LanguageServerInstallationStatus::Downloading,
            Status::Failed(message) => LanguageServerInstallationStatus::Failed(message),
        };
        zed::set_language_server_installation_status(self.server_id, &status);
    }

    fn which(&self, name: &str) -> Option<String> {
        self.worktree.which(name)
    }
}

/// The Zed host as seen by provisioning for a context server.
///
/// The context-server API has no installation status and no worktree, so
/// status updates are dropped (failures reach the user through the returned
/// error) and there is no `PATH` lookup.
pub struct ContextHost;

impl Host for ContextHost {
    fn release_assets(&mut self, repo: &str, tag: &str) -> Result<Vec<Asset>, String> {
        let release = zed::github_release_by_tag_name(repo, tag)?;
        Ok(release
            .assets
            .into_iter()
            .map(|asset| Asset {
                name: asset.name,
                download_url: asset.download_url,
            })
            .collect())
    }

    fn download(&mut self, url: &str, path: &str) -> Result<(), String> {
        zed::download_file(url, path, DownloadedFileType::Uncompressed)
    }

    fn make_executable(&mut self, path: &str) -> Result<(), String> {
        zed::make_file_executable(path)
    }

    fn set_status(&mut self, _status: Status) {}

    fn which(&self, _name: &str) -> Option<String> {
        None
    }
}

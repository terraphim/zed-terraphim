//! Terraphim extension for Zed.
//!
//! A thin adapter: it provisions the pinned, checksummed `terraphim-lsp`
//! release (or uses the user's own binary), launches it for Markdown buffers
//! and forwards the user's `lsp.terraphim-lsp` settings. It also registers a
//! `terraphim` context server (MCP) provisioned the same way.
//! All knowledge-graph analysis lives in the language server
//! (`terraphim-ai`'s `terraphim_lsp` crate); the extension embeds none of it.
//!
//! The decisions that do not need the Zed host live in [`provision`] (binary
//! resolution, download verification, install layout) and [`config`]
//! (settings mapping, environment merging) so they are unit-tested natively;
//! [`host`] is the thin glue that calls Zed.

pub mod config;
pub mod host;
#[cfg(feature = "mcp")]
pub mod mcp;
pub mod provision;

use zed_extension_api::{self as zed, settings::LspSettings, LanguageServerId, Worktree};

#[cfg(feature = "mcp")]
use zed_extension_api::{settings::ContextServerSettings, ContextServerId, Project};

/// The extension state. It holds nothing: every request reads the current
/// settings, so edits to `settings.json` apply on the next server start or
/// configuration push without caching bugs.
struct TerraphimExtension;

/// The user's `lsp.terraphim-lsp` settings for `worktree`.
fn lsp_settings(worktree: &Worktree) -> LspSettings {
    // Reading settings only fails when the host cannot serialise them; the
    // defaults (provisioned binary, server defaults) are the right fallback.
    LspSettings::for_worktree(config::SERVER_ID, worktree).unwrap_or_default()
}

impl zed::Extension for TerraphimExtension {
    fn new() -> Self {
        TerraphimExtension
    }

    fn language_server_command(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> zed::Result<zed::Command> {
        let binary = lsp_settings(worktree).binary;
        let binary = binary.as_ref();
        // The extension's working directory is its own work directory, so
        // relative paths resolve inside it.
        let command = provision::resolve(
            &provision::configured_lsp(),
            host::current_platform(),
            binary.and_then(|binary| binary.path.as_deref()),
            std::path::Path::new("."),
            &mut host::ZedHost {
                server_id: language_server_id,
                worktree,
            },
        )?;
        let args = binary
            .and_then(|binary| binary.arguments.clone())
            .unwrap_or_default();
        let env = config::merge_env(
            worktree.shell_env(),
            binary.and_then(|binary| binary.env.clone()),
        );
        Ok(zed::Command { command, args, env })
    }

    #[cfg(feature = "mcp")]
    fn context_server_command(
        &mut self,
        _context_server_id: &ContextServerId,
        project: &Project,
    ) -> zed::Result<zed::Command> {
        let settings = ContextServerSettings::for_project(mcp::SERVER_ID, project)?;
        let command = settings.command.as_ref();
        let path = command.and_then(|command| mcp::override_path(command.path.as_deref()));
        let program = provision::resolve(
            &provision::MCP,
            host::current_platform(),
            path,
            std::path::Path::new("."),
            &mut host::ContextHost,
        )?;
        // Zed runs context servers from its own directory, so a provisioned
        // (work-directory relative) binary is made absolute.
        let program = if path.is_some() {
            program
        } else {
            std::env::current_dir()
                .map_err(|error| format!("cannot find the extension work directory: {error}"))?
                .join(program)
                .to_string_lossy()
                .into_owned()
        };
        let args = mcp::arguments(
            path.is_some(),
            command.and_then(|command| command.arguments.clone()),
            settings.settings.as_ref(),
        )?;
        let env = mcp::environment(command.and_then(|command| command.env.clone()));
        Ok(zed::Command {
            command: program,
            args,
            env,
        })
    }

    #[cfg(feature = "mcp")]
    fn context_server_configuration(
        &mut self,
        _context_server_id: &ContextServerId,
        _project: &Project,
    ) -> zed::Result<Option<zed::ContextServerConfiguration>> {
        Ok(Some(zed::ContextServerConfiguration {
            installation_instructions: mcp::installation_instructions(),
            settings_schema: mcp::settings_schema(),
            default_settings: mcp::default_settings(),
        }))
    }

    fn language_server_initialization_options(
        &mut self,
        _language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> zed::Result<Option<zed::serde_json::Value>> {
        let settings = lsp_settings(worktree);
        Ok(config::initialization_options(
            settings.initialization_options,
            settings.settings,
        ))
    }

    fn language_server_workspace_configuration(
        &mut self,
        _language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> zed::Result<Option<zed::serde_json::Value>> {
        let settings = lsp_settings(worktree);
        Ok(config::workspace_configuration(
            settings.initialization_options,
            settings.settings,
        ))
    }
}

zed::register_extension!(TerraphimExtension);

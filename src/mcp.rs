//! Host-independent logic for the `terraphim` context server (MCP).
//!
//! The extension provisions the pinned `terraphim_mcp_server` release (see
//! [`crate::provision::MCP`]) and starts it over stdio. Argument building,
//! override precedence and the configuration shown by Zed live here so they
//! are unit-tested natively.

use serde_json::{json, Value};

/// Context-server id, as registered in `extension.toml` and used as the key of
/// the user's `context_servers.<id>` settings.
pub const SERVER_ID: &str = "terraphim";

/// Profiles the server accepts; the first is the default.
pub const PROFILES: [&str; 2] = ["desktop", "server"];

/// The user's explicit command path, when set and not blank.
pub fn override_path(command_path: Option<&str>) -> Option<&str> {
    command_path.map(str::trim).filter(|path| !path.is_empty())
}

/// Arguments for the server.
///
/// With an explicit command (`override_active`) the user's own `arguments`
/// are used verbatim and nothing is added. Otherwise `--profile` (default
/// `desktop`) and, when set, `--config-dir` come from `settings`.
pub fn arguments(
    override_active: bool,
    user_arguments: Option<Vec<String>>,
    settings: Option<&Value>,
) -> Result<Vec<String>, String> {
    if override_active {
        return Ok(user_arguments.unwrap_or_default());
    }
    let setting = |key: &str| settings.and_then(|settings| settings.get(key));
    let profile = match setting("profile") {
        None | Some(Value::Null) => PROFILES[0],
        Some(Value::String(profile)) if PROFILES.contains(&profile.as_str()) => profile,
        Some(other) => {
            return Err(format!(
                "terraphim context server: invalid \"profile\" {other}; use one of {}",
                PROFILES.join(", ")
            ))
        }
    };
    let mut arguments = vec!["--profile".to_string(), profile.to_string()];
    match setting("config_dir") {
        None | Some(Value::Null) => {}
        Some(Value::String(dir)) if dir.trim().is_empty() => {}
        Some(Value::String(dir)) => {
            arguments.push("--config-dir".to_string());
            arguments.push(dir.trim().to_string());
        }
        Some(other) => {
            return Err(format!(
            "terraphim context server: invalid \"config_dir\" {other}; use a directory path string"
        ))
        }
    }
    Ok(arguments)
}

/// Environment from the user's `command.env`, sorted by name so the command
/// line is deterministic.
pub fn environment(
    user_env: Option<impl IntoIterator<Item = (String, String)>>,
) -> Vec<(String, String)> {
    let mut env: Vec<(String, String)> = user_env.into_iter().flatten().collect();
    env.sort();
    env
}

/// Installation instructions shown by Zed, in Markdown.
pub fn installation_instructions() -> String {
    "The Terraphim context server exposes the Terraphim knowledge graph and tools \
     to Zed's agent. The extension downloads a pinned, checksummed \
     `terraphim_mcp_server` release on first use; macOS and Linux only for now.\n\n\
     **Risk: all tools are enabled.** The server's tool list includes code and shell \
     execution tools (for example `rlm_code` and `rlm_bash`). Anything the agent is \
     allowed to call can run commands as you. Only enable this server for projects and \
     agents you trust, and review tool-call permissions in Zed.\n\n\
     Settings (all optional):\n\n\
     - `profile`: `desktop` (default) or `server`.\n\
     - `config_dir`: directory whose `.terraphim/` configuration the server reads. Zed \
     does not tell the extension the project root, so set this for project-specific \
     knowledge graphs.\n\n\
     To use your own binary, define `command` for `terraphim` in your Zed settings \
     (`path`, `arguments`, `env`); that overrides the extension and skips the download."
        .to_string()
}

/// JSON Schema for the settings, as a string.
pub fn settings_schema() -> String {
    json!({
        "type": "object",
        "additionalProperties": false,
        "properties": {
            "profile": {
                "type": "string",
                "enum": PROFILES,
                "default": PROFILES[0],
                "description": "Server profile."
            },
            "config_dir": {
                "type": "string",
                "description": "Directory containing the .terraphim/ configuration to use instead of the working directory."
            }
        }
    })
    .to_string()
}

/// Default settings template, as a string.
pub fn default_settings() -> String {
    "{\n  \"profile\": \"desktop\"\n}".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provision::{
        candidate_assets, failure_message, install_dir, lookup_checksum, pick_asset, Arch, Asset,
        Os, Platform, ProvisionError, MCP,
    };

    const CHECKSUMS: &str = include_str!("../tests/fixtures/mcp_checksums.txt");
    const ASSETS_JSON: &str = include_str!("../tests/fixtures/mcp_release_assets.json");

    fn strings(list: &[&str]) -> Vec<String> {
        list.iter().map(|item| item.to_string()).collect()
    }

    fn assets() -> Vec<Asset> {
        let value: Value = serde_json::from_str(ASSETS_JSON).unwrap();
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

    // --- arguments --------------------------------------------------------

    #[test]
    fn defaults_to_the_desktop_profile() {
        for settings in [None, Some(json!({})), Some(json!({"profile": null}))] {
            assert_eq!(
                arguments(false, None, settings.as_ref()).unwrap(),
                strings(&["--profile", "desktop"])
            );
        }
    }

    #[test]
    fn profile_and_config_dir_become_flags() {
        let settings = json!({"profile": "server", "config_dir": " /work/kg "});
        assert_eq!(
            arguments(false, None, Some(&settings)).unwrap(),
            strings(&["--profile", "server", "--config-dir", "/work/kg"])
        );
    }

    #[test]
    fn blank_config_dir_is_omitted() {
        for dir in [json!(""), json!("   "), Value::Null] {
            let settings = json!({"config_dir": dir});
            assert_eq!(
                arguments(false, None, Some(&settings)).unwrap(),
                strings(&["--profile", "desktop"])
            );
        }
    }

    #[test]
    fn invalid_settings_are_errors() {
        for settings in [
            json!({"profile": "laptop"}),
            json!({"profile": 3}),
            json!({"config_dir": 7}),
            json!({"config_dir": ["a"]}),
        ] {
            let error = arguments(false, None, Some(&settings)).unwrap_err();
            assert!(error.contains("invalid"), "{error}");
        }
    }

    #[test]
    fn explicit_command_uses_only_the_users_arguments() {
        let settings = json!({"profile": "server", "config_dir": "/x"});
        assert_eq!(
            arguments(true, Some(strings(&["--stdio"])), Some(&settings)).unwrap(),
            strings(&["--stdio"])
        );
        assert!(arguments(true, None, Some(&settings)).unwrap().is_empty());
    }

    #[test]
    fn override_path_ignores_blank_values() {
        assert_eq!(override_path(Some(" /opt/mcp \n")), Some("/opt/mcp"));
        for path in [None, Some(""), Some("  ")] {
            assert_eq!(override_path(path), None);
        }
    }

    #[test]
    fn environment_is_sorted() {
        let env = environment(Some(vec![
            ("B".to_string(), "2".to_string()),
            ("A".to_string(), "1".to_string()),
        ]));
        assert_eq!(
            env,
            vec![("A".into(), "1".into()), ("B".into(), "2".into())]
        );
        assert!(environment(None::<Vec<(String, String)>>).is_empty());
    }

    // --- configuration ----------------------------------------------------

    #[test]
    fn configuration_is_consistent() {
        let schema: Value = serde_json::from_str(&settings_schema()).unwrap();
        assert_eq!(
            schema["properties"]["profile"]["enum"],
            json!(["desktop", "server"])
        );
        assert_eq!(schema["properties"]["config_dir"]["type"], "string");
        let defaults: Value = serde_json::from_str(&default_settings()).unwrap();
        assert_eq!(defaults["profile"], "desktop");
        // The default settings produce valid arguments.
        assert!(arguments(false, None, Some(&defaults)).is_ok());
        let text = installation_instructions();
        for needle in ["rlm_bash", "rlm_code", "all tools", "config_dir", "command"] {
            assert!(
                text.to_lowercase().contains(&needle.to_lowercase()),
                "{needle}"
            );
        }
    }

    // --- MCP asset selection ----------------------------------------------

    fn platform(os: Os, arch: Arch) -> Platform {
        Platform { os, arch }
    }

    #[test]
    fn mcp_assets_per_platform() {
        assert_eq!(
            candidate_assets(&MCP, platform(Os::Mac, Arch::Aarch64)).unwrap(),
            strings(&[
                "terraphim_mcp_server-universal-apple-darwin",
                "terraphim_mcp_server-aarch64-apple-darwin"
            ])
        );
        assert_eq!(
            candidate_assets(&MCP, platform(Os::Linux, Arch::X8664)).unwrap(),
            strings(&[
                "terraphim_mcp_server-x86_64-unknown-linux-gnu",
                "terraphim_mcp_server-x86_64-unknown-linux-musl"
            ])
        );
        assert_eq!(
            candidate_assets(&MCP, platform(Os::Linux, Arch::Aarch64)).unwrap(),
            strings(&["terraphim_mcp_server-aarch64-unknown-linux-musl"])
        );
    }

    /// The fixtures are captured from the published pre-release, so the
    /// pinned tag must resolve to the real universal binary's digest.
    #[test]
    fn mcp_fixture_is_the_published_pinned_release() {
        assert_eq!(MCP.tag, "terraphim_mcp_server-v1.21.18-rc.1");
        let assets = assets();
        let candidates = candidate_assets(&MCP, platform(Os::Mac, Arch::Aarch64)).unwrap();
        let asset = pick_asset(&candidates, &assets).unwrap();
        assert_eq!(asset.name, "terraphim_mcp_server-universal-apple-darwin");
        assert!(asset
            .download_url
            .contains("/releases/download/terraphim_mcp_server-v1.21.18-rc.1/"));
        assert_eq!(
            lookup_checksum(CHECKSUMS, &asset.name).unwrap(),
            "2e422deb1921b238787b99655c5900127fe8e26de9c32784e6ce8cd78d96bdb2"
        );
    }

    #[test]
    fn mcp_fixture_resolves_and_verifies_every_supported_platform() {
        let assets = assets();
        for platform in [
            platform(Os::Mac, Arch::Aarch64),
            platform(Os::Mac, Arch::X8664),
            platform(Os::Linux, Arch::X8664),
            platform(Os::Linux, Arch::Aarch64),
        ] {
            let candidates = candidate_assets(&MCP, platform).unwrap();
            let asset = pick_asset(&candidates, &assets).unwrap();
            assert!(asset.name.starts_with("terraphim_mcp_server-"));
            assert!(asset.download_url.contains("terraphim-clients"));
            assert_eq!(lookup_checksum(CHECKSUMS, &asset.name).unwrap().len(), 64);
        }
    }

    #[test]
    fn windows_is_unsupported_and_the_message_points_to_the_command_override() {
        let windows = platform(Os::Windows, Arch::X8664);
        let error = candidate_assets(&MCP, windows).unwrap_err();
        assert_eq!(
            error,
            ProvisionError::UnsupportedPlatform { platform: windows }
        );
        let message = failure_message(&MCP, windows, &error);
        assert!(message.contains("Windows x86_64"), "{message}");
        assert!(
            message.contains("context_servers.terraphim.command.path"),
            "{message}"
        );
        assert!(
            !message.contains("PATH"),
            "no PATH lookup is offered: {message}"
        );
    }

    #[test]
    fn mcp_and_lsp_installs_never_share_or_clean_each_others_directories() {
        use crate::provision::{stale_dirs, LSP};
        let lsp_dir = install_dir(&LSP);
        let mcp_dir = install_dir(&MCP);
        assert!(stale_dirs(&MCP, std::slice::from_ref(&lsp_dir)).is_empty());
        assert!(stale_dirs(&LSP, std::slice::from_ref(&mcp_dir)).is_empty());
        assert_ne!(lsp_dir, mcp_dir);
    }
}

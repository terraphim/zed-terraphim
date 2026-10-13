//! Host-independent configuration logic for the Terraphim extension.
//!
//! Nothing here calls the Zed host, so every rule is unit-tested natively
//! with `cargo test`. Binary resolution lives in [`crate::provision`].

use serde_json::Value;
use std::collections::BTreeMap;

/// Language-server id, as registered in `extension.toml` and used as the key
/// of the user's `lsp.<id>` settings.
pub const SERVER_ID: &str = "terraphim-lsp";

/// Environment variables, in the shape the Zed host expects.
pub type EnvVars = Vec<(String, String)>;

/// Merges the user's `binary.env` over the worktree shell environment.
///
/// User values win on conflict. The result is sorted by name so the command
/// line is deterministic.
pub fn merge_env(
    shell_env: EnvVars,
    user_env: Option<impl IntoIterator<Item = (String, String)>>,
) -> EnvVars {
    let mut merged: BTreeMap<String, String> = shell_env.into_iter().collect();
    if let Some(user_env) = user_env {
        merged.extend(user_env);
    }
    merged.into_iter().collect()
}

/// Treats `null` as absent.
fn present(value: Option<Value>) -> Option<Value> {
    value.filter(|value| !value.is_null())
}

/// `initializationOptions` sent to the server.
///
/// `lsp.terraphim-lsp.initialization_options` when set, otherwise
/// `lsp.terraphim-lsp.settings`, so a user who writes the settings once gets
/// them from the first request on. The server accepts the object bare or
/// under a `terraphim` key, so it is passed through unchanged.
pub fn initialization_options(
    initialization_options: Option<Value>,
    settings: Option<Value>,
) -> Option<Value> {
    present(initialization_options).or_else(|| present(settings))
}

/// Workspace configuration (`workspace/didChangeConfiguration` and
/// `workspace/configuration`) sent to the server.
///
/// `lsp.terraphim-lsp.settings` when set, otherwise the initialization
/// options, so settings changed while Zed runs reach the server without a
/// restart and the server never falls back to defaults behind the user's
/// back.
pub fn workspace_configuration(
    initialization_options: Option<Value>,
    settings: Option<Value>,
) -> Option<Value> {
    present(settings).or_else(|| present(initialization_options))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn env(pairs: &[(&str, &str)]) -> EnvVars {
        pairs
            .iter()
            .map(|(name, value)| (name.to_string(), value.to_string()))
            .collect()
    }

    #[test]
    fn user_env_overrides_shell_env_and_is_sorted() {
        let merged = merge_env(
            env(&[("PATH", "/bin"), ("HOME", "/home/a")]),
            Some(env(&[
                ("TERRAPHIM_THESAURUS", "/kg.json"),
                ("PATH", "/custom"),
            ])),
        );
        assert_eq!(
            merged,
            env(&[
                ("HOME", "/home/a"),
                ("PATH", "/custom"),
                ("TERRAPHIM_THESAURUS", "/kg.json"),
            ])
        );
    }

    #[test]
    fn no_user_env_keeps_shell_env() {
        let merged = merge_env(env(&[("PATH", "/bin")]), None::<EnvVars>);
        assert_eq!(merged, env(&[("PATH", "/bin")]));
    }

    #[test]
    fn settings_feed_initialization_options_when_not_set() {
        let settings = json!({"inlayHints": true, "lab": {"actions": ["hedges_and_filler"]}});
        assert_eq!(
            initialization_options(None, Some(settings.clone())),
            Some(settings.clone())
        );
        assert_eq!(
            initialization_options(Some(Value::Null), Some(settings.clone())),
            Some(settings)
        );
    }

    #[test]
    fn explicit_initialization_options_win() {
        let init = json!({"terraphim": {"ghostDiagnostics": false}});
        let settings = json!({"inlayHints": true});
        assert_eq!(
            initialization_options(Some(init.clone()), Some(settings.clone())),
            Some(init.clone())
        );
        assert_eq!(
            workspace_configuration(Some(init), Some(settings.clone())),
            Some(settings)
        );
    }

    #[test]
    fn workspace_configuration_falls_back_to_initialization_options() {
        let init = json!({"inlayHints": true});
        assert_eq!(
            workspace_configuration(Some(init.clone()), None),
            Some(init.clone())
        );
        assert_eq!(
            workspace_configuration(Some(init.clone()), Some(Value::Null)),
            Some(init)
        );
    }

    #[test]
    fn nothing_configured_sends_nothing() {
        assert_eq!(initialization_options(None, None), None);
        assert_eq!(workspace_configuration(Some(Value::Null), None), None);
    }

    #[test]
    fn settings_pass_through_unchanged() {
        // The server accepts both shapes; the extension must not rewrite them.
        for value in [
            json!({"inlayHints": true, "lab": {"actions": ["off_tone"], "trigger": "command"}}),
            json!({"terraphim": {"inlayHints": true}}),
        ] {
            assert_eq!(
                workspace_configuration(None, Some(value.clone())),
                Some(value)
            );
        }
    }
}

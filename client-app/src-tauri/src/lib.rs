mod commands;

pub fn build_app() -> tauri::Builder<tauri::Wry> {
    tauri::Builder::default()
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    build_app()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Verify that build_app() returns a non-null builder instance.
    #[test]
    fn test_build_app_returns_builder() {
        let builder = build_app();
        // The builder type is opaque; we simply ensure it can be created.
        let _ = builder;
    }

    /// Compile-time / smoke test ensuring the public run function exists.
    #[test]
    fn test_run_fn_exists() {
        // We cannot actually call run() in a unit test because it blocks on the event loop.
        // This test documents that the function is part of the public API.
        let _fn_ptr: fn() = run;
    }
}

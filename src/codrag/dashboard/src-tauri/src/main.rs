#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::Manager;
use tauri::api::process::CommandEvent;
use std::thread;
use std::time::Duration;

fn is_port_open(port: u16) -> bool {
    std::net::TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn is_daemon_healthy(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{}/health", port);
    // Use blocking client for simplicity in setup hook
    match reqwest::blocking::get(&url) {
        Ok(resp) => resp.status().is_success(),
        Err(_) => false,
    }
}

fn main() {
  tauri::Builder::default()
    .setup(|app| {
        let port = 8400;
        let mut launch_sidecar = true;

        if is_port_open(port) {
            println!("[Tauri] Port {} is open, checking health...", port);
            if is_daemon_healthy(port) {
                println!("[Tauri] Daemon is healthy. Attaching.");
                launch_sidecar = false;
            } else {
                println!("[Tauri] Port is open but daemon unhealthy/unknown. Attempting to launch sidecar anyway (might fail if port blocked).");
            }
        }

        if launch_sidecar {
            println!("[Tauri] Launching sidecar...");
            // "codrag-daemon" corresponds to binaries/codrag-daemon-<target>
            let sidecar = tauri::api::process::Command::new_sidecar("codrag-daemon")
                .expect("Failed to create sidecar command");
            
            // The daemon defaults to 8400, but we can be explicit
            // sidecar.args(&["--port", "8400"]);

            let (mut rx, _child) = sidecar.spawn().expect("Failed to spawn sidecar");

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        tauri::api::process::CommandEvent::Stdout(line) => {
                            println!("[Daemon] {}", line);
                        }
                        tauri::api::process::CommandEvent::Stderr(line) => {
                            eprintln!("[Daemon] {}", line);
                        }
                        _ => {}
                    }
                }
            });
            
            // Simple wait to allow daemon to startup
            thread::sleep(Duration::from_secs(1));
        }

        Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}

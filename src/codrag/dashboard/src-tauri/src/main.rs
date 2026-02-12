#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::{Manager, RunEvent};
use tauri::api::process::{Command, CommandEvent, CommandChild};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

struct SidecarState {
    child: Mutex<Option<CommandChild>>,
}

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

#[derive(serde::Serialize)]
struct DaemonConfig {
    url: String,
    port: u16,
}

#[tauri::command]
fn get_daemon_config() -> DaemonConfig {
    // MVP: Currently hardcoded to 8400. 
    // Future: Retrieve from managed state if dynamic port selection is implemented.
    DaemonConfig {
        url: "http://127.0.0.1:8400".to_string(),
        port: 8400,
    }
}

fn main() {
  let app = tauri::Builder::default()
    .manage(SidecarState { child: Mutex::new(None) })
    .invoke_handler(tauri::generate_handler![get_daemon_config])
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
            let sidecar = Command::new_sidecar("codrag-daemon")
                .expect("Failed to create sidecar command");
            
            // The daemon defaults to 8400, but we can be explicit
            // sidecar.args(&["--port", "8400"]);

            let (mut rx, child) = sidecar.spawn().expect("Failed to spawn sidecar");
            
            // Store child process handle for cleanup
            let state = app.state::<SidecarState>();
            *state.child.lock().unwrap() = Some(child);

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            println!("[Daemon] {}", line);
                        }
                        CommandEvent::Stderr(line) => {
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
    .build(tauri::generate_context!())
    .expect("error while building tauri application");

  app.run(|app_handle, event| {
      if let RunEvent::Exit = event {
          let state = app_handle.state::<SidecarState>();
          let mut child = state.child.lock().unwrap();
          if let Some(c) = child.take() {
              println!("[Tauri] Killing sidecar process...");
              if let Err(e) = c.kill() {
                  eprintln!("[Tauri] Failed to kill sidecar: {}", e);
              } else {
                  println!("[Tauri] Sidecar killed.");
              }
          }
      }
  });
}

#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::{Manager, RunEvent};
use tauri::api::process::{Command, CommandEvent, CommandChild};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use uuid::Uuid;

struct SidecarState {
    child: Mutex<Option<CommandChild>>,
}

struct AppConfig {
    token: String,
}

fn is_port_open(port: u16) -> bool {
    std::net::TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn is_daemon_healthy(port: u16, token: &str) -> bool {
    let url = format!("http://127.0.0.1:{}/health", port);
    let client = reqwest::blocking::Client::new();
    match client.get(&url).header("Authorization", format!("Bearer {}", token)).send() {
        Ok(resp) => resp.status().is_success(),
        Err(_) => false,
    }
}

#[derive(serde::Serialize)]
struct DaemonConfig {
    url: String,
    port: u16,
    token: String,
}

#[tauri::command]
fn get_daemon_config(config: tauri::State<'_, AppConfig>) -> DaemonConfig {
    DaemonConfig {
        url: "http://127.0.0.1:8400".to_string(),
        port: 8400,
        token: config.token.clone(),
    }
}

// ── Dev-Only Commands ────────────────────────────────────────────────────────
#[cfg(debug_assertions)]
#[tauri::command]
fn trigger_mock_event() {
    println!("[Dev] Mock event triggered");
}

fn main() {
  let ipc_token = Uuid::new_v4().to_string();
  let token_clone = ipc_token.clone();

  let mut builder = tauri::Builder::default()
    .manage(SidecarState { child: Mutex::new(None) })
    .manage(AppConfig { token: ipc_token });

  // Conditionally register commands
  #[cfg(debug_assertions)]
  {
      builder = builder.invoke_handler(tauri::generate_handler![
          get_daemon_config,
          trigger_mock_event,
      ]);
  }
  
  #[cfg(not(debug_assertions))]
  {
      builder = builder.invoke_handler(tauri::generate_handler![
          get_daemon_config,
      ]);
  }

  let app = builder
    .setup(move |app| {
        // Conditionally open devtools on startup
        #[cfg(debug_assertions)]
        {
            let window = app.get_window("main").unwrap();
            window.open_devtools();
        }

        let port = 8400;
        let mut launch_sidecar = true;

        if is_port_open(port) {
            println!("[Tauri] Port {} is open, checking health...", port);
            if is_daemon_healthy(port, &token_clone) {
                println!("[Tauri] Daemon is healthy. Attaching.");
                launch_sidecar = false;
            } else {
                println!("[Tauri] Port is open but daemon unhealthy/unknown. Attempting to launch sidecar anyway (might fail if port blocked).");
            }
        }

        if launch_sidecar {
            println!("[Tauri] Launching sidecar...");
            // "prep-daemon" corresponds to binaries/prep-daemon-<target>
            let mut sidecar = Command::new_sidecar("prep-daemon")
                .expect("Failed to create sidecar command");

            // Pass the token to the daemon via environment variable
            let mut envs = std::collections::HashMap::new();
            envs.insert("PREP_DAEMON_TOKEN".to_string(), token_clone.clone());
            sidecar = sidecar.envs(envs);

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

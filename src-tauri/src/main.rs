#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};
use std::{error::Error, io};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

use tauri::{AppHandle, Manager, RunEvent, WindowBuilder, WindowUrl};

struct BackendState(Mutex<Option<Child>>);

fn install_dir() -> PathBuf {
    if let Ok(d) = std::env::var("USPEX_INSTALL_DIR") {
        if !d.is_empty() {
            return PathBuf::from(d);
        }
    }
    if let Ok(appdata) = std::env::var("APPDATA") {
        if !appdata.is_empty() {
            return PathBuf::from(appdata).join("USPEX Runner");
        }
    }
    PathBuf::from(".")
}

fn find_backend_exe(app: &AppHandle) -> Result<PathBuf, String> {
    let exe = std::env::current_exe()
        .map_err(|e| format!("Cannot get exe path: {e}"))?;
    let exe_dir = exe.parent()
        .ok_or("Cannot get exe directory")?
        .to_path_buf();

    // With map-format resources {"src": "."}, Tauri places files next to the exe.
    // resource_dir() on Windows also returns exe_dir. Try both patterns for safety.
    let candidates: Vec<PathBuf> = vec![
        exe_dir.join("USPEX_Runner_Backend.exe"),
        exe_dir.join("resources").join("USPEX_Runner_Backend.exe"),
        app.path_resolver()
            .resource_dir()
            .map(|d| d.join("USPEX_Runner_Backend.exe"))
            .unwrap_or_else(|| exe_dir.join("USPEX_Runner_Backend.exe")),
    ];

    for path in &candidates {
        if path.is_file() {
            return Ok(path.clone());
        }
    }

    let searched: Vec<String> = candidates
        .iter()
        .map(|p| format!("  {}", p.display()))
        .collect();

    // List files in exe_dir to help diagnose
    let dir_contents: Vec<String> = std::fs::read_dir(&exe_dir)
        .map(|rd| {
            rd.filter_map(|e| e.ok())
              .map(|e| format!("  {}", e.file_name().to_string_lossy()))
              .collect()
        })
        .unwrap_or_default();

    let dir_list = if dir_contents.is_empty() {
        "  (empty or unreadable)".to_string()
    } else {
        dir_contents.join("\n")
    };

    Err(format!(
        "USPEX_Runner_Backend.exe not found.\n\nApp dir: {}\n\nSearched:\n{}\n\nFiles in app dir:\n{}",
        exe_dir.display(),
        searched.join("\n"),
        dir_list
    ))
}

fn read_backend_port(timeout: Duration) -> Result<u16, String> {
    let port_file = install_dir().join(".port");
    let start = Instant::now();
    loop {
        if start.elapsed() > timeout {
            return Err(format!(
                "Timeout waiting for backend.\nPort file: {}\nExists: {}",
                port_file.display(),
                port_file.exists()
            ));
        }
        if let Ok(content) = fs::read_to_string(&port_file) {
            if let Ok(port) = content.trim().parse::<u16>() {
                if TcpStream::connect(format!("127.0.0.1:{port}")).is_ok() {
                    return Ok(port);
                }
            }
        }
        thread::sleep(Duration::from_millis(200));
    }
}

fn start_backend(app: &AppHandle) -> Result<Child, String> {
    let install_d = install_dir();

    let mut cmd = if cfg!(debug_assertions) {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .ok_or("Failed to resolve project root")?
            .to_path_buf();

        let mut cmd = Command::new("python");
        cmd.arg("run_backend.py");
        cmd.current_dir(root);
        cmd
    } else {
        let backend_path = find_backend_exe(app)?;
        let resource_dir = backend_path
            .parent()
            .ok_or("Cannot get backend directory")?
            .to_path_buf();

        let mut cmd = Command::new(&backend_path);
        cmd.current_dir(resource_dir);
        cmd
    };

    cmd.env("USPEX_INSTALL_DIR", install_d.to_string_lossy().as_ref());
    cmd.stdin(Stdio::null());
    cmd.stdout(Stdio::null());
    cmd.stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);

    cmd.spawn().map_err(|e| format!("Failed to spawn backend: {e}"))
}

fn create_main_window(app: &AppHandle, port: u16) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{port}")
        .parse()
        .map_err(|e| format!("Invalid URL: {e}"))?;

    WindowBuilder::new(app, "main", WindowUrl::External(url))
        .title("USPEX Runner")
        .inner_size(1440.0, 960.0)
        .min_inner_size(1200.0, 760.0)
        .resizable(true)
        .build()
        .map_err(|e| format!("Failed to create window: {e}"))?;

    Ok(())
}

fn stop_backend(app: &AppHandle) {
    let state = app.state::<BackendState>();
    if let Some(mut child) = state.0.lock().ok().and_then(|mut g| g.take()) {
        let pid = child.id();
        #[cfg(target_os = "windows")]
        {
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .creation_flags(CREATE_NO_WINDOW)
                .status();
        }
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn show_error(message: &str) {
    tauri::api::dialog::blocking::MessageDialogBuilder::new(
        "USPEX Runner — Error",
        message,
    )
    .kind(tauri::api::dialog::MessageDialogKind::Error)
    .show();
}

fn boxed_error(msg: String) -> Box<dyn Error> {
    show_error(&msg);
    Box::new(io::Error::new(io::ErrorKind::Other, msg))
}

fn main() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let handle = app.handle();

            if cfg!(debug_assertions) {
                app.manage(BackendState(Mutex::new(None)));
                create_main_window(&handle, 8503).map_err(boxed_error)?;
            } else {
                let child = start_backend(&handle).map_err(boxed_error)?;
                let port = read_backend_port(Duration::from_secs(60))
                    .map_err(boxed_error)?;
                app.manage(BackendState(Mutex::new(Some(child))));
                create_main_window(&handle, port).map_err(boxed_error)?;
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            stop_backend(app);
        }
    });
}

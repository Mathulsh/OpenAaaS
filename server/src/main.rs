//! OpenAaaS Server
//!
//! 异步Agent即服务 (Agent-as-a-Service) 服务端 - 一对一服务模型

use anyhow::Context;
use axum::{
    Router,
    extract::DefaultBodyLimit,
};
use clap::{Parser, Subcommand};
use std::io::{self, IsTerminal, Write};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::time::Duration;
use tokio::net::TcpListener;
use tokio::sync::watch;
use tower_http::{
    compression::CompressionLayer, timeout::TimeoutLayer, trace::TraceLayer,
};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use uuid::Uuid;

use open_aaas_server::{config::AppConfig, handlers, state::AppState};

const SERVER_LONG_ABOUT: &str = "OpenAaaS Server - 异步 Agent 即服务的调度中心\n\n负责接收 Client 任务、管理 Agent 注册与心跳、分发任务并中转结果文件。";
const SERVER_AFTER_HELP: &str = "常用流程:\n  open-aaas-server run\n  open-aaas-server status\n  open-aaas-server stop\n\n首次运行:\n  如果当前目录没有 config.toml，run 会自动生成配置、SQLite 数据库和数据目录。\n  默认数据目录: ./data\n  默认监听地址: 0.0.0.0:8080";
const SERVER_RUN_AFTER_HELP: &str = "默认行为:\n  配置文件: ./config.toml\n  数据目录: ./data\n  数据库: ./data/app.db\n  文件目录: ./data/files\n  监听地址: 0.0.0.0:8080";
const SERVER_DETACHED_AFTER_HELP: &str = "输出位置:\n  pidfile: 数据目录/server.pid\n  日志: 数据目录/server.log";
const SERVER_RUN_LONG_ABOUT: &str = "前台启动 OpenAaaS Server；首次运行会自动创建默认配置、数据目录、SQLite 数据库、文件目录、secret_key 和 admin_api_key。";
const SERVER_DETACHED_LONG_ABOUT: &str = "后台启动 OpenAaaS Server；适合长期运行，日志和 pidfile 默认写入数据目录。";
const SERVER_STATUS_LONG_ABOUT: &str = "查看 OpenAaaS Server 运行状态；会读取配置文件和 pidfile，显示配置路径、数据目录、监听地址和运行状态。";
const SERVER_STOP_LONG_ABOUT: &str = "停止后台运行的 OpenAaaS Server；根据 pidfile 查找进程并发送停止信号。";

#[derive(Parser)]
#[command(name = "server")]
#[command(about = "OpenAaaS Server - 异步 Agent 即服务中心")]
#[command(long_about = SERVER_LONG_ABOUT)]
#[command(after_help = SERVER_AFTER_HELP)]
#[command(version = env!("CARGO_PKG_VERSION"))]
struct Cli {
    /// 配置文件路径，默认使用当前目录的 config.toml
    #[arg(long, global = true, value_name = "FILE")]
    config: Option<PathBuf>,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// 前台启动 Server
    #[command(long_about = SERVER_RUN_LONG_ABOUT)]
    #[command(after_help = SERVER_RUN_AFTER_HELP)]
    Run,
    /// 后台启动 Server
    #[command(name = "run-detached")]
    #[command(long_about = SERVER_DETACHED_LONG_ABOUT)]
    #[command(after_help = SERVER_DETACHED_AFTER_HELP)]
    RunDetached,
    /// 查看 Server 运行状态
    #[command(long_about = SERVER_STATUS_LONG_ABOUT)]
    Status,
    /// 停止后台 Server
    #[command(long_about = SERVER_STOP_LONG_ABOUT)]
    Stop,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let config_path = cli.config.unwrap_or_else(AppConfig::config_path);

    match cli.command {
        Commands::Run => run_foreground(config_path).await,
        Commands::RunDetached => run_detached(config_path).await,
        Commands::Stop => stop(config_path).await,
        Commands::Status => status(config_path).await,
    }
}

fn load_config_from_path(path: &PathBuf) -> anyhow::Result<AppConfig> {
    let config = config::Config::builder()
        .add_source(config::File::from(path.as_path()).required(false))
        .add_source(config::Environment::with_prefix("APP").separator("__"))
        .build()?;
    Ok(config.try_deserialize()?)
}

fn prepare_server_config(config_path: &PathBuf) -> anyhow::Result<AppConfig> {
    let interactive = io::stdin().is_terminal() && io::stdout().is_terminal();
    let is_first_startup = !config_path.exists();
    let mut changed = false;

    let mut config = if config_path.exists() {
        load_config_from_path(config_path).context("加载 config.toml 失败")?
    } else {
        let config = AppConfig::startup_default();
        eprintln!("config.toml 不存在，将在当前目录生成默认配置。");
        changed = true;
        config
    };

    if database_dir_from_url(&config.database.url).is_none()
        || is_blank(&config.task.file_storage_path)
    {
        let data_dir = choose_server_data_dir(interactive, "./data")?;
        apply_server_data_dir(&mut config, &data_dir);
        changed = true;
    }

    if interactive && is_first_startup {
        let default_addr = config.server.addr.to_string();
        let addr = loop {
            let input = prompt_with_default(
                "Server listen address",
                &default_addr,
                "The address and port the server will bind to.",
            )?;
            match input.parse::<SocketAddr>() {
                Ok(addr) => break addr,
                Err(e) => {
                    eprintln!("Invalid address '{}': {}. Please try again.", input, e);
                    continue;
                }
            }
        };
        if addr != config.server.addr {
            config.server.addr = addr;
            changed = true;
        }
    }

    if secret_needs_generation(config.secret_key.as_deref()) {
        config.secret_key = Some(generate_secret());
        changed = true;
    }

    if is_blank_option(config.admin_api_key.as_deref()) {
        let generated = format!("ak_admin_{}", &generate_secret()[..16]);
        let value = if interactive {
            prompt_with_default(
                "Admin API key",
                &generated,
                "用于管理员接口和生成 agent-core 注册 token。直接回车使用随机值。",
            )?
        } else {
            generated
        };
        config.admin_api_key = Some(value);
        changed = true;
    }

    ensure_server_runtime_dirs(&config)?;

    if changed {
        config.save_to_path(config_path)?;
        eprintln!("已更新配置文件: {}", config_path.display());
    }

    Ok(config)
}

async fn run_foreground(config_path: PathBuf) -> anyhow::Result<()> {
    // 加载 .env 文件（如果存在）
    dotenvy::dotenv().ok();

    // 1. 准备配置
    let config = prepare_server_config(&config_path)?;

    // 检查是否已有实例在运行
    if let Some(pid) = check_running(&config)? {
        anyhow::bail!("Server 已在运行 (PID: {})，请先停止或运行 `server stop`", pid);
    }

    // 写入 pidfile
    write_pidfile(&config)?;

    // 2. 初始化日志
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| {
                format!("open_aaas_server={},tower_http=warn", config.log_level).into()
            }),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    tracing::info!(
        "Starting OpenAaaS Server v{} (一对一服务模型)",
        env!("CARGO_PKG_VERSION")
    );

    // 2. 加载配置
    tracing::info!(
        "Server config: addr={}, timeout_secs={}, max_body_size={}",
        config.server.addr,
        config.server.timeout_secs,
        config.server.max_body_size
    );
    tracing::info!("Database config: {:?}", config.database);


    // 3. 创建数据库连接
    let state = AppState::new(config.clone()).await?;

    // 4. 初始化数据库表
    state.db.init_tables().await?;
    tracing::info!("Database tables initialized");

    // 确保 admin 用户存在
    let secret_key = config.secret_key.as_deref()
        .ok_or_else(|| anyhow::anyhow!("Secret key not configured"))?;
    let admin_api_key = runtime_admin_api_key(&config)
        .unwrap_or_else(|| format!("ak_admin_{}", Uuid::new_v4().simple()));
    let admin_hash = open_aaas_server::auth::hash_api_key(secret_key, &admin_api_key);
    let result = sqlx::query(
        "INSERT OR IGNORE INTO users (id, api_key, name, role) VALUES (?, ?, ?, ?)"
    )
    .bind("admin")
    .bind(&admin_hash)
    .bind("Administrator")
    .bind("admin")
    .execute(state.db.pool())
    .await?;

    if result.rows_affected() > 0 {
        tracing::warn!("Admin 用户已创建，API Key: {}（请保存，只展示一次）", admin_api_key);
    }

    // 更新管理员API Key（优先环境变量，其次 config.toml）
    if let Some(admin_key) = runtime_admin_api_key(&config) {
        let hashed_admin_key = open_aaas_server::auth::hash_api_key(secret_key, &admin_key);
        sqlx::query("UPDATE users SET api_key = ? WHERE id = 'admin'")
            .bind(&hashed_admin_key)
            .execute(state.db.pool())
            .await?;
        tracing::info!("Admin API Key updated from environment variable");
    }

    // 查询管理员API Key状态（仅输出提示信息，不泄露key值）
    let admin_key_exists: Option<String> =
        sqlx::query_scalar("SELECT api_key FROM users WHERE id = 'admin'")
            .fetch_optional(state.db.pool())
            .await?;

    tracing::info!("========================================");
    if let Some(key) = admin_key_exists {
        if key.is_empty() || key == "not-set" {
            tracing::warn!("Admin API Key 未设置，请设置 ADMIN_API_KEY 环境变量");
        } else {
            tracing::info!("Admin API Key 已配置 (长度: {} 字符)", key.len());
        }
    } else {
        tracing::warn!("Admin 用户不存在，请检查数据库初始化");
    }
    tracing::info!("========================================");

    // 5. 构建路由
    let app = Router::new()
        .merge(handlers::routes(state.clone()))
        // Multipart 上传默认会受到 Axum 默认 body limit（约 2MB）影响，
        // 这里关闭默认限制，具体文件大小由业务层 max_file_size_mb 逐文件控制。
        .layer(DefaultBodyLimit::disable())
        .layer(CompressionLayer::new())
        .layer(TraceLayer::new_for_http())
        .layer(TimeoutLayer::with_status_code(
            axum::http::StatusCode::REQUEST_TIMEOUT,
            Duration::from_secs(config.server.timeout_secs),
        ))
        .with_state(state.clone());

    // 7. 启动后台心跳检查任务
    let (shutdown_tx, mut shutdown_rx) = watch::channel(());
    let heartbeat_state = state.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(30));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);

        loop {
            tokio::select! {
                _ = interval.tick() => {
                    let timeout_secs = heartbeat_state.config.agent.heartbeat_timeout_secs;
                    let threshold = chrono::Utc::now() - chrono::Duration::seconds(timeout_secs as i64);

                    // 更新离线服务状态
                    match sqlx::query(
                        "UPDATE services SET agent_status = 'offline', agent_current_load = 0 WHERE agent_status != 'offline' AND agent_last_heartbeat < ?"
                    )
                    .bind(threshold.to_rfc3339())
                    .execute(heartbeat_state.db.pool())
                    .await {
                        Ok(result) => {
                            let rows = result.rows_affected();
                            if rows > 0 {
                                tracing::warn!("{} service(s) marked as offline due to heartbeat timeout", rows);

                                // 任务自动迁移：将 offline 服务的 running 任务改回 pending
                                match migrate_tasks_from_offline_services(&heartbeat_state, threshold.to_rfc3339()).await {
                                    Ok(migrated_count) => {
                                        if migrated_count > 0 {
                                            tracing::info!("{} task(s) migrated back to pending queue", migrated_count);
                                        }
                                    }
                                    Err(e) => {
                                        tracing::error!("Failed to migrate tasks from offline services: {}", e);
                                    }
                                }
                            }
                        }
                        Err(e) => {
                            tracing::error!("Failed to check service heartbeats: {}", e);
                        }
                    }
                }
                _ = shutdown_rx.changed() => {
                    tracing::info!("Heartbeat checker shutting down gracefully...");
                    break;
                }
            }
        }
    });

    // 8. 启动后台任务清理任务
    let cleanup_state = state.clone();
    let retention_days = config.task.result_retention_days;
    let (cleanup_shutdown_tx, mut cleanup_shutdown_rx) = watch::channel(false);
    let cleanup_handle = tokio::spawn(async move {
        // 每天执行一次清理
        let mut interval = tokio::time::interval(Duration::from_secs(24 * 60 * 60));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);

        // 启动时立即执行一次清理
        cleanup_expired_tasks(&cleanup_state, retention_days).await;

        loop {
            tokio::select! {
                _ = interval.tick() => {
                    cleanup_expired_tasks(&cleanup_state, retention_days).await;
                }
                _ = cleanup_shutdown_rx.changed() => {
                    tracing::info!("Cleanup task shutting down gracefully...");
                    break;
                }
            }
        }
    });

    // 9. 启动服务器
    let listener = TcpListener::bind(&config.server_addr()).await?;
    tracing::info!("Server listening on {}", config.server_addr());

    // 优雅关闭
    axum::serve(listener, app)
        .with_graceful_shutdown(async move {
            shutdown_signal().await;
            let _ = shutdown_tx.send(());
            let _ = cleanup_shutdown_tx.send(true);
        })
        .await?;

    // 等待后台任务完成
    cleanup_handle.await.ok();
    tracing::info!("Cleanup task stopped");

    // 删除 pidfile
    remove_pidfile(&config);

    // 关闭数据库连接
    state.db.close().await;
    tracing::info!("Server shutdown complete");

    Ok(())
}

async fn run_detached(config_path: PathBuf) -> anyhow::Result<()> {
    let config = prepare_server_config(&config_path)?;

    if let Some(pid) = check_running(&config)? {
        println!("Server 已在后台运行 (PID: {})", pid);
        return Ok(());
    }

    let exe_path = std::env::current_exe()?;

    // 创建日志文件路径（从 database_url 推断 data_dir）
    let data_dir = database_dir_from_url(&config.database.url)
        .unwrap_or_else(|| PathBuf::from("./data"));
    let log_path = data_dir.join("server.log");
    if let Some(parent) = log_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    #[cfg(unix)]
    {
        use std::fs::File;
        use std::process::Stdio;

        let log_file = File::create(&log_path)?;
        let child = std::process::Command::new("nohup")
            .arg(&exe_path)
            .arg("--config")
            .arg(&config_path)
            .arg("run")
            .stdout(Stdio::from(log_file.try_clone()?))
            .stderr(Stdio::from(log_file))
            .stdin(Stdio::null())
            .spawn()?;

        println!("Server 已在后台启动 (PID: {})", child.id());
        println!("查看日志: tail -f {}", log_path.display());
    }

    #[cfg(not(unix))]
    {
        use std::fs::File;
        use std::process::Stdio;

        let log_file = File::create(&log_path)?;
        let _ = std::process::Command::new("cmd")
            .args(&["/C", "start", "/B", ""])
            .arg(&exe_path)
            .arg("--config")
            .arg(&config_path)
            .arg("run")
            .stdout(Stdio::from(log_file.try_clone()?))
            .stderr(Stdio::from(log_file))
            .spawn()?;

        println!("Server 已在后台启动");
        println!("查看日志: {}", log_path.display());
    }

    Ok(())
}

async fn stop(config_path: PathBuf) -> anyhow::Result<()> {
    let pidfile = match load_config_from_path(&config_path) {
        Ok(config) => pidfile_path(&config),
        Err(_) => PathBuf::from("./data/server.pid"),
    };

    if !pidfile.exists() {
        println!("Server 未在运行");
        return Ok(());
    }

    let pid_str = std::fs::read_to_string(&pidfile)?;
    let pid = match pid_str.trim().parse::<u32>() {
        Ok(p) if p > 0 => p,
        _ => {
            let _ = std::fs::remove_file(&pidfile);
            println!("Server 未在运行 (pidfile 已清理)");
            return Ok(());
        }
    };

    #[cfg(unix)]
    {
        use std::process::Stdio;

        // 检查进程是否存在
        let output = std::process::Command::new("kill")
            .args(&["-0", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .output()?;

        if !output.status.success() {
            println!("Server 未在运行 (PID: {} 已不存在)", pid);
            let _ = std::fs::remove_file(&pidfile);
            return Ok(());
        }

        // 发送优雅关闭信号
        let output = std::process::Command::new("kill")
            .args(&["-TERM", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .output()?;

        if !output.status.success() {
            // 竞态：进程可能在 kill -0 和 kill -TERM 之间退出
            let check = std::process::Command::new("kill")
                .args(&["-0", &pid.to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .output()?;
            if !check.status.success() {
                println!("Server 已停止 (PID: {} 已退出)", pid);
                let _ = std::fs::remove_file(&pidfile);
                return Ok(());
            }
            anyhow::bail!("停止 Server 失败");
        }

        println!("正在停止 Server (PID: {})...", pid);

        // 等待进程退出（轮询最多 5 秒）
        let mut stopped = false;
        for _ in 0..50 {
            tokio::time::sleep(Duration::from_millis(100)).await;
            let output = std::process::Command::new("kill")
                .args(&["-0", &pid.to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .output()?;
            if !output.status.success() {
                stopped = true;
                break;
            }
        }

        if !stopped {
            println!("优雅关闭超时，强制终止 (PID: {})...", pid);
            let output = std::process::Command::new("kill")
                .args(&["-KILL", &pid.to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .output()?;
            if !output.status.success() {
                // 确认进程是否真的不存在了
                let check = std::process::Command::new("kill")
                    .args(&["-0", &pid.to_string()])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .output()?;
                if check.status.success() {
                    anyhow::bail!("强制终止 Server 失败");
                }
            }
        }

        // 最后再确认进程不存在，才删除 pidfile
        let check = std::process::Command::new("kill")
            .args(&["-0", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .output()?;
        if !check.status.success() {
            let _ = std::fs::remove_file(&pidfile);
            println!("Server 已停止");
        } else {
            anyhow::bail!("Server 停止后进程仍存在");
        }
    }

    #[cfg(not(unix))]
    {
        let _ = std::process::Command::new("taskkill")
            .args(&["/PID", &pid.to_string(), "/F"])
            .output()?;
        let _ = std::fs::remove_file(&pidfile);
        println!("Server 已停止");
    }

    Ok(())
}

async fn status(config_path: PathBuf) -> anyhow::Result<()> {
    let (pidfile, data_dir, addr) = match load_config_from_path(&config_path) {
        Ok(config) => {
            let pidfile = pidfile_path(&config);
            let data_dir = database_dir_from_url(&config.database.url)
                .unwrap_or_else(|| PathBuf::from("./data"));
            let addr = config.server_addr().to_string();
            (pidfile, data_dir, addr)
        }
        Err(_) => {
            let default_pidfile = PathBuf::from("./data/server.pid");
            (default_pidfile, PathBuf::from("./data"), "unknown".to_string())
        }
    };

    let running = if pidfile.exists() {
        let pid_str = std::fs::read_to_string(&pidfile).unwrap_or_default();
        let pid = match pid_str.trim().parse::<u32>() {
            Ok(p) if p > 0 => p,
            _ => {
                let _ = std::fs::remove_file(&pidfile);
                println!("运行状态: 未运行");
                return Ok(());
            }
        };

        #[cfg(unix)]
        {
            use std::process::Stdio;
            let output = std::process::Command::new("kill")
                .args(&["-0", &pid.to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .output()?;
            if output.status.success() {
                Some(pid)
            } else {
                None
            }
        }

        #[cfg(not(unix))]
        {
            Some(pid)
        }
    } else {
        None
    };

    println!("OpenAaaS Server 状态");
    println!("====================");
    println!("配置文件: {}", config_path.display());
    println!("数据目录: {}", data_dir.display());
    println!("监听地址: {}", addr);
    println!();
    if let Some(pid) = running {
        println!("运行状态: 运行中 (PID: {})", pid);
    } else {
        println!("运行状态: 未运行");
    }

    Ok(())
}

fn pidfile_path(config: &AppConfig) -> PathBuf {
    database_dir_from_url(&config.database.url)
        .unwrap_or_else(|| PathBuf::from("./data"))
        .join("server.pid")
}

fn check_running(config: &AppConfig) -> anyhow::Result<Option<u32>> {
    let pidfile = pidfile_path(config);
    if !pidfile.exists() {
        return Ok(None);
    }

    let pid_str = std::fs::read_to_string(&pidfile)?;
    let pid = match pid_str.trim().parse::<u32>() {
        Ok(p) if p > 0 => p,
        _ => {
            let _ = std::fs::remove_file(&pidfile);
            return Ok(None);
        }
    };

    #[cfg(unix)]
    {
        use std::process::Stdio;
        let output = std::process::Command::new("kill")
            .args(&["-0", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .output()?;

        if output.status.success() {
            return Ok(Some(pid));
        } else {
            let _ = std::fs::remove_file(&pidfile);
            return Ok(None);
        }
    }

    #[cfg(not(unix))]
    {
        Ok(Some(pid))
    }
}

fn write_pidfile(config: &AppConfig) -> anyhow::Result<()> {
    let pidfile = pidfile_path(config);
    if let Some(parent) = pidfile.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let pid = std::process::id();
    std::fs::write(&pidfile, pid.to_string())?;
    Ok(())
}

fn remove_pidfile(config: &AppConfig) {
    let _ = std::fs::remove_file(pidfile_path(config));
}

fn runtime_admin_api_key(config: &AppConfig) -> Option<String> {
    std::env::var("ADMIN_API_KEY")
        .ok()
        .filter(|value| !is_blank(value))
        .or_else(|| {
            config
                .admin_api_key
                .clone()
                .filter(|value| !is_blank(value))
        })
}

fn apply_server_data_dir(config: &mut AppConfig, data_dir: &str) {
    let data_path = std::path::PathBuf::from(data_dir);
    let db_path = data_path.join("app.db");
    let path_str = db_path.to_str().expect("data dir path should be valid UTF-8").replace('\\', "/");
    config.database.url = if db_path.is_absolute() {
        format!("sqlite:///{}", path_str)
    } else {
        format!("sqlite:{}", path_str)
    };
    config.task.file_storage_path = data_path
        .join("files")
        .to_str()
        .expect("data dir path should be valid UTF-8")
        .to_string();
}

fn choose_server_data_dir(interactive: bool, default_dir: &str) -> anyhow::Result<String> {
    if !interactive {
        return Ok(default_dir.to_string());
    }

    eprintln!();
    eprintln!("--- Data Directory ---");
    eprintln!("Purpose: stores the server SQLite database and runtime files.");
    eprintln!("Default: {default_dir}");
    eprintln!();

    if prompt_yes_no("Use the default data directory?", true)? {
        return Ok(default_dir.to_string());
    }

    loop {
        let value = prompt_raw("Enter custom data directory", None)?;
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Ok(trimmed.to_string());
        }
        eprintln!("Data directory cannot be empty.");
    }
}

fn ensure_server_runtime_dirs(config: &AppConfig) -> anyhow::Result<()> {
    if let Some(data_dir) = database_dir_from_url(&config.database.url) {
        std::fs::create_dir_all(&data_dir)
            .with_context(|| format!("创建数据目录失败: {}", data_dir.display()))?;
    }

    if !is_blank(&config.task.file_storage_path) {
        std::fs::create_dir_all(&config.task.file_storage_path)
            .with_context(|| format!("创建文件目录失败: {}", config.task.file_storage_path))?;
    }

    Ok(())
}

fn database_dir_from_url(url: &str) -> Option<PathBuf> {
    let path = url.strip_prefix("sqlite:")?;
    // 处理三斜杠绝对路径格式: sqlite:///C:/path → C:/path
    let path = path.strip_prefix("///").unwrap_or(path);
    let path = path.split(&['?', '#']).next().unwrap_or(path);
    let db_path = PathBuf::from(path);
    db_path.parent().map(PathBuf::from)
}

fn secret_needs_generation(value: Option<&str>) -> bool {
    match value {
        Some(secret) => {
            let trimmed = secret.trim();
            trimmed.is_empty() || trimmed == "change-me-in-production"
        }
        None => true,
    }
}

fn is_blank(value: &str) -> bool {
    value.trim().is_empty()
}

fn is_blank_option(value: Option<&str>) -> bool {
    value.is_none_or(is_blank)
}

fn generate_secret() -> String {
    format!(
        "{}{}",
        Uuid::new_v4().simple(),
        Uuid::new_v4().simple()
    )
}

fn prompt_with_default(label: &str, default: &str, help: &str) -> anyhow::Result<String> {
    eprintln!();
    eprintln!("{label}: {help}");
    let value = prompt_raw(label, Some(default))?;
    let trimmed = value.trim();
    if trimmed.is_empty() {
        Ok(default.to_string())
    } else {
        Ok(trimmed.to_string())
    }
}

fn prompt_yes_no(label: &str, default_yes: bool) -> anyhow::Result<bool> {
    let default = if default_yes { "Y" } else { "N" };
    loop {
        let value = prompt_raw(label, Some(default))?;
        let normalized = if value.trim().is_empty() {
            default.to_string()
        } else {
            value.trim().to_string()
        };

        match normalized.as_str() {
            "Y" | "y" | "yes" | "YES" => return Ok(true),
            "N" | "n" | "no" | "NO" => return Ok(false),
            _ => eprintln!("Please enter Y or N."),
        }
    }
}

fn prompt_raw(label: &str, default: Option<&str>) -> anyhow::Result<String> {
    let mut stdout = io::stdout();
    match default {
        Some(default) => write!(stdout, "{label} [{default}]: ")?,
        None => write!(stdout, "{label}: ")?,
    }
    stdout.flush()?;

    let mut input = String::new();
    io::stdin().read_line(&mut input)?;
    Ok(input.trim_end_matches(['\n', '\r']).to_string())
}

/// 优雅关闭信号处理
async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {
            tracing::info!("Received Ctrl+C, shutting down gracefully...");
        }
        _ = terminate => {
            tracing::info!("Received SIGTERM, shutting down gracefully...");
        }
    }
}

/// 将 offline 服务的活跃任务收敛到终态或重新排队
/// - running: 改回 pending（或重试超限后 failed）
/// - cancelling: 直接标记为 cancelled，避免永久卡住
async fn migrate_tasks_from_offline_services(
    state: &AppState,
    threshold: String,
) -> anyhow::Result<u64> {
    use open_aaas_server::models::task::Task;

    // 1. 查询需要迁移的任务
    let tasks_to_migrate: Vec<Task> = sqlx::query_as::<_, Task>(
        r#"
        SELECT * FROM tasks 
        WHERE service_id IN (
            SELECT id FROM services 
            WHERE agent_status = 'offline' AND agent_last_heartbeat < ?
        ) AND status IN ('running', 'cancelling')
        "#,
    )
    .bind(&threshold)
    .fetch_all(state.db.pool())
    .await?;

    let mut migrated_count = 0u64;
    let mut failed_count = 0u64;
    let mut cancelled_count = 0u64;
    let now = chrono::Utc::now();

    for task in tasks_to_migrate {
        if task.status == open_aaas_server::models::task::TaskStatus::Cancelling {
            sqlx::query(
                r#"
                UPDATE tasks
                SET status = 'cancelled', error_message = ?, completed_at = ?
                WHERE id = ?
                "#,
            )
            .bind("Agent 离线，任务取消完成")
            .bind(now.to_rfc3339())
            .bind(&task.id)
            .execute(state.db.pool())
            .await?;

            cancelled_count += 1;
            continue;
        }

        if task.retry_count >= 3 {
            // 重试次数超限，标记为失败
            sqlx::query(
                r#"
                UPDATE tasks 
                SET status = 'failed', error_message = ?, completed_at = ?
                WHERE id = ?
                "#,
            )
            .bind("任务重试次数超过上限，无可用服务")
            .bind(now.to_rfc3339())
            .bind(&task.id)
            .execute(state.db.pool())
            .await?;

            failed_count += 1;
        } else {
            // 重试次数未超限，改回 pending 并增加计数
            sqlx::query(
                r#"
                UPDATE tasks 
                SET status = 'pending', assigned_at = NULL, started_at = NULL, retry_count = retry_count + 1
                WHERE id = ?
                "#
            )
            .bind(&task.id)
            .execute(state.db.pool())
            .await?;

            migrated_count += 1;
        }
    }

    if failed_count > 0 {
        tracing::warn!(
            "{} task(s) marked as failed due to retry limit exceeded",
            failed_count
        );
    }
    if cancelled_count > 0 {
        tracing::info!(
            "{} cancelling task(s) finalized as cancelled after agent offline",
            cancelled_count
        );
    }

    Ok(migrated_count + cancelled_count)
}

/// 清理过期任务
/// 删除 completed/failed/cancelled 状态且超过保留期限的任务
async fn cleanup_expired_tasks(state: &AppState, retention_days: i64) {
    if retention_days <= 0 {
        tracing::debug!("Task cleanup skipped: retention_days is {}", retention_days);
        return;
    }

    let cutoff_date = chrono::Utc::now() - chrono::Duration::days(retention_days);

    // 先获取要删除的任务ID列表（用于后续清理文件）
    let tasks_to_delete: Vec<String> = sqlx::query_scalar(
        r#"
        SELECT id FROM tasks 
        WHERE status IN ('completed', 'failed', 'cancelled') 
        AND completed_at < ?
        "#,
    )
    .bind(cutoff_date.to_rfc3339())
    .fetch_all(state.db.pool())
    .await
    .unwrap_or_default();

    // 清理这些任务的文件
    for task_id in &tasks_to_delete {
        if let Err(e) = cleanup_task_files(state, task_id).await {
            tracing::error!("Failed to cleanup files for task {}: {}", task_id, e);
        }
    }

    match sqlx::query(
        r#"
        DELETE FROM tasks 
        WHERE status IN ('completed', 'failed', 'cancelled') 
        AND completed_at < ?
        "#,
    )
    .bind(cutoff_date.to_rfc3339())
    .execute(state.db.pool())
    .await
    {
        Ok(result) => {
            let deleted = result.rows_affected();
            if deleted > 0 {
                tracing::info!(
                    "Cleaned up {} expired task(s) older than {} days",
                    deleted,
                    retention_days
                );
            } else {
                tracing::debug!(
                    "No expired tasks to cleanup (retention: {} days)",
                    retention_days
                );
            }
        }
        Err(e) => {
            tracing::error!("Failed to cleanup expired tasks: {}", e);
        }
    }
}

/// 清理任务的文件
/// 删除数据库记录和对应的磁盘文件
async fn cleanup_task_files(state: &AppState, task_id: &str) -> anyhow::Result<()> {
    use open_aaas_server::models::file::TaskFile;

    // 查询该任务的所有文件
    let files: Vec<TaskFile> = sqlx::query_as("SELECT * FROM task_files WHERE task_id = ?")
        .bind(task_id)
        .fetch_all(state.db.pool())
        .await?;

    let storage_path = state.file_storage_path();
    let mut deleted_count = 0;
    let mut failed_count = 0;

    for file in files {
        let full_path = match file.full_storage_path(storage_path) {
            Ok(path) => path,
            Err(e) => {
                tracing::warn!("Invalid file path for file {}: {}", file.id, e);
                failed_count += 1;
                continue;
            }
        };

        // 删除磁盘文件（如果存在）
        if full_path.exists() {
            match tokio::fs::remove_file(&full_path).await {
                Ok(_) => {
                    deleted_count += 1;
                    tracing::debug!("Deleted file: {}", full_path.display());
                }
                Err(e) => {
                    failed_count += 1;
                    tracing::warn!("Failed to delete file {}: {}", full_path.display(), e);
                }
            }
        }
    }

    // 删除空目录（任务目录）
    let task_dir = std::path::PathBuf::from(storage_path).join(task_id);
    if task_dir.exists() {
        match tokio::fs::remove_dir(&task_dir).await {
            Ok(_) => tracing::debug!("Deleted task directory: {}", task_dir.display()),
            Err(e) => tracing::debug!(
                "Failed to delete task directory {} (may not be empty): {}",
                task_dir.display(),
                e
            ),
        }
    }

    if deleted_count > 0 || failed_count > 0 {
        tracing::info!(
            "Task {} file cleanup: {} deleted, {} failed",
            task_id,
            deleted_count,
            failed_count
        );
    }

    Ok(())
}

//! OpenAaaS Agent Core - 主入口

use agent_core::client::ApiClient;
use agent_core::config::Config;
use agent_core::executor::docker::DockerExecutor;
use agent_core::executor::Executor;
use agent_core::scheduler::{Scheduler, SchedulerCommand};
use agent_core::state::StateManager;
use clap::{Parser, Subcommand};
use std::fs;
use std::io::{self, IsTerminal, Write};
use std::path::{Path, PathBuf};
use std::process::Command as StdCommand;
use std::time::Duration;

use anyhow::Context;
use tokio::signal;
use tracing::{error, info, warn};
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;

const AGENT_LONG_ABOUT: &str = "OpenAaaS Agent Core - Agent 执行节点\n\n连接 OpenAaaS Server，注册本机服务能力，轮询任务，并通过 Docker 执行任务。";
const AGENT_AFTER_HELP: &str = "首次使用:\n  agent-core init\n  编辑 config.toml 中的 server.base_url\n  agent-core register --token <TOKEN> --name my-agent\n  agent-core run\n\n默认值:\n  配置文件: ./config.toml\n  数据目录: ./data\n  Server 地址: http://127.0.0.1:8080\n  Executor 镜像: open-aaas-executor:latest";
const AGENT_INIT_AFTER_HELP: &str = "生成后通常需要:\n  1. 编辑 server.base_url\n  2. 运行 agent-core register --token <TOKEN>\n  3. 运行 agent-core run";
const AGENT_RUN_AFTER_HELP: &str = "启动前请确认:\n  Server 已启动\n  config.toml 中的 server.base_url 正确\n  Agent 已注册，或使用 --interactive 交互注册";
const AGENT_DETACHED_AFTER_HELP: &str = "输出位置:\n  pidfile: 数据目录/agent.pid\n  日志: 数据目录/agent.log";
const AGENT_INIT_LONG_ABOUT: &str = "生成 Agent Core 默认配置文件；只创建 config.toml，不注册 Agent，也不启动调度器。";
const AGENT_REGISTER_LONG_ABOUT: &str = "向 OpenAaaS Server 注册 Agent；成功后会把 service_id 和 api_key 写入 config.toml，token 需要从 Server 管理端获取。";
const AGENT_RUN_LONG_ABOUT: &str = "前台启动 Agent 调度器；启动后连接 Server、发送心跳、轮询任务，并通过 Docker 执行任务。";
const AGENT_DETACHED_LONG_ABOUT: &str = "后台启动 Agent 调度器；适合长期运行，日志和 pidfile 默认写入数据目录。";
const AGENT_STATUS_LONG_ABOUT: &str = "查看 Agent Core 状态；显示配置文件、数据目录、Server 地址、注册状态和执行器配置。";
const AGENT_STOP_LONG_ABOUT: &str = "停止后台运行的 Agent Core；根据 pidfile 查找进程并发送停止信号。";

#[derive(Parser)]
#[command(name = "agent-core")]
#[command(about = "OpenAaaS Agent Core - Agent 调度与执行")]
#[command(long_about = AGENT_LONG_ABOUT)]
#[command(after_help = AGENT_AFTER_HELP)]
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
    /// 生成默认配置文件
    #[command(long_about = AGENT_INIT_LONG_ABOUT)]
    #[command(after_help = AGENT_INIT_AFTER_HELP)]
    Init,
    /// 向 Server 注册 Agent
    #[command(long_about = AGENT_REGISTER_LONG_ABOUT)]
    Register {
        /// 注册令牌，例如 rt_xxx
        #[arg(short, long)]
        token: Option<String>,
        /// Agent 名称，默认 agent-core
        #[arg(short, long)]
        name: Option<String>,
    },
    /// 前台启动 Agent 调度器
    #[command(long_about = AGENT_RUN_LONG_ABOUT)]
    #[command(after_help = AGENT_RUN_AFTER_HELP)]
    Run {
        /// 未注册时交互输入 token 并完成注册
        #[arg(long)]
        interactive: bool,
    },
    /// 后台启动 Agent 调度器
    #[command(name = "run-detached")]
    #[command(long_about = AGENT_DETACHED_LONG_ABOUT)]
    #[command(after_help = AGENT_DETACHED_AFTER_HELP)]
    RunDetached,
    /// 查看 Agent 状态
    #[command(long_about = AGENT_STATUS_LONG_ABOUT)]
    Status,
    /// 停止后台 Agent
    #[command(long_about = AGENT_STOP_LONG_ABOUT)]
    Stop,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 初始化日志
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "agent_core=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let cli = Cli::parse();
    let config_path = cli.config.unwrap_or_else(Config::config_path);

    match cli.command {
        Commands::Run { interactive } => run_foreground(config_path, interactive).await,
        Commands::RunDetached => run_detached(config_path).await,
        Commands::Stop => stop(config_path).await,
        Commands::Status => status(config_path).await,
        Commands::Init => init(config_path).await,
        Commands::Register { token, name } => register(config_path, token, name).await,
    }
}

async fn run_foreground(config_path: PathBuf, interactive: bool) -> anyhow::Result<()> {
    info!("启动前台模式");

    // 加载配置
    let mut config = ensure_agent_runtime_config(&config_path).await?;
    info!("配置加载完成: data_dir={:?}", config.data_dir());

    // 检查是否已有实例在运行
    if let Some(pid) = check_running(&config)? {
        anyhow::bail!(
            "Agent 已在运行 (PID: {})，请先停止或运行 `agent-core stop`",
            pid
        );
    }

    // 检查 Server 端口是否可达
    let server_url = &config.server.base_url;
    info!("检查 Server 连接: {}", server_url);
    match check_server_available(server_url).await {
        Ok(true) => info!("Server 连接正常"),
        Ok(false) => {
            warn!("无法连接到 Server: {}", server_url);
            warn!("请检查:");
            warn!("  1. Server 是否已启动");
            warn!("  2. 配置文件中的 server.base_url 是否正确");
            warn!("  3. 网络连接是否正常");
            // 不强制退出，允许离线启动（如果设计支持）
        }
        Err(e) => {
            warn!("检查 Server 连接时出错: {}", e);
        }
    }

    // 确保挂载目录存在
    config.ensure_mount_dirs().await?;

    // 获取 docker 挂载参数
    let docker_mounts = config.docker_mounts();
    info!("Docker 挂载: {:?}", docker_mounts);

    // 检查是否已注册
    if !config.agent.has_credentials() {
        if interactive || is_interactive_terminal() {
            let token = prompt_registration_token()?;
            let name = config.agent.name.clone();
            register(config_path.clone(), Some(token), name).await?;
            println!("继续启动 agent-core...");
            config = Config::load_from_path(&config_path).await?;
        } else {
            anyhow::bail!("Agent 未注册，请先运行: agent-core register --token <TOKEN>");
        }
    }

    let pidfile = pidfile_path(&config);

    // 写入 pidfile
    write_pidfile(&config)?;
    info!("pidfile 已写入: {:?}", pidfile);

    // 创建 API 客户端
    let mut client = ApiClient::new(&config.server);
    client.set_auth(
        config.agent.api_key.clone().unwrap(),
        config.agent.service_id.clone().unwrap(),
    );

    // 初始化状态管理
    let state = StateManager::init(config.database_path()).await?;
    info!("状态管理器初始化完成");

    // 创建执行器
    let executor = DockerExecutor::new(config.executor.clone(), config.data_dir());
    info!("Docker 执行器创建完成，容量: {}", executor.capacity());

    // 创建调度器
    let scheduler = Scheduler::new(config, client, executor, state);
    println!("agent-core 已启动，正在轮询 server 等待任务...");

    // 优雅退出处理
    let scheduler_clone = scheduler.command_sender();
    tokio::spawn(async move {
        #[cfg(unix)]
        {
            let mut sigint = signal::unix::signal(signal::unix::SignalKind::interrupt()).ok();
            let mut sigterm = signal::unix::signal(signal::unix::SignalKind::terminate()).ok();

            tokio::select! {
                _ = async { sigint.as_mut()?.recv().await }, if sigint.is_some() => {}
                _ = async { sigterm.as_mut()?.recv().await }, if sigterm.is_some() => {}
                _ = signal::ctrl_c() => {}
            }
        }
        #[cfg(not(unix))]
        {
            let _ = signal::ctrl_c().await;
        }

        info!("收到退出信号，正在优雅停止...");
        let _ = scheduler_clone.send(SchedulerCommand::Stop).await;
    });

    // 运行调度器
    scheduler.run().await?;

    // 删除 pidfile
    let _ = fs::remove_file(&pidfile);
    info!("pidfile 已删除");

    info!("Agent 已停止");
    Ok(())
}

/// 获取 pidfile 路径
fn pidfile_path(config: &Config) -> PathBuf {
    config.data_dir().join("agent.pid")
}

/// 检查是否已有实例在运行
fn check_running(config: &Config) -> anyhow::Result<Option<u32>> {
    let pidfile = pidfile_path(config);
    if !pidfile.exists() {
        return Ok(None);
    }

    let pid_str = fs::read_to_string(&pidfile)?;
    let pid: u32 = pid_str.trim().parse()?;

    // 检查进程是否存在
    #[cfg(unix)]
    {
        use std::process::Stdio;
        let output = StdCommand::new("kill")
            .args(["-0", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .output()?;

        if output.status.success() {
            return Ok(Some(pid));
        }
    }

    // 进程不存在，删除过期 pidfile
    let _ = fs::remove_file(&pidfile);
    Ok(None)
}

/// 写入 pidfile
fn write_pidfile(config: &Config) -> anyhow::Result<()> {
    let pidfile = pidfile_path(config);
    if let Some(parent) = pidfile.parent() {
        fs::create_dir_all(parent)?;
    }
    let pid = std::process::id();
    fs::write(&pidfile, pid.to_string())?;
    Ok(())
}

/// 删除 pidfile
fn remove_pidfile(config: &Config) {
    let _ = fs::remove_file(pidfile_path(config));
}

async fn run_detached(config_path: PathBuf) -> anyhow::Result<()> {
    let config = ensure_agent_runtime_config(&config_path).await?;

    // 检查是否已有实例在运行
    if let Some(pid) = check_running(&config)? {
        println!("Agent 已在后台运行 (PID: {})", pid);
        return Ok(());
    }

    info!("启动后台模式...");

    // 获取当前可执行文件路径
    let exe_path = std::env::current_exe()?;

    // 创建日志文件路径
    let log_path = config.data_dir().join("agent.log");
    if let Some(parent) = log_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    #[cfg(unix)]
    {
        use std::fs::File;
        use std::process::Stdio;

        let log_file = File::create(&log_path)?;
        let child = StdCommand::new("nohup")
            .arg(&exe_path)
            .arg("--config")
            .arg(&config_path)
            .arg("run")
            .stdout(Stdio::from(log_file.try_clone()?))
            .stderr(Stdio::from(log_file))
            .stdin(Stdio::null())
            .spawn()?;

        println!("Agent 已在后台启动 (PID: {})", child.id());
        println!("查看日志: tail -f {}", log_path.display());
    }

    #[cfg(not(unix))]
    {
        use std::fs::File;
        use std::process::Stdio;

        let log_file = File::create(&log_path)?;
        let _ = StdCommand::new("cmd")
            .args(["/C", "start", "/B", ""])
            .arg(&exe_path)
            .arg("--config")
            .arg(&config_path)
            .arg("run")
            .stdout(Stdio::from(log_file.try_clone()?))
            .stderr(Stdio::from(log_file))
            .spawn()?;

        println!("Agent 已在后台启动");
        println!("查看日志: {}", log_path.display());
    }

    Ok(())
}

async fn stop(config_path: PathBuf) -> anyhow::Result<()> {
    let config = Config::load_from_path(&config_path).await?;

    match check_running(&config)? {
        Some(pid) => {
            info!("停止 Agent (PID: {})...", pid);

            #[cfg(unix)]
            {
                use std::process::Stdio;
                let output = StdCommand::new("kill")
                    .args(["-TERM", &pid.to_string()])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .output()?;

                if output.status.success() {
                    println!("Agent 已停止 (PID: {})", pid);
                    // 等待进程退出
                    for _ in 0..10 {
                        tokio::time::sleep(Duration::from_millis(500)).await;
                        if check_running(&config)?.is_none() {
                            break;
                        }
                    }
                    // 强制清理 pidfile
                    remove_pidfile(&config);
                } else {
                    println!("停止 Agent 失败");
                }
            }

            #[cfg(not(unix))]
            {
                // Windows: 使用 taskkill
                let _ = StdCommand::new("taskkill")
                    .args(["/PID", &pid.to_string(), "/F"])
                    .output()?;
                println!("Agent 已停止");
            }
        }
        None => {
            println!("Agent 未在运行");
        }
    }

    Ok(())
}

async fn status(config_path: PathBuf) -> anyhow::Result<()> {
    // 加载配置
    let config = Config::load_from_path(&config_path).await?;

    println!("OpenAaaS Agent 状态");
    println!("====================");
    println!("配置文件: {:?}", config_path);
    println!("数据目录: {:?}", config.data_dir());
    println!();
    println!("Server URL: {}", config.server.base_url);
    println!("轮询间隔: {} 秒", config.server.poll_interval_secs);
    println!();

    if let Some(ref service_id) = config.agent.service_id {
        println!("注册状态: 已注册");
        println!("Service ID: {}", service_id);
    } else {
        println!("注册状态: 未注册");
        println!("运行: agent-core register --token <TOKEN>");
    }

    if let Some(ref name) = config.agent.name {
        println!("Agent 名称: {}", name);
    }

    println!();
    println!("执行器配置:");
    println!("  镜像: {}", config.executor.image);
    println!("  容量: {}", config.executor.capacity);
    println!("  超时: {} 分钟", config.executor.timeout_minutes);

    Ok(())
}

async fn init(config_path: PathBuf) -> anyhow::Result<()> {
    info!("初始化配置...");
    let config = Config::default();
    config.save_to_path(&config_path).await?;
    info!("配置已保存到: {:?}", config_path);
    println!("配置文件已创建: {:?}", config_path);
    println!("可直接运行 agent-core run，缺少的启动信息会在终端提示录入");
    Ok(())
}

/// 检查 Server 是否可达
async fn check_server_available(url: &str) -> anyhow::Result<bool> {
    // 解析 URL 获取 host 和 port
    let parsed = reqwest::Url::parse(url).context("解析 Server URL 失败")?;

    let host = parsed.host_str().context("URL 中缺少 host")?;
    let port = parsed.port_or_known_default().unwrap_or(8080);

    // 尝试 TCP 连接
    match tokio::net::TcpStream::connect((host, port)).await {
        Ok(_) => Ok(true),
        Err(e) if e.kind() == std::io::ErrorKind::ConnectionRefused => Ok(false),
        Err(e) => Err(anyhow::anyhow!("连接检查失败: {}", e)),
    }
}

async fn register(
    config_path: PathBuf,
    token: Option<String>,
    name: Option<String>,
) -> anyhow::Result<()> {
    info!("========================================");
    info!("开始注册流程...");
    info!("========================================");

    // 加载配置
    info!("步骤 1: 加载配置...");
    let mut config = Config::load_from_path(&config_path).await?;
    info!("配置加载成功: base_url={}", config.server.base_url);

    // 检查是否已注册
    info!("步骤 2: 检查是否已注册...");
    if config.agent.has_credentials() {
        println!(
            "Agent 已注册: {}",
            config.agent.service_id.as_ref().unwrap()
        );
        println!("如需重新注册，请删除配置文件后重试");
        return Ok(());
    }
    info!("未注册，继续...");

    // 设置名称
    if let Some(name) = name {
        config.agent.name = Some(name);
    } else if config
        .agent
        .name
        .as_deref()
        .is_none_or(|value| value.trim().is_empty())
    {
        config.agent.name = Some("agent-core".to_string());
    }

    let token = match token {
        Some(token) => token,
        None if is_interactive_terminal() => prompt_registration_token()?,
        None => anyhow::bail!("缺少注册令牌，请使用 agent-core register --token <TOKEN>"),
    };

    // 创建客户端
    info!("步骤 3: 创建 API 客户端...");
    let mut client = ApiClient::new(&config.server);
    info!("API 客户端创建成功");

    // 调用注册
    info!("步骤 4: 调用 client.register()...");
    match client.register(&token, config.executor.capacity).await {
        Ok(response) => {
            info!("注册成功: service_id={}", response.service_id);

            // 保存配置
            config.agent.api_key = Some(response.api_key);
            config.agent.service_id = Some(response.service_id);
            config.save_to_path(&config_path).await?;

            println!("注册成功！");
            println!("Service ID: {}", config.agent.service_id.as_ref().unwrap());
            println!(
                "API Key: {}...",
                &config.agent.api_key.as_ref().unwrap()[..20]
            );
            println!("配置已保存");
        }
        Err(e) => {
            error!("注册失败: {}", e);
            eprintln!("注册失败！");
            eprintln!("==============");
            eprintln!("{}", e);
            eprintln!();
            eprintln!("常见问题:");
            eprintln!("1. Server 地址配置错误: 检查 config.toml 中的 server.base_url");
            eprintln!("2. 注册令牌过期: 联系管理员获取新的 registration_token");
            eprintln!(
                "3. Server 未运行: 确保 Server 在 {} 上监听",
                config.server.base_url
            );
            std::process::exit(1);
        }
    }

    Ok(())
}

async fn ensure_agent_runtime_config(config_path: &Path) -> anyhow::Result<Config> {
    let config_exists = config_path.exists();
    let mut config = Config::load_from_path(config_path).await?;
    let interactive = is_interactive_terminal();
    let mut changed = false;
    let should_confirm_server_url = interactive && !config_exists;

    if config.server.base_url.trim().is_empty() {
        config.server.base_url = "http://127.0.0.1:8080".to_string();
        changed = true;
    } else {
        let normalized = normalize_server_url(&config.server.base_url);
        if normalized != config.server.base_url {
            config.server.base_url = normalized;
            changed = true;
        }
    }

    if should_confirm_server_url || config.server.base_url.trim().is_empty() {
        let selected = prompt_server_url(&config.server.base_url)?;
        if selected != config.server.base_url {
            config.server.base_url = selected;
            changed = true;
        }
    }

    if config.paths.data_dir.is_none() {
        config.paths.data_dir = Some(if interactive {
            choose_agent_data_dir("./data")?
        } else {
            PathBuf::from("./data")
        });
        changed = true;
    }

    if config
        .agent
        .name
        .as_deref()
        .is_none_or(|value| value.trim().is_empty())
    {
        config.agent.name = Some("agent-core".to_string());
        changed = true;
    }

    let is_first_startup = interactive && !config_exists;

    if is_first_startup {
        let image = prompt_executor_image(&config.executor.image)?;
        if image != config.executor.image {
            config.executor.image = image;
            changed = true;
        }

        let capacity = prompt_executor_capacity(config.executor.capacity)?;
        if capacity != config.executor.capacity {
            config.executor.capacity = capacity;
            changed = true;
        }
    }

    if changed {
        config.save_to_path(config_path).await?;
    }

    Ok(config)
}

fn is_interactive_terminal() -> bool {
    io::stdin().is_terminal() && io::stdout().is_terminal()
}

fn prompt_registration_token() -> anyhow::Result<String> {
    println!();
    println!("--- Registration Token ---");
    println!("Purpose: one-time token generated by the server when creating a service.");
    println!("It is used only for first registration and is not saved by this prompt.");
    println!();

    loop {
        let token = prompt_raw("Registration token", None)?;
        let trimmed = token.trim().to_string();
        if trimmed.starts_with("rt_") {
            return Ok(trimmed);
        }
        eprintln!("Registration token should start with rt_.");
    }
}

fn prompt_server_url(default: &str) -> anyhow::Result<String> {
    println!();
    println!("--- Server URL ---");
    println!(
        "Purpose: the HTTP address of the OpenAaaS server that this agent-core will connect to."
    );
    println!("Ask the server administrator for this value.");
    println!("Default: {default}");
    println!();

    loop {
        let value = prompt_raw("Server URL", Some(default))?;
        let raw = if value.trim().is_empty() {
            default
        } else {
            value.trim()
        };
        let normalized = normalize_server_url(raw);
        if validate_server_url(&normalized) {
            return Ok(normalized);
        }
        eprintln!("Invalid Server URL. Use a full URL such as https://www.open-aaas.com or http://127.0.0.1:8080.");
    }
}

fn choose_agent_data_dir(default_dir: &str) -> anyhow::Result<PathBuf> {
    println!();
    println!("--- Data Directory ---");
    println!("Purpose: stores agent-core local state, pid/log runtime files, and task workspaces.");
    println!("Default: {default_dir}");
    println!();

    if prompt_yes_no("Use the default data directory?", true)? {
        return Ok(PathBuf::from(default_dir));
    }

    loop {
        let value = prompt_raw("Enter custom data directory", None)?;
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Ok(PathBuf::from(trimmed));
        }
        eprintln!("Data directory cannot be empty.");
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

fn prompt_executor_image(default: &str) -> anyhow::Result<String> {
    println!();
    println!("--- Executor Image ---");
    println!("Purpose: the Docker image used by the executor to run tasks.");
    println!("Default: {default}");
    println!();

    let value = prompt_raw("Executor image", Some(default))?;
    let trimmed = value.trim();
    if trimmed.is_empty() {
        Ok(default.to_string())
    } else {
        Ok(trimmed.to_string())
    }
}

fn prompt_executor_capacity(default: usize) -> anyhow::Result<usize> {
    println!();
    println!("--- Executor Capacity ---");
    println!("Purpose: the maximum number of concurrent tasks the executor can run.");
    println!("Default: {default}");
    println!();

    loop {
        let input = prompt_raw("Executor capacity", Some(&default.to_string()))?;
        if input.trim().is_empty() {
            return Ok(default);
        }
        match input.trim().parse::<usize>() {
            Ok(n) if n == 0 => {
                eprintln!("Capacity must be greater than 0. Please try again.");
                continue;
            }
            Ok(n) => return Ok(n),
            Err(e) => {
                eprintln!("Invalid number '{}': {}. Please try again.", input, e);
                continue;
            }
        }
    }
}

fn normalize_server_url(value: &str) -> String {
    let trimmed = value.trim().trim_end_matches('/');
    if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        trimmed.to_string()
    } else {
        format!("https://{trimmed}")
    }
}

fn validate_server_url(value: &str) -> bool {
    match reqwest::Url::parse(value) {
        Ok(url) => url.host_str().is_some(),
        Err(_) => false,
    }
}

//! OpenAaaS Agent Core - 主入口

use agent_core::client::ApiClient;
use agent_core::config::Config;
use agent_core::executor::docker::DockerExecutor;
use agent_core::executor::Executor;
use agent_core::main_support::*;
use agent_core::scheduler::{Scheduler, SchedulerCommand};
use agent_core::state::StateManager;
use clap::{Parser, Subcommand};
use std::fs;
use std::path::PathBuf;
use std::process::Command as StdCommand;
use std::time::Duration;

use anyhow::Context;
use tokio::signal;
use tracing::{error, info, warn};
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;

#[derive(Parser)]
#[command(name = "agent-core")]
#[command(about = "OpenAaaS Agent Core - 调度与执行框架")]
#[command(version = env!("CARGO_PKG_VERSION"))]
struct Cli {
    /// 配置文件路径；不传时读取当前工作目录下的 config.toml
    #[arg(long, global = true, value_name = "FILE")]
    config: Option<PathBuf>,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// 运行调度器（前台）
    Run {
        /// 使用交互模式注册（如果未注册）
        #[arg(long)]
        interactive: bool,
    },
    /// 运行调度器（后台）
    #[command(name = "run-detached")]
    RunDetached,
    /// 停止后台调度器
    Stop,
    /// 查看状态
    Status,
    /// 初始化配置
    Init,
    /// 注册服务
    Register {
        /// 注册令牌
        #[arg(short, long)]
        token: Option<String>,
        /// Agent 名称
        #[arg(short, long)]
        name: Option<String>,
    },
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


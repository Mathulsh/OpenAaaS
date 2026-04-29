"""Task submission page for OpenAaaS Dashboard."""

from __future__ import annotations

from datetime import datetime, timezone

import html

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from aaas_dashboard.client import TaskStatus
from aaas_dashboard.components import (
    get_or_create_client,
    init_session_state,
    render_sidebar,
    sync_sidebar_state,
    sync_sidebar_state_for_page,
)
from aaas_dashboard.config import get_config


st.set_page_config(
    page_title="Submit Task - OpenAaaS",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)


STATUS_STYLES = {
    "online": ("status-online", "在线"),
    "offline": ("status-offline", "离线"),
    "unknown": ("status-idle", "未知"),
    "pending": ("status-idle", "等待中"),
    "running": ("status-running", "执行中"),
    "completed": ("status-completed", "已完成"),
    "failed": ("status-failed", "失败"),
    "cancelled": ("status-idle", "已取消"),
    "cancelling": ("status-running", "取消中"),
}

FAILURE_LOG_FILENAMES = ("step2.log", "step1.log")


def inject_page_styles() -> None:
    """Inject page-level custom styles."""
    st.markdown(
        """
        <style>
            :root {
                --surface-0: #11151b;
                --surface-1: #171c24;
                --surface-2: #1f2631;
                --ink-0: #f3ede2;
                --ink-1: #b8b09f;
                --line-soft: rgba(236, 226, 203, 0.12);
                --brand-strong: #d7b46c;
                --brand-soft: #b89448;
                --ok-soft: rgba(67, 111, 77, 0.34);
                --ok-ink: #d8ebd8;
                --warn-soft: rgba(184, 148, 72, 0.28);
                --warn-ink: #f2d28a;
                --danger-soft: rgba(147, 70, 62, 0.3);
                --danger-ink: #f2c4be;
                --idle-soft: rgba(99, 102, 111, 0.34);
                --idle-ink: #d7d1c7;
            }

            .submit-hero {
                padding: 1.2rem 1.35rem 1rem 1.35rem;
                border: 1px solid var(--line-soft);
                border-radius: 22px;
                background:
                    radial-gradient(circle at top right, rgba(184, 148, 72, 0.18), transparent 26%),
                    linear-gradient(180deg, rgba(24, 29, 36, 0.98) 0%, rgba(18, 22, 28, 0.96) 100%);
                color: var(--ink-0);
                margin-bottom: 1rem;
            }

            .submit-hero h1 {
                margin: 0;
                font-size: 2rem;
                letter-spacing: -0.03em;
            }

            .submit-hero p {
                margin: 0.45rem 0 0;
                color: var(--ink-1);
                max-width: 60rem;
                line-height: 1.55;
            }

            .mini-label {
                text-transform: uppercase;
                letter-spacing: 0.14em;
                font-size: 0.72rem;
                color: var(--brand-strong);
                font-weight: 700;
                margin-bottom: 0.45rem;
            }

            .section-title {
                margin: 0.1rem 0 0.25rem;
                font-size: 1.15rem;
                font-weight: 700;
                color: var(--ink-0);
            }

            .section-copy {
                color: var(--ink-1);
                margin: 0 0 0.85rem;
                line-height: 1.5;
            }

            .stat-tile {
                border: 1px solid var(--line-soft);
                border-radius: 18px;
                padding: 0.95rem 1rem;
                background: linear-gradient(180deg, rgba(25, 31, 39, 0.96), rgba(19, 24, 31, 0.9));
                min-height: 100px;
            }

            .stat-tile .label {
                color: var(--ink-1);
                font-size: 0.82rem;
                margin-bottom: 0.5rem;
            }

            .stat-tile .value {
                font-size: 2rem;
                line-height: 1;
                color: var(--ink-0);
                font-weight: 700;
                letter-spacing: -0.04em;
            }

            .stat-tile .hint {
                font-size: 0.84rem;
                color: var(--ink-1);
                margin-top: 0.55rem;
            }

            .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                border-radius: 999px;
                padding: 0.26rem 0.72rem;
                font-size: 0.78rem;
                font-weight: 700;
                border: 1px solid transparent;
            }

            .status-pill::before {
                content: "";
                width: 0.46rem;
                height: 0.46rem;
                border-radius: 999px;
                background: currentColor;
                opacity: 0.72;
            }

            .status-online,
            .status-completed {
                background: var(--ok-soft);
                color: var(--ok-ink);
                border-color: rgba(47, 92, 48, 0.14);
            }

            .status-running {
                background: var(--warn-soft);
                color: var(--warn-ink);
                border-color: rgba(130, 93, 11, 0.14);
            }

            .status-offline,
            .status-idle {
                background: var(--idle-soft);
                color: var(--idle-ink);
                border-color: rgba(103, 95, 82, 0.15);
            }

            .status-failed {
                background: var(--danger-soft);
                color: var(--danger-ink);
                border-color: rgba(138, 46, 40, 0.14);
            }

            .meta-card {
                border: 1px solid var(--line-soft);
                border-radius: 20px;
                padding: 1rem 1.05rem;
                background: rgba(23, 28, 36, 0.94);
                margin-bottom: 0.85rem;
            }

            .meta-card h3 {
                margin: 0 0 0.35rem;
                color: var(--ink-0);
                font-size: 1.02rem;
            }

            .meta-card p {
                margin: 0.25rem 0 0;
                color: var(--ink-1);
                line-height: 1.5;
                font-size: 0.92rem;
            }

            .inline-code {
                display: inline-block;
                margin-top: 0.55rem;
                padding: 0.38rem 0.55rem;
                border-radius: 12px;
                background: rgba(39, 46, 57, 0.92);
                border: 1px solid var(--line-soft);
                color: var(--ink-0);
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                font-size: 0.82rem;
                word-break: break-all;
            }

            .service-strip {
                border: 1px solid var(--line-soft);
                border-radius: 18px;
                padding: 0.95rem 1rem;
                background: rgba(23, 28, 36, 0.92);
                min-height: 132px;
            }

            .service-strip h4 {
                margin: 0 0 0.5rem;
                font-size: 1rem;
                color: var(--ink-0);
            }

            .service-strip p {
                margin: 0.45rem 0 0;
                color: var(--ink-1);
                line-height: 1.5;
                font-size: 0.92rem;
            }

            .task-card {
                border: 1px solid var(--line-soft);
                border-radius: 18px;
                padding: 0.9rem 1rem 0.2rem;
                background: rgba(19, 24, 31, 0.96);
                margin-bottom: 0.8rem;
            }

            .task-title {
                margin: 0;
                font-size: 1rem;
                color: var(--ink-0);
                font-weight: 700;
                line-height: 1.4;
            }

            .task-id {
                margin-top: 0.16rem;
                color: var(--ink-1);
                font-size: 0.8rem;
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                word-break: break-all;
            }

            .task-identity-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.42rem;
                margin-top: 0.52rem;
            }

            .task-identity-item {
                border: 1px solid var(--line-soft);
                border-radius: 12px;
                background: rgba(39, 46, 57, 0.72);
                padding: 0.42rem 0.5rem;
                min-width: 0;
            }

            .task-identity-label {
                color: var(--ink-1);
                font-size: 0.68rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.2rem;
            }

            .task-identity-value {
                color: var(--ink-0);
                font-size: 0.76rem;
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                word-break: break-all;
                line-height: 1.35;
            }

            .task-meta {
                color: var(--ink-1);
                font-size: 0.82rem;
                line-height: 1.45;
                text-align: right;
            }

            .task-subline {
                margin-top: 0.36rem;
                color: var(--ink-1);
                font-size: 0.82rem;
                line-height: 1.45;
            }

            .task-running-note {
                margin: 0.55rem 0 0.2rem;
                padding: 0.52rem 0.72rem;
                border-radius: 12px;
                background: rgba(184, 148, 72, 0.2);
                color: var(--warn-ink);
                font-size: 0.82rem;
                border: 1px solid rgba(184, 148, 72, 0.18);
            }

            .list-toolbar {
                border: 1px solid var(--line-soft);
                border-radius: 18px;
                padding: 0.72rem 0.85rem 0.15rem;
                background: rgba(23, 28, 36, 0.9);
                margin-bottom: 0.9rem;
            }

            .detail-label {
                margin: 0.2rem 0 0.45rem;
                color: var(--ink-0);
                font-size: 0.84rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }

            .empty-note {
                border: 1px dashed var(--line-soft);
                border-radius: 18px;
                padding: 1rem;
                background: rgba(23, 28, 36, 0.88);
                color: var(--ink-1);
            }

            .stDownloadButton button {
                border-radius: 12px;
                border: 1px solid rgba(127, 90, 20, 0.18);
                background: linear-gradient(180deg, #fffaf0, #f1e2b9);
                color: #5b4414;
                font-weight: 700;
            }

            .stButton button[kind="primary"],
            .stFormSubmitButton button[kind="primary"] {
                border-radius: 14px;
                border: 1px solid rgba(127, 90, 20, 0.18);
                background: linear-gradient(180deg, #c99a42, #8e6920);
                color: #fff8e8;
                font-weight: 700;
                min-height: 2.9rem;
            }

            .stTextArea textarea,
            .stTextInput input {
                border-radius: 14px !important;
            }

            @media (max-width: 900px) {
                .task-identity-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(start: datetime | None, end: datetime | None) -> str:
    """Format duration between two datetimes."""
    if start is None:
        return "-"

    if end is None:
        end = datetime.now(timezone.utc)

    if start.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    elif start.tzinfo is not None and end.tzinfo is None:
        start = start.replace(tzinfo=None)

    total_seconds = int((end - start).total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def render_status_badge(status: str) -> None:
    """Render a status badge."""
    css_class, label = STATUS_STYLES.get(status, ("status-idle", status))
    st.markdown(
        f'<span class="status-pill {css_class}">{label}</span>',
        unsafe_allow_html=True,
    )


def render_stat_tile(label: str, value: int, hint: str) -> None:
    """Render a compact stat tile."""
    st.markdown(
        f"""
        <div class="stat-tile">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_task_file_list(task_id: str, task_files: list, prefix: str, client) -> None:
    """Render downloadable task files."""
    st.markdown("**结果文件**")
    for file_info in task_files:
        file_col1, file_col2, file_col3 = st.columns([3.2, 1.2, 1.2])
        with file_col1:
            st.markdown(f"`{file_info.filename}`")
        with file_col2:
            st.caption(f"{file_info.size_bytes} bytes")
        with file_col3:
            file_bytes = client.download_file_bytes(file_info.id)
            if file_bytes is not None:
                st.download_button(
                    "下载",
                    data=file_bytes,
                    file_name=file_info.filename,
                    mime=file_info.mime_type or "application/octet-stream",
                    key=f"{prefix}_{task_id}_{file_info.id}",
                    use_container_width=True,
                )

    response_file = next(
        (
            file_info
            for file_info in task_files
            if file_info.filename in {"response.md", "output/response.md"}
        ),
        None,
    )
    if response_file:
        response_text = client.download_file_text(response_file.id)
        if response_text:
            st.markdown("**预览 `response.md`**")
            preview, raw = st.tabs(["渲染视图", "原始内容"])
            with preview:
                st.markdown(response_text)
            with raw:
                st.text_area(
                    f"raw_{prefix}_{task_id}",
                    value=response_text,
                    height=260,
                    disabled=True,
                    label_visibility="collapsed",
                )


def render_failure_diagnostics(task, task_files: list, prefix: str, client) -> None:
    """Render the most useful failure signal near the task details."""
    if task.status != TaskStatus.FAILED:
        return

    if task.error_message:
        st.error(task.error_message)

    log_file = next(
        (
            file_info
            for preferred_name in FAILURE_LOG_FILENAMES
            for file_info in task_files
            if file_info.filename == preferred_name
        ),
        None,
    )
    if not log_file:
        if not task.error_message:
            st.markdown(
                '<div class="empty-note">任务失败，但服务端没有返回错误详情，也没有上传 step 日志。</div>',
                unsafe_allow_html=True,
            )
        return

    log_text = client.download_file_text(log_file.id)
    if not log_text:
        return

    st.markdown(f"**失败日志 `{log_file.filename}`**")
    if len(log_text) > 4000:
        log_text = "...\n" + log_text[-4000:]
    st.code(log_text, language="text")


def render_task_details(task, client, prefix: str) -> None:
    """Render details for a task."""
    content_left, content_right = st.columns([1.35, 1])

    with content_left:
        st.markdown('<div class="detail-label">Task Metadata</div>', unsafe_allow_html=True)
        st.code(
            f"task_id: {task.id}\n"
            f"session_id: {task.session_id}\n"
            f"service_id: {task.service_id}\n"
            f"status: {task.status.value}",
            language="text",
        )

        if task.input:
            task_prompt = task.input.get("task_prompt", "")
            if task_prompt:
                st.markdown('<div class="detail-label">Task Prompt</div>', unsafe_allow_html=True)
                st.text_area(
                    f"task_prompt_{prefix}_{task.id}",
                    value=task_prompt,
                    height=170,
                    disabled=True,
                    label_visibility="collapsed",
                )

            output_prompt = task.input.get("output_prompt", "")
            if output_prompt:
                st.markdown('<div class="detail-label">Output Prompt</div>', unsafe_allow_html=True)
                st.text_area(
                    f"output_prompt_{prefix}_{task.id}",
                    value=output_prompt,
                    height=110,
                    disabled=True,
                    label_visibility="collapsed",
                )

    with content_right:
        task_files = client.list_task_files(task.id)
        render_failure_diagnostics(task, task_files, prefix, client)
        if task_files:
            render_task_file_list(task.id, task_files, prefix, client)
        elif task.status == TaskStatus.COMPLETED:
            st.markdown('<div class="empty-note">任务已完成，但还没有可下载的结果文件。</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-note">结果文件会在任务完成后显示在这里。</div>', unsafe_allow_html=True)


init_session_state()
inject_page_styles()

if st.session_state.config is None:
    st.session_state.config = get_config()
    sync_sidebar_state(st.session_state.config)

config = st.session_state.config
sync_sidebar_state_for_page(config, "submit_task")
new_config, auto_refresh = render_sidebar(config)

if new_config.server_url != config.server_url or new_config.api_key != config.api_key:
    st.session_state.config = new_config
    st.session_state.client = None
    config = new_config

client = get_or_create_client(config)

if auto_refresh:
    st_autorefresh(interval=config.refresh_interval * 1000, key="submit_task_autorefresh")

services = client.list_client_services()
online_services = [svc for svc in services if svc.get("agent_status") == "online"]
service_options = online_services or services

if not config.api_key and not st.session_state.use_mock:
    st.warning("请先在左侧填写 API Key。")
    st.stop()

if not services:
    st.info("当前没有可用服务。先创建并启动一个 service + agent。")
    st.stop()

all_tasks = client.list_tasks(limit=100)
running_count = sum(1 for task in all_tasks if task.status == TaskStatus.RUNNING)
completed_count = sum(1 for task in all_tasks if task.status == TaskStatus.COMPLETED)
default_service = service_options[0]
selected_service_snapshot = default_service

st.markdown(
    """
    <div class="submit-hero">
        <div class="mini-label">OpenAaaS Client Surface</div>
        <h1>任务提交与结果浏览</h1>
        <p>把任务发给指定 service，直接观察任务状态、结果文件和 Markdown 输出。这个页面现在既是提交入口，也是用户查看结果的主界面。</p>
    </div>
    """,
    unsafe_allow_html=True,
)

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
with stat_col1:
    render_stat_tile("在线服务", len(online_services), "可立即接任务的执行节点")
with stat_col2:
    render_stat_tile("总服务数", len(services), "当前账号可见的 service")
with stat_col3:
    render_stat_tile("运行中", running_count, "仍在等待结果回传的任务")
with stat_col4:
    render_stat_tile("已完成", completed_count, "可直接下载文件和阅读输出")

main_left, main_right = st.columns([1.45, 0.95], gap="large")

with main_left:
    st.markdown('<div class="mini-label">Compose</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">提交新任务</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-copy">先选目标 service，再写清楚任务目标和输出要求。文本越具体，结果越稳定。</p>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        with st.form("submit_task_form", clear_on_submit=False):
            selected_service = st.selectbox(
                "Target Service",
                options=service_options,
                format_func=lambda svc: (
                    f"{svc.get('name', '-')}"
                    f" [{svc.get('agent_status', 'unknown')}]"
                    f" ({svc.get('id', '-')})"
                ),
                index=0,
                help="优先选择在线服务；离线服务无法执行任务。",
            )

            task_prompt = st.text_area(
                "Task Prompt",
                value="",
                height=240,
                placeholder="例如：请总结这份文档，并给出 5 条可执行建议。",
            )

            output_prompt = st.text_area(
                "Output Prompt",
                value="返回 Markdown 格式结果",
                height=120,
                placeholder="例如：分成标题、要点、结论三部分输出。",
            )

            advanced_left, advanced_right = st.columns([1, 1.1])
            with advanced_left:
                session_id = st.text_input(
                    "Session ID",
                    value="",
                    placeholder="可选：用于标记同一组任务",
                    help="仅用于任务分组或执行器会话标识；系统不会自动读取上一轮输出文件。",
                )
            with advanced_right:
                uploaded_files = st.file_uploader(
                    "Input Files",
                    accept_multiple_files=True,
                    help="可选：随任务一起上传材料",
                )

            submitted = st.form_submit_button("提交任务", use_container_width=True, type="primary")

            if submitted:
                if not task_prompt.strip():
                    st.error("Task Prompt 不能为空。")
                elif not output_prompt.strip():
                    st.error("Output Prompt 不能为空。")
                else:
                    created = client.create_task(
                        service_id=selected_service["id"],
                        task_prompt=task_prompt.strip(),
                        output_prompt=output_prompt.strip(),
                        session_id=session_id.strip() or None,
                        files=uploaded_files,
                    )
                    if created is None:
                        st.error("提交任务失败。请检查 API Key、Service 状态或服务端日志。")
                        if getattr(client, "last_error", None):
                            st.caption(f"错误详情：`{client.last_error}`")
                    else:
                        st.session_state["last_created_task_id"] = created.id
                        st.session_state["last_created_session_id"] = created.session_id
                        st.success(f"任务已提交：`{created.id}`")
                        st.info(f"Session ID: `{created.session_id}`")

            selected_service_snapshot = selected_service

with main_right:
    st.markdown('<div class="mini-label">Target</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">当前 service</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-copy">这里显示当前任务会发往哪个执行节点，以及它的可用状态。</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="meta-card">
            <h3>{selected_service_snapshot.get('name', '-')}</h3>
            <div style="margin: 0.35rem 0 0.65rem;">
                <span class="status-pill {STATUS_STYLES.get(selected_service_snapshot.get('agent_status', 'unknown'), ('status-idle', '未知'))[0]}">
                    {STATUS_STYLES.get(selected_service_snapshot.get('agent_status', 'unknown'), ('status-idle', '未知'))[1]}
                </span>
            </div>
            <p>{selected_service_snapshot.get('description', '-') or '暂无描述。'}</p>
            <div class="inline-code">{selected_service_snapshot.get('id', '-')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_info, col_btn = st.columns([4, 1])
    with col_info:
        st.markdown(f"**Description:** {selected_service_snapshot.get('description', '-')}")
    with col_btn:
        if st.button("📖 View Usage", key=f"view_usage_{selected_service_snapshot.get('id')}"):
            usage_data = client.get_service_usage(selected_service_snapshot.get('id'))
            if usage_data is None:
                st.session_state[f"show_usage_{selected_service_snapshot.get('id')}"] = "❌ Failed to fetch usage. Please check your connection."
            elif not usage_data.get('usage'):
                st.session_state[f"show_usage_{selected_service_snapshot.get('id')}"] = "No usage description available for this service."
            else:
                st.session_state[f"show_usage_{selected_service_snapshot.get('id')}"] = usage_data['usage']

    # 显示 usage 内容（如果已获取）
    # 显示 usage 内容（如果已获取）
    usage_key = f"show_usage_{selected_service_snapshot.get('id')}"
    if usage_key in st.session_state:
        # 先 html.escape 防止 XSS，再把 \n 替换成 <br> 确保换行正确渲染
        usage_html = html.escape(st.session_state[usage_key]).replace("\n", "<br>")
        st.markdown(
            f'''
            <div class="meta-card">
                <h3>📖 Service Usage</h3>
                <div style="color: #f3ede2; background: #1f2631; padding: 0.75rem; border-radius: 12px; line-height: 1.6; font-size: 0.92rem; border: 1px solid rgba(236,226,203,0.12); font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;">
                    {usage_html}
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        if st.button("Hide Usage", key=f"hide_usage_{selected_service_snapshot.get('id')}"):
            del st.session_state[usage_key]
            st.rerun()

    if st.session_state.get("last_created_task_id"):
        st.markdown(
            f"""
            <div class="meta-card">
                <h3>最近一次提交</h3>
                <p>你刚提交的任务会优先在下方任务列表里展开。</p>
                <p>Task ID</p>
                <div class="inline-code">{st.session_state["last_created_task_id"]}</div>
                <p>Session ID</p>
                <div class="inline-code">{st.session_state.get("last_created_session_id", "-")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()
st.markdown('<div class="mini-label">Services</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">可用服务</div>', unsafe_allow_html=True)
st.markdown(
    '<p class="section-copy">优先展示在线服务，方便你快速判断哪个执行节点正在接任务。</p>',
    unsafe_allow_html=True,
)

service_columns = st.columns(2, gap="medium")
for index, svc in enumerate(service_options):
    with service_columns[index % 2]:
        status_class, status_label = STATUS_STYLES.get(
            svc.get("agent_status", "unknown"),
            ("status-idle", "未知"),
        )
        st.markdown(
            f"""
            <div class="service-strip">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.75rem;">
                    <div>
                        <h4>{svc.get('name', '-')}</h4>
                        <div class="inline-code">{svc.get('id', '-')}</div>
                    </div>
                    <span class="status-pill {status_class}">{status_label}</span>
                </div>
                <p>{svc.get("description", "-") or "暂无描述。"}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()
st.markdown('<div class="mini-label">Recent Activity</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">最近任务</div>', unsafe_allow_html=True)
st.markdown(
    '<p class="section-copy">这里按任务流转展示输入、结果文件和最终输出。默认只看当前选中的 service。</p>',
    unsafe_allow_html=True,
)

st.markdown('<div class="list-toolbar">', unsafe_allow_html=True)
filter_col1, filter_col2 = st.columns([1.2, 1])
with filter_col1:
    task_scope = st.radio(
        "Task Scope",
        options=["当前服务", "全部服务"],
        horizontal=True,
        help="默认只看当前选择的 service，便于提交后直接观察任务流转。",
    )
with filter_col2:
    status_filter_label = st.selectbox(
        "Status Filter",
        options=["全部", "pending", "running", "completed", "failed", "cancelled", "cancelling"],
        index=0,
    )
st.markdown("</div>", unsafe_allow_html=True)

status_filter = None if status_filter_label == "全部" else TaskStatus(status_filter_label)
tasks = client.list_tasks(status=status_filter, limit=50)
tasks.sort(key=lambda task: task.created_at or datetime.min, reverse=True)

if task_scope == "当前服务":
    tasks = [task for task in tasks if task.service_id == selected_service_snapshot.get("id")]

if not tasks:
    st.markdown('<div class="empty-note">当前筛选条件下还没有任务。提交一个任务后，这里会自动刷新显示。</div>', unsafe_allow_html=True)
else:
    for task in tasks:
        with st.container(border=True):
            header_left, header_mid, header_right = st.columns([4.4, 1.05, 1.55], gap="small")
            with header_left:
                st.markdown(f'<div class="task-title">{task.name}</div>', unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div class="task-identity-grid">
                        <div class="task-identity-item">
                            <div class="task-identity-label">Task ID</div>
                            <div class="task-identity-value">{task.id}</div>
                        </div>
                        <div class="task-identity-item">
                            <div class="task-identity-label">Session ID</div>
                            <div class="task-identity-value">{task.session_id}</div>
                        </div>
                        <div class="task-identity-item">
                            <div class="task-identity-label">Service ID</div>
                            <div class="task-identity-value">{task.service_id}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with header_mid:
                render_status_badge(task.status.value)
            with header_right:
                st.markdown(
                    f"""
                    <div class="task-meta">
                        <div>{format_datetime(task.created_at)}</div>
                        <div>耗时 {format_duration(task.created_at, task.completed_at)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            if task.status == TaskStatus.RUNNING:
                st.markdown(
                    '<div class="task-running-note">任务执行中。当前界面不展示真实进度，只会在结果回传后更新。</div>',
                    unsafe_allow_html=True,
                )

            with st.expander("查看任务详情", expanded=task.id == st.session_state.get("last_created_task_id")):
                render_task_details(task, client, "submit_page")

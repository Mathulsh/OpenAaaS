"""Streamlit main application for OpenAaaS Dashboard."""

from datetime import datetime, timezone
from typing import Optional

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from aaas_dashboard.client import OaaSClient, TaskStatus
from aaas_dashboard.components import (
    get_or_create_client,
    init_session_state,
    render_sidebar,
    sync_sidebar_state,
    sync_sidebar_state_for_page,
)
from aaas_dashboard.config import get_config


# Page configuration
st.set_page_config(
    page_title="OpenAaaS Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .task-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 5px solid #ccc;
    }
    .task-card.running { border-left-color: #ffa500; }
    .task-card.completed { border-left-color: #28a745; }
    .task-card.failed { border-left-color: #dc3545; }
    .task-card.pending { border-left-color: #6c757d; }
    .task-card.cancelled { border-left-color: #6f42c1; }
    .task-card.cancelling { border-left-color: #ffa500; }

    .status-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: bold;
    }
    .status-running { background-color: #fff3cd; color: #856404; }
    .status-completed { background-color: #d4edda; color: #155724; }
    .status-failed { background-color: #f8d7da; color: #721c24; }
    .status-pending { background-color: #e2e3e5; color: #383d41; }
    .status-cancelled { background-color: #e2e3e5; color: #6f42c1; }
    .status-cancelling { background-color: #fff3cd; color: #856404; }

    .metric-card {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


def get_status_color(status: TaskStatus) -> str:
    """Get color for task status."""
    colors = {
        TaskStatus.PENDING: "gray",
        TaskStatus.RUNNING: "orange",
        TaskStatus.COMPLETED: "green",
        TaskStatus.FAILED: "red",
        TaskStatus.CANCELLED: "purple",
        TaskStatus.CANCELLING: "orange",
    }
    return colors.get(status, "gray")


def get_status_badge_class(status: TaskStatus) -> str:
    """Get CSS class for status badge."""
    return f"status-{status.value}"


def get_task_card_class(status: TaskStatus) -> str:
    """Get CSS class for task card."""
    return f"task-card {status.value}"


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(start: Optional[datetime], end: Optional[datetime]) -> str:
    """Format duration between two datetimes."""
    if start is None:
        return "-"

    # 如果 end 为 None，使用当前时间（带时区）
    if end is None:
        end = datetime.now(timezone.utc)

    # 统一时区处理：如果 start 有 tzinfo 而 end 没有，给 end 加 UTC
    # 如果 start 没有 tzinfo 而 end 有，移除 end 的 tzinfo
    if start.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    elif start.tzinfo is not None and end.tzinfo is None:
        start = start.replace(tzinfo=None)

    duration = end - start
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def build_task_stats(tasks) -> dict:
    """Build status counts from a task list."""
    return {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
        "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
        "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
        "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
        "cancelled": sum(1 for t in tasks if t.status == TaskStatus.CANCELLED),
        "cancelling": sum(1 for t in tasks if t.status == TaskStatus.CANCELLING),
    }


def render_stats(client: OaaSClient, tasks=None) -> None:
    """Render statistics cards."""
    stats = build_task_stats(tasks) if tasks is not None else client.get_stats()

    # 第一行：总任务 + 等待中 + 运行中
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📊 Total", stats.get("total", 0))
    with col2:
        st.metric("⏳ Pending", stats.get("pending", 0))
    with col3:
        st.metric("🔄 Running", stats.get("running", 0))

    # 第二行：完成状态
    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric("✅ Completed", stats.get("completed", 0))
    with col5:
        st.metric("❌ Failed", stats.get("failed", 0))
    with col6:
        st.metric("🚫 Cancelled", stats.get("cancelled", 0))

    # 第三行：取消中（较少见，单独一行）
    if stats.get("cancelling", 0) > 0:
        col7, _, _ = st.columns(3)
        with col7:
            st.metric("⏹️ Cancelling", stats.get("cancelling", 0))


def render_task_card(task, client: OaaSClient) -> None:
    """Render a single task card.

    Args:
        task: Task object
        client: API client
    """
    status_color = get_status_color(task.status)
    status_badge = get_status_badge_class(task.status)

    with st.container():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

        with col1:
            st.markdown(f"**{task.name}**")
            st.caption(f"Task ID: `{task.id}`")
            st.caption(f"Session ID: `{task.session_id}`")
            if task.user_name or task.user_id:
                user_label = task.user_name or task.user_id
                st.caption(f"User: `{user_label}`")
            if task.service_id:
                st.caption(f"Service ID: `{task.service_id}`")

        with col2:
            st.markdown(
                f'<span class="status-badge {status_badge}">{task.status.value.upper()}</span>',
                unsafe_allow_html=True,
            )
            if task.progress is not None and task.status == TaskStatus.RUNNING:
                st.progress(task.progress / 100, text=f"{task.progress:.0f}%")

        with col3:
            st.caption(f"Created: {format_datetime(task.created_at)}")
            if task.completed_at:
                st.caption(f"Completed: {format_datetime(task.completed_at)}")
            duration = format_duration(task.created_at, task.completed_at)
            st.caption(f"Duration: {duration}")

        with col4:
            if task.status == TaskStatus.RUNNING:
                if st.button("⏹️ Cancel", key=f"cancel_{task.id}"):
                    if client.cancel_task(task.id):
                        st.success("Cancelled!")
                        st.rerun()
                    else:
                        st.error("Failed to cancel")

        # Show error message if failed
        if task.status == TaskStatus.FAILED and task.error_message:
            st.error(f"Error: {task.error_message}")

        # Show input/output summary
        with st.expander("📋 Details"):
            st.markdown("**Task Metadata:**")
            st.code(
                f"task_id: {task.id}\n"
                f"session_id: {task.session_id}\n"
                f"service_id: {task.service_id}\n"
                f"status: {task.status.value}",
                language="text",
            )

            if task.input:
                st.markdown("**📝 Input:**")

                # Task Prompt
                task_prompt = task.input.get("task_prompt", "")
                if task_prompt:
                    with st.container():
                        st.markdown("*Task Prompt:*")
                        st.text_area("Task Prompt", value=task_prompt, height=150, key=f"prompt_{task.id}", disabled=True, label_visibility="collapsed")

                # Output Prompt
                output_prompt = task.input.get("output_prompt", "")
                if output_prompt:
                    with st.container():
                        st.markdown("*Output Prompt:*")
                        st.text_area("Output Prompt", value=output_prompt, height=100, key=f"output_prompt_{task.id}", disabled=True, label_visibility="collapsed")

                # Input Files
                input_files = task.input.get("input_files", [])
                if input_files:
                    st.markdown("*Input Files:*")
                    for f in input_files:
                        st.markdown(f"- `{f}`")

            if task.output:
                st.markdown("**📤 Output:**")
                output_data = task.output

                # 如果 output 包含 content 字段，优先显示
                if isinstance(output_data, dict):
                    task_files = client.list_task_files(task.id)
                    if task_files:
                        st.markdown("*Output Files:*")
                        for file_info in task_files:
                            file_col1, file_col2, file_col3 = st.columns([3, 1.2, 1.2])
                            with file_col1:
                                st.markdown(f"`{file_info.filename}`")
                            with file_col2:
                                st.caption(f"{file_info.size_bytes} bytes")
                            with file_col3:
                                file_bytes = client.download_file_bytes(file_info.id)
                                if file_bytes is not None:
                                    st.download_button(
                                        "Download",
                                        data=file_bytes,
                                        file_name=file_info.filename,
                                        mime=file_info.mime_type or "application/octet-stream",
                                        key=f"download_{task.id}_{file_info.id}",
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
                            response_content = client.download_file_text(response_file.id)
                            if response_content:
                                st.markdown("*Rendered `response.md`:*")
                                st.markdown(response_content)
                                if st.checkbox("Show raw Markdown", key=f"show_response_md_{task.id}"):
                                    st.text_area(
                                        "Response Markdown",
                                        value=response_content,
                                        height=220,
                                        key=f"response_md_{task.id}",
                                        disabled=True,
                                        label_visibility="collapsed",
                                    )
                    else:
                        output_files = output_data.get("files", [])
                        if output_files:
                            st.markdown("*Output Files:*")
                            for filename in output_files:
                                st.markdown(f"- `{filename}`")

                    if "content" in output_data:
                        st.markdown("*Content:*")
                        st.text_area("Content", value=output_data["content"], height=200, key=f"content_{task.id}", disabled=True, label_visibility="collapsed")

                    # 显示其他字段
                    other_fields = {k: v for k, v in output_data.items() if k not in {"content"}}
                    if other_fields:
                        if st.checkbox("Show raw output JSON", key=f"show_raw_output_{task.id}"):
                            import json
                            st.code(json.dumps(other_fields, indent=2, ensure_ascii=False))
                else:
                    st.code(str(output_data))

        st.divider()


def render_task_list(
    client: OaaSClient,
    status_filter: Optional[TaskStatus] = None,
    user_id_filter: Optional[str] = None,
    admin_view: bool = False,
    tasks=None,
) -> None:
    """Render the task list.

    Args:
        client: API client
        status_filter: Optional status filter
    """
    if tasks is None:
        if admin_view:
            tasks = client.list_admin_tasks(
                status=status_filter,
                user_id=user_id_filter,
                limit=100,
            )
        else:
            tasks = client.list_tasks(status=status_filter, limit=100)

    if not tasks:
        st.info("No tasks found." if status_filter is None else f"No {status_filter.value} tasks found.")
        return

    # Sort by created_at descending
    tasks.sort(key=lambda t: t.created_at or datetime.min, reverse=True)

    for task in tasks:
        render_task_card(task, client)


def main() -> None:
    """Main application entry point."""
    init_session_state()

    # Load configuration
    if st.session_state.config is None:
        st.session_state.config = get_config()
        sync_sidebar_state(st.session_state.config)

    config = st.session_state.config
    sync_sidebar_state_for_page(config, "app")

    # Render sidebar
    new_config, auto_refresh = render_sidebar(config)

    # Update config if changed
    if new_config.server_url != config.server_url or new_config.api_key != config.api_key:
        st.session_state.config = new_config
        st.session_state.client = None
        config = new_config

    # Initialize client
    client = get_or_create_client(config)

    # Header
    st.title("📊 OpenAaaS Dashboard")
    st.caption(f"Connected to: {config.server_url}")

    # Health check
    health = client.health_check()
    if health.get("status") == "healthy":
        st.success("🟢 Server is healthy")
    else:
        st.error(f"🔴 Server is unhealthy: {health.get('error', 'Unknown error')}")
        st.info("You can enable 'Use Mock Data' in the sidebar to test the dashboard.")

    st.divider()

    # Task list header with filters
    users = client.list_users()
    admin_view = bool(users)
    selected_user_id = None

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.subheader("📋 Task List")

    with col2:
        status_options = {
            "All": None,
            "⏳ Pending": TaskStatus.PENDING,
            "🔄 Running": TaskStatus.RUNNING,
            "✅ Completed": TaskStatus.COMPLETED,
            "❌ Failed": TaskStatus.FAILED,
            "🚫 Cancelled": TaskStatus.CANCELLED,
            "⏹️ Cancelling": TaskStatus.CANCELLING,
        }
        selected_status = st.selectbox(
            "Filter by status",
            options=list(status_options.keys()),
            index=0,
        )
        status_filter = status_options[selected_status]

    with col3:
        if admin_view:
            user_options = {"All Users": None}
            for user in users:
                user_options[f"{user.name} ({user.role})"] = user.id
            selected_user = st.selectbox(
                "Filter by user",
                options=list(user_options.keys()),
                index=0,
            )
            selected_user_id = user_options[selected_user]
        else:
            st.caption("User filter is available for admin API keys.")

    tasks = (
        client.list_admin_tasks(status=status_filter, user_id=selected_user_id, limit=100)
        if admin_view
        else client.list_tasks(status=status_filter, limit=100)
    )

    if admin_view:
        st.caption("Admin view: showing tasks across users. Use the user filter to narrow the list.")

    # Statistics
    render_stats(client, tasks)

    st.divider()

    # Render task list
    render_task_list(
        client,
        status_filter,
        user_id_filter=selected_user_id,
        admin_view=admin_view,
        tasks=tasks,
    )

    # 自动刷新 - 使用 st_autorefresh 只更新组件，不刷新页面
    if auto_refresh:
        st_autorefresh(interval=config.refresh_interval * 1000, key="task_refresh")
        st.caption(f"⏱️ Auto-refreshing every {config.refresh_interval} seconds")
    else:
        # Show manual refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()


if __name__ == "__main__":
    main()

//! 执行器 trait 和实现

pub mod docker;

use serde::{Deserialize, Serialize};
use std::time::Duration;
use thiserror::Error;

/// 下载到本地 workspace 的输入文件
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskInputFile {
    /// 服务端文件 ID
    pub id: String,
    /// 原始文件名
    pub filename: String,
    /// 文件 MIME 类型
    pub mime_type: Option<String>,
    /// 文件大小
    pub size_bytes: i64,
    /// 相对于 workspace 的本地路径
    pub local_path: String,
}

/// 执行任务
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    /// 任务 ID
    pub task_id: String,
    /// 任务提示词
    pub prompt: String,
    /// 输出格式要求
    pub output_prompt: Option<String>,
    /// 会话 ID（可选）
    pub session_id: Option<String>,
    /// 输入文件
    #[serde(default)]
    pub input_files: Vec<TaskInputFile>,
    // 注意：没有 timeout 字段，全局统一配置
}

/// 任务执行结果
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    /// 任务 ID
    pub task_id: String,
    /// 退出码（0 表示成功）
    pub exit_code: i32,
    /// 标准输出
    pub stdout: String,
    /// 标准错误
    pub stderr: String,
    /// 输出文件路径（相对于 workspace）
    pub output_files: Vec<String>,
}

impl TaskResult {
    /// 根据退出码获取完成状态
    pub fn status(&self) -> crate::client::TaskCompleteStatus {
        if self.exit_code == 0 {
            crate::client::TaskCompleteStatus::Completed
        } else {
            crate::client::TaskCompleteStatus::Failed
        }
    }
}

/// 执行器错误
#[derive(Error, Debug, Clone)]
pub enum ExecutorError {
    #[error("任务 {task_id} 执行失败: {reason}")]
    ExecutionFailed { task_id: String, reason: String },

    #[error("任务 {task_id} 执行超时，已耗时 {elapsed:?}")]
    Timeout { task_id: String, elapsed: Duration },

    #[error("IO错误: {0}")]
    Io(String),
}

/// 执行器 trait
pub trait Executor: Send + Sync {
    /// 执行任务，返回执行结果
    fn execute(
        &self,
        task: Task,
        docker_mounts: Vec<String>,
    ) -> impl std::future::Future<Output = Result<TaskResult, ExecutorError>> + Send;

    /// 取消正在执行的任务
    fn cancel(
        &self,
        task_id: &str,
    ) -> impl std::future::Future<Output = Result<(), ExecutorError>> + Send;

    /// 获取执行器容量（并发任务数）
    fn capacity(&self) -> usize;

    /// 当前负载（正在执行的任务数）
    fn current_load(&self) -> usize;
}

#[cfg(test)]
mod tests {
    use super::*;

    // ==================== Task 序列化/反序列化测试 ====================

    #[test]
    fn test_task_serialization_full_fields() {
        let task = Task {
            task_id: "task-123".to_string(),
            prompt: "Hello World".to_string(),
            output_prompt: Some("JSON".to_string()),
            session_id: Some("session-456".to_string()),
            input_files: vec![TaskInputFile {
                id: "file-1".to_string(),
                filename: "report.pdf".to_string(),
                mime_type: Some("application/pdf".to_string()),
                size_bytes: 1024,
                local_path: "input/01-report.pdf".to_string(),
            }],
        };

        let json = serde_json::to_string(&task).unwrap();
        assert!(json.contains("task-123"));
        assert!(json.contains("Hello World"));
        assert!(json.contains("JSON"));
        assert!(json.contains("session-456"));
        assert!(json.contains("report.pdf"));

        let deserialized: Task = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.task_id, task.task_id);
        assert_eq!(deserialized.prompt, task.prompt);
        assert_eq!(deserialized.output_prompt, task.output_prompt);
        assert_eq!(deserialized.session_id, task.session_id);
        assert_eq!(deserialized.input_files.len(), 1);
        assert_eq!(
            deserialized.input_files[0].local_path,
            "input/01-report.pdf"
        );
    }

    #[test]
    fn test_task_serialization_optional_none() {
        let task = Task {
            task_id: "task-789".to_string(),
            prompt: "Simple task".to_string(),
            output_prompt: None,
            session_id: None,
            input_files: vec![],
        };

        let json = serde_json::to_string(&task).unwrap();
        assert!(json.contains("task-789"));
        assert!(json.contains("Simple task"));

        let deserialized: Task = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.task_id, task.task_id);
        assert_eq!(deserialized.prompt, task.prompt);
        assert!(deserialized.output_prompt.is_none());
        assert!(deserialized.session_id.is_none());
        assert!(deserialized.input_files.is_empty());
    }

    // ==================== TaskResult 序列化/反序列化测试 ====================

    #[test]
    fn test_task_result_serialization_success() {
        let result = TaskResult {
            task_id: "task-123".to_string(),
            exit_code: 0,
            stdout: "Success output".to_string(),
            stderr: "".to_string(),
            output_files: vec![],
        };

        let json = serde_json::to_string(&result).unwrap();
        let deserialized: TaskResult = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.task_id, result.task_id);
        assert_eq!(deserialized.exit_code, 0);
        assert_eq!(deserialized.stdout, result.stdout);
        assert_eq!(deserialized.stderr, result.stderr);
    }

    #[test]
    fn test_task_result_serialization_failure() {
        let result = TaskResult {
            task_id: "task-456".to_string(),
            exit_code: 1,
            stdout: "".to_string(),
            stderr: "Error occurred".to_string(),
            output_files: vec![],
        };

        let json = serde_json::to_string(&result).unwrap();
        let deserialized: TaskResult = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.task_id, result.task_id);
        assert_eq!(deserialized.exit_code, 1);
        assert_eq!(deserialized.stderr, result.stderr);
    }

    #[test]
    fn test_task_result_serialization_with_output_files() {
        let result = TaskResult {
            task_id: "task-789".to_string(),
            exit_code: 0,
            stdout: "Done".to_string(),
            stderr: "".to_string(),
            output_files: vec![
                "output/file1.txt".to_string(),
                "output/file2.png".to_string(),
            ],
        };

        let json = serde_json::to_string(&result).unwrap();
        let deserialized: TaskResult = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.output_files.len(), 2);
        assert_eq!(deserialized.output_files[0], "output/file1.txt");
        assert_eq!(deserialized.output_files[1], "output/file2.png");
    }

    // ==================== ExecutorError 错误消息测试 ====================

    #[test]
    fn test_executor_error_execution_failed_message() {
        let error = ExecutorError::ExecutionFailed {
            task_id: "task-123".to_string(),
            reason: "Permission denied".to_string(),
        };
        let msg = format!("{}", error);
        assert!(msg.contains("任务 task-123 执行失败"));
        assert!(msg.contains("Permission denied"));
    }

    #[test]
    fn test_executor_error_timeout_message() {
        let error = ExecutorError::Timeout {
            task_id: "task-456".to_string(),
            elapsed: Duration::from_secs(300),
        };
        let msg = format!("{}", error);
        assert!(msg.contains("任务 task-456 执行超时"));
    }

    #[test]
    fn test_executor_error_io_message() {
        let error = ExecutorError::Io("File not found".to_string());
        let msg = format!("{}", error);
        assert_eq!(msg, "IO错误: File not found");
    }
}

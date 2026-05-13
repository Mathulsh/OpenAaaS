/**
 * 将技术性错误 message 映射为用户友好的文案。
 */
export function friendlyErrorMessage(message: string): string {
  if (!message) return '操作失败，请稍后重试'
  const lower = message.toLowerCase()
  if (
    lower.includes('payload too large') ||
    lower.includes('entity too large') ||
    lower.includes('too large') ||
    lower.includes('过大')
  ) {
    return '附件过大，请缩小后重试'
  }
  return message
}

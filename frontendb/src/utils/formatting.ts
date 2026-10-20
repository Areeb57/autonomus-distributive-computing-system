/**
 * Format a 9-digit code into spaced format (e.g. "849 203 194")
 */
export function formatProjectCode(code: string): string {
  const digits = code.replace(/\D/g, '').slice(0, 9);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)} ${digits.slice(3)}`;
  return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6, 9)}`;
}

/**
 * Remove spacing/formatting to get raw 9 digits
 */
export function cleanProjectCode(code: string): string {
  return code.replace(/\D/g, '').slice(0, 9);
}

/**
 * Generate a random 9-digit project code as a numeric string
 */
export function generateProjectCode(): string {
  // 9 digits between 100,000,000 and 999,999,999
  const num = Math.floor(100000000 + Math.random() * 900000000);
  return num.toString();
}

/**
 * Format seconds into human readable duration e.g. "01h 14m 20s"
 */
export function formatDuration(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00m 00s';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs.toString().padStart(2, '0')}h ${mins.toString().padStart(2, '0')}m ${secs.toString().padStart(2, '0')}s`;
  }
  return `${mins.toString().padStart(2, '0')}m ${secs.toString().padStart(2, '0')}s`;
}

/**
 * Format bytes to readable size
 */
export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

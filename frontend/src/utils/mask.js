/** 手机号/姓名脱敏（AC5）：与契约一致 138****8000 / 王**。 */
export function maskPhone(raw) {
  const s = String(raw || '').trim()
  if (s.length < 7) return s
  return s.slice(0, 3) + '****' + s.slice(-4)
}

export function maskName(raw) {
  const s = String(raw || '').trim()
  if (!s) return ''
  return s[0] + '**'
}

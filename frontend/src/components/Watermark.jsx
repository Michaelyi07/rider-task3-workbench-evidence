/** AC6：页面右下角个人水印（姓名 · 工号 · 日期时间），半透明 fixed，不遮挡操作。 */
export default function Watermark({ user }) {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`
  const text = `${user.name} · ${user.empId} · ${stamp}`
  return (
    <div
      data-testid="watermark"
      style={{
        position: 'fixed', right: 12, bottom: 12, zIndex: 9999,
        pointerEvents: 'none', userSelect: 'none',
        color: 'rgba(0, 0, 0, 0.35)', fontSize: 12, lineHeight: 1.6,
        background: 'rgba(255,255,255,0.4)', padding: '2px 8px', borderRadius: 4,
      }}
    >
      {text}
    </div>
  )
}

import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfigProvider } from 'antd'
import App from '../App'
import { maskPhone, maskName } from '../utils/mask'
import { mockRequest } from '../api/mock'

// 测试环境关闭 antd 全局动画（theme token motion:false），避免 Modal 关闭动画在 jsdom 卡住
function renderApp() {
  return render(
    <ConfigProvider theme={{ token: { motion: false } }}>
      <App />
    </ConfigProvider>
  )
}

describe('AC5/AC6 工作台前端（真实构建产物同源代码）', () => {
  test('列表默认脱敏：显示 138****8000，不出现完整号码', async () => {
    renderApp()
    await waitFor(() => {
      expect(screen.getByText('138****8000')).toBeInTheDocument()
    })
    expect(screen.getByText('王**')).toBeInTheDocument()
    // 页面上任何位置都不应出现完整手机号
    expect(document.body.textContent).not.toContain('13800008000')
  })

  test('maskPhone/maskName 工具符合契约掩码格式', () => {
    expect(maskPhone('13800008000')).toBe('138****8000')
    expect(maskName('王大明')).toBe('王**')
  })

  test('标记不合适：无理由时禁提交，填理由后可提交', async () => {
    const user = userEvent.setup()
    renderApp()
    await screen.findByText('138****8000')
    await user.click(screen.getAllByText('查看详情')[0])

    const markBtn = await screen.findByTestId('mark-unsuitable')
    await user.click(markBtn)
    const submit = await screen.findByTestId('reject-submit')
    // 无理由：禁提交
    expect(submit).toBeDisabled()
    // 填理由后：可提交
    await user.type(await screen.findByTestId('reject-reason'), '健康证无法提供且无法到岗')
    expect(submit).toBeEnabled()
    await user.click(submit)
    await waitFor(() => {
      expect(screen.getByText('已标记不合适')).toBeInTheDocument()
    })
  })

  test('查看完整号码：必须填理由，调 vault detokenize 后仅显示一次', async () => {
    const user = userEvent.setup()
    // 先验证 mock 层：理由不足直接 400
    const bad = await mockRequest('POST', '/api/v1/candidates/c-0001/reveal', { reason: 'abc' })
    expect(bad.ok).toBe(false)
    const okRes = await mockRequest('POST', '/api/v1/candidates/c-0001/reveal', { reason: '电话确认面试时间' })
    expect(okRes.ok).toBe(true)
    expect(okRes.data.phone).toBe('13800008000')

    // UI 层：填理由 → 显示完整号码一次
    renderApp()
    await screen.findByText('138****8000')
    await user.click(screen.getAllByText('查看详情')[0])
    await user.click(await screen.findByTestId('reveal-open'))
    await user.type(await screen.findByTestId('reveal-reason'), '电话联系候选人 c-0001 确认面试时间')
    await user.click(screen.getByTestId('reveal-submit'))
    await waitFor(() => {
      expect(screen.getByTestId('revealed-phone')).toHaveTextContent('13800008000')
    })
    // 关闭弹窗后不缓存
    fireEvent.click(screen.getByTestId('reveal-close'))
    await waitFor(() => {
      expect(screen.queryByTestId('revealed-phone')).not.toBeInTheDocument()
    }, { timeout: 5000 })
    expect(document.body.textContent).not.toContain('13800008000')
  })

  test('AC6：页面右下角存在个人水印（姓名 · 工号 · 日期）', () => {
    renderApp()
    const wm = document.querySelector('[data-testid="watermark"]')
    expect(wm).toBeInTheDocument()
    expect(wm.textContent).toContain('王招聘')
    expect(wm.textContent).toContain('EMP-1001')
    expect(wm.textContent).toMatch(/\d{4}-\d{2}-\d{2}/)
  })
})

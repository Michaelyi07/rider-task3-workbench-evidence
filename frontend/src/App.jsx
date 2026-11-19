import React, { useState } from 'react'
import { ConfigProvider, Layout, Menu, Typography, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import Candidates from './pages/Candidates'
import CandidateDetail from './pages/CandidateDetail'
import Watermark from './components/Watermark'
import { MOCK_USER } from './api/mock'

export default function App() {
  const [detailId, setDetailId] = useState(null)
  const { token } = theme.useToken()

  return (
    <ConfigProvider locale={zhCN}>
      <Layout style={{ minHeight: '100vh' }}>
        <Layout.Sider theme="dark">
          <div style={{ color: '#fff', padding: 16, fontWeight: 700 }}>ClawHunt 招聘工作台</div>
          <Menu
            theme="dark" mode="inline" selectedKeys={['candidates']}
            items={[{ key: 'candidates', label: '我的候选人' }]}
            onClick={() => setDetailId(null)}
          />
          <div style={{ color: 'rgba(255,255,255,0.45)', padding: 16, fontSize: 12 }}>
            Task 3/5 · 合成数据演示
          </div>
        </Layout.Sider>
        <Layout.Content style={{ padding: 24, background: token.colorBgLayout }}>
          {detailId ? (
            <CandidateDetail candidateId={detailId} onBack={() => setDetailId(null)} />
          ) : (
            <>
              <Typography.Title level={3}>我的候选人</Typography.Title>
              <Candidates onOpenDetail={setDetailId} />
            </>
          )}
        </Layout.Content>
        <Watermark user={MOCK_USER} />
      </Layout>
    </ConfigProvider>
  )
}

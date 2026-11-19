import React, { useEffect, useState } from 'react'
import { Button, Descriptions, Input, Modal, Space, Tag, Typography, message } from 'antd'
import { api, STATUS_LABEL } from '../api/mock'

const { TextArea } = Input

export default function CandidateDetail({ candidateId, onBack }) {
  const [rows, setRows] = useState(null)
  const [revealOpen, setRevealOpen] = useState(false)
  const [revealReason, setRevealReason] = useState('')
  const [revealedPhone, setRevealedPhone] = useState('') // 只显示一次，不在前端缓存
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  async function load() {
    const res = await api('GET', '/api/v1/candidates')
    if (res.ok) setRows(res.data.find(x => x.id === candidateId) || null)
  }
  useEffect(() => { load() }, [candidateId])

  if (!rows) return <Typography.Text>加载中…</Typography.Text>
  const c = rows

  async function doTransition(next) {
    const res = await api('POST', `/api/v1/candidates/${c.id}/transition`, { next, reason: '' })
    if (res.ok) { message.success(`已流转至：${STATUS_LABEL[next] || next}`); load() }
    else message.error(res.message)
  }

  // AC5：查看完整号码 —— 必须填理由，调 vault detokenize，只显示一次
  async function submitReveal() {
    const res = await api('POST', `/api/v1/candidates/${c.id}/reveal`, { reason: revealReason.trim() })
    if (res.ok) {
      setRevealedPhone(res.data.phone)
      message.warning('完整号码仅本次显示，关闭后不再缓存')
    } else {
      message.error(res.message)
    }
  }
  function closeReveal() {
    setRevealOpen(false)
    setRevealedPhone('')
    setRevealReason('')
  }

  // AC5：标记不合适 —— 无理由禁提交
  async function submitReject() {
    const res = await api('POST', `/api/v1/candidates/${c.id}/reject`, { status: 'rejected', reason: rejectReason.trim() })
    if (res.ok) {
      message.success('已标记不合适')
      setRejectOpen(false); setRejectReason('')
      load()
    } else message.error(res.message)
  }

  return (
    <div data-testid="candidate-detail">
      <Button onClick={onBack} style={{ marginBottom: 16 }}>← 返回列表</Button>
      <Typography.Title level={4}>
        候选人档案（{c.name_masked} / {c.phone_masked}）
      </Typography.Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button data-testid="confirm-interview" type="primary"
          disabled={!['complete'].includes(c.status)}
          onClick={() => doTransition('booked')}>确认面试</Button>
        <Button data-testid="handoff"
          onClick={() => doTransition('handoff')}>转人工跟进</Button>
        <Button data-testid="mark-unsuitable" danger onClick={() => setRejectOpen(true)}>标记不合适</Button>
        <Button data-testid="reveal-open" onClick={() => { setRevealOpen(true); setRevealedPhone('') }}>查看完整号码</Button>
      </Space>

      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="状态"><Tag color="blue">{STATUS_LABEL[c.status] || c.status}</Tag></Descriptions.Item>
        <Descriptions.Item label="资格初筛建议">
          {c.screening === 'ok' ? <Tag color="green">✓ 通过</Tag> : <Tag color="orange">! 待确认</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="出生年月">{c.birth_ym}</Descriptions.Item>
        <Descriptions.Item label="区域">{c.area_text}</Descriptions.Item>
        <Descriptions.Item label="工作类型">{c.job_type}</Descriptions.Item>
        <Descriptions.Item label="有电动车">{c.has_ebike === null ? '未知' : c.has_ebike ? '是' : '否'}</Descriptions.Item>
        <Descriptions.Item label="到岗时间">{c.start_text}</Descriptions.Item>
        <Descriptions.Item label="健康证">{c.health_cert}</Descriptions.Item>
        <Descriptions.Item label="经验" span={2}>{c.experience_text}</Descriptions.Item>
        <Descriptions.Item label="AI 建档摘要" span={2}>{c.ai_summary}</Descriptions.Item>
        <Descriptions.Item label="来源渠道">{c.source_channel}</Descriptions.Item>
        <Descriptions.Item label="意向站点">{c.station_id}</Descriptions.Item>
        <Descriptions.Item label="创建时间" span={2}>{c.created_at}</Descriptions.Item>
      </Descriptions>

      <Modal
        title="查看完整手机号（需填写理由，写入审计）"
        open={revealOpen}
        destroyOnClose
        onCancel={closeReveal}
        footer={[
          <Button key="cancel" data-testid="reveal-close" onClick={closeReveal}>关闭</Button>,
          <Button key="ok" data-testid="reveal-submit" type="primary" disabled={revealedPhone !== '' && revealReason === ''}
            onClick={submitReveal}>查看完整号码</Button>,
        ]}
      >
        {revealedPhone ? (
          <Typography.Paragraph data-testid="revealed-phone" copyable={false} style={{ fontSize: 18 }}>
            {revealedPhone}（仅本次显示）
          </Typography.Paragraph>
        ) : (
          <>
            <Typography.Paragraph type="secondary">
              理由不少于 5 个字符，将调用保险箱 detokenize 并写审计；号码只显示一次，不在前端缓存。
            </Typography.Paragraph>
            <TextArea data-testid="reveal-reason" rows={3}
              value={revealReason} onChange={e => setRevealReason(e.target.value)}
              placeholder="例如：电话联系候选人 c-0001 确认面试时间" />
          </>
        )}
      </Modal>

      <Modal
        title="标记不合适（必须填写理由）"
        open={rejectOpen}
        destroyOnClose
        onCancel={() => { setRejectOpen(false); setRejectReason('') }}
        footer={[
          <Button key="cancel" onClick={() => { setRejectOpen(false); setRejectReason('') }}>取消</Button>,
          <Button key="ok" data-testid="reject-submit" type="primary" danger
            disabled={rejectReason.trim() === ''}
            onClick={submitReject}>确认标记</Button>,
        ]}
      >
        <Typography.Paragraph type="secondary">录用与淘汰由人确认；理由必填（AC5）。</Typography.Paragraph>
        <TextArea data-testid="reject-reason" rows={3}
          value={rejectReason} onChange={e => setRejectReason(e.target.value)}
          placeholder="例如：健康证无法提供且无法到岗" />
      </Modal>
    </div>
  )
}

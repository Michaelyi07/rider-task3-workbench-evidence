import React, { useEffect, useState } from 'react'
import { Table, Input, Select, Tag, Button, Space, message } from 'antd'
import { api, STATUS_LABEL } from '../api/mock'

const STATUS_COLOR = {
  new: 'default', collecting: 'processing', complete: 'success', booked: 'cyan',
  interviewed: 'geekblue', hired: 'green', rejected: 'red', handoff: 'orange',
}

export default function Candidates({ onOpenDetail }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState(undefined)

  async function load() {
    setLoading(true)
    const res = await api('GET', '/api/v1/candidates')
    setLoading(false)
    if (res.ok) setRows(res.data)
    else message.error(res.message || '加载失败')
  }
  useEffect(() => { load() }, [])

  const filtered = rows.filter(r => {
    if (statusFilter && r.status !== statusFilter) return false
    if (!keyword) return true
    const k = keyword.toLowerCase()
    return (r.phone_masked || '').includes(k) ||
      (r.name_masked || '').includes(k) ||
      (r.source_channel || '').toLowerCase().includes(k) ||
      (r.station_id || '').toLowerCase().includes(k)
  })

  const columns = [
    { title: '姓名', dataIndex: 'name_masked', key: 'name_masked', width: 90 },
    { title: '手机号(脱敏)', dataIndex: 'phone_masked', key: 'phone_masked', width: 130 },
    { title: '来源', dataIndex: 'source_channel', key: 'source_channel', width: 130 },
    { title: '意向站点', dataIndex: 'station_id', key: 'station_id', width: 90 },
    {
      title: '意向度', dataIndex: 'interest_level', key: 'interest_level', width: 90,
      render: v => ({ high: <Tag color="green">高</Tag>, mid: <Tag color="gold">中</Tag>, low: <Tag>低</Tag> }[v] || v),
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: v => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v] || v}</Tag>,
    },
    {
      title: '操作', key: 'actions', width: 120,
      render: (_, r) => <Button type="link" onClick={() => onOpenDetail(r.id)}>查看详情</Button>,
    },
  ]

  return (
    <div data-testid="candidates-page">
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          data-testid="search-input"
          placeholder="搜索脱敏手机号/姓名/来源/站点"
          allowClear
          onSearch={setKeyword}
          onChange={e => { if (!e.target.value) setKeyword('') }}
          style={{ width: 280 }}
        />
        <Select
          data-testid="status-filter"
          placeholder="按状态筛选"
          allowClear
          style={{ width: 160 }}
          options={Object.entries(STATUS_LABEL).map(([v, label]) => ({ value: v, label }))}
          onChange={setStatusFilter}
        />
        <Button onClick={load}>刷新</Button>
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={filtered}
        pagination={{ pageSize: 10 }}
      />
    </div>
  )
}

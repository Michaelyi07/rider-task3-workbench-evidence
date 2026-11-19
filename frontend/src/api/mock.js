/**
 * 共用接口契约 v1 的前端内置 mock（AC5：不依赖后端起服即可演示工作台）。
 * 真实部署时设置 VITE_USE_MOCK=false 走 fetch 直连后端 /api/v1。
 * 逻辑与 src/main.py 后端一致：detokenize 需理由≥5字，reveal 只显示一次不缓存。
 */
import { maskPhone, maskName } from '../utils/mask'

export const MOCK_USER = { name: '王招聘', empId: 'EMP-1001' }

const FULL_PHONES = {
  phone_aaaa1111: '13800008000',
  phone_bbbb2222: '13922222666',
  phone_cccc3333: '13733335321',
  phone_dddd4444: '13644449042',
}
const FULL_NAMES = {
  name_aaaa1111: '王大明',
  name_bbbb2222: '李二红',
  name_cccc3333: '张小强',
  name_dddd4444: '陈四平',
}

const CANDIDATES = [
  {
    id: 'c-0001', name_token: 'name_aaaa1111', phone_token: 'phone_aaaa1111',
    birth_ym: '1995-03', area_text: '浦东新区 张江镇', job_type: 'fulltime',
    has_ebike: true, start_text: '随时到岗', experience_text: '2 年即时配送经验，熟悉浦东片区',
    health_cert: 'holding', source_channel: 'friend_referral', station_id: 'S1',
    status: 'complete', interest_level: 'high',
    ai_summary: '有全职意愿与电动车，健康证在手，可即时入职，初筛建议：通过（✓）',
    screening: 'ok',
    created_at: '2026-11-18 09:30:00',
  },
  {
    id: 'c-0002', name_token: 'name_bbbb2222', phone_token: 'phone_bbbb2222',
    birth_ym: '1998-11', area_text: '闵行区 莘庄镇', job_type: 'parttime',
    has_ebike: false, start_text: '本周五后', experience_text: '无配送经验，有服务业经历',
    health_cert: 'processing', source_channel: 'qr_poster', station_id: 'S2',
    status: 'collecting', interest_level: 'mid',
    ai_summary: '兼职意向，需补健康证与电动车确认，初筛建议：待确认（!）',
    screening: 'warn',
    created_at: '2026-11-18 10:12:00',
  },
  {
    id: 'c-0003', name_token: 'name_cccc3333', phone_token: 'phone_cccc3333',
    birth_ym: '2001-06', area_text: '徐汇区 田林街道', job_type: 'undecided',
    has_ebike: null, start_text: '下月初', experience_text: '应届生，无经验',
    health_cert: 'none', source_channel: 'wechat_group', station_id: 'S3',
    status: 'new', interest_level: 'low',
    ai_summary: '信息收集中，意向待确认',
    screening: 'warn',
    created_at: '2026-11-18 11:05:00',
  },
  {
    id: 'c-0004', name_token: 'name_dddd4444', phone_token: 'phone_dddd4444',
    birth_ym: '1993-01', area_text: '静安区 江宁路街道', job_type: 'fulltime',
    has_ebike: true, start_text: '随时到岗', experience_text: '5 年骑手经验，带过小组',
    health_cert: 'holding', source_channel: 'channel_import', station_id: 'S1',
    status: 'interviewed', interest_level: 'high',
    ai_summary: '资深骑手，初筛建议：通过（✓），已进入面试环节',
    screening: 'ok',
    created_at: '2026-11-17 15:40:00',
  },
]

function toOut(c) {
  return {
    ...c,
    phone_masked: maskPhone(FULL_PHONES[c.phone_token] || ''),
    name_masked: maskName(FULL_NAMES[c.name_token] || ''),
  }
}

const STATUS_LABEL = {
  new: '新线索', collecting: '收集中', complete: '建档完成', booked: '已约面',
  interviewed: '已面试', hired: '已录用', rejected: '不合适', handoff: '转人工',
}
export { STATUS_LABEL }

const STATUS_FLOW = {
  new: ['collecting', 'handoff'],
  collecting: ['complete', 'handoff'],
  complete: ['booked', 'handoff', 'rejected'],
  booked: ['interviewed', 'cancelled:booked'],
  interviewed: ['hired', 'rejected', 'handoff'],
  hired: [],
  rejected: [],
  handoff: [],
}

function ok(data) { return { ok: true, status: 200, data } }
function fail(status, code, message) { return { ok: false, status, code, message } }

/** 与后端 src/main.py 路由对齐的 mock 处理器。 */
export async function mockRequest(method, path, body) {
  await new Promise(r => setTimeout(r, 10))
  let m
  if (method === 'GET' && path === '/api/v1/candidates') {
    return ok(CANDIDATES.map(toOut))
  }
  if ((m = path.match(/^\/api\/v1\/candidates\/([\w-]+)\/reveal$/)) && method === 'POST') {
    const c = CANDIDATES.find(x => x.id === m[1])
    if (!c) return fail(404, 'NOT_FOUND', 'candidate missing')
    if (!body.reason || body.reason.trim().length < 5)
      return fail(400, 'DETOKENIZE_FAILED', 'reason must be at least 5 characters')
    return ok({ phone: FULL_PHONES[c.phone_token], reason: body.reason, one_time: true })
  }
  if ((m = path.match(/^\/api\/v1\/candidates\/([\w-]+)\/reject$/)) && method === 'POST') {
    const c = CANDIDATES.find(x => x.id === m[1])
    if (!c) return fail(404, 'NOT_FOUND', 'candidate missing')
    if (!body.reason) return fail(400, 'BAD_REQUEST', 'reason required')
    c.status = 'rejected'
    return ok(toOut(c))
  }
  if ((m = path.match(/^\/api\/v1\/candidates\/([\w-]+)\/transition$/)) && method === 'POST') {
    const c = CANDIDATES.find(x => x.id === m[1])
    if (!c) return fail(404, 'NOT_FOUND', 'candidate missing')
    const allowed = STATUS_FLOW[c.status] || []
    if (!allowed.includes(body.next)) return fail(400, 'ILLEGAL_TRANSITION', `illegal ${c.status} -> ${body.next}`)
    c.status = body.next
    return ok(toOut(c))
  }
  if (path === '/api/v1/vault/detokenize' && method === 'POST') {
    if (!body.reason || body.reason.trim().length < 5)
      return fail(400, 'DETOKENIZE_FAILED', 'reason must be at least 5 characters')
    const v = FULL_PHONES[body.token]
    if (!v) return fail(400, 'DETOKENIZE_FAILED', 'unknown token')
    return ok({ value: v })
  }
  return fail(404, 'NOT_FOUND', `no mock handler for ${method} ${path}`)
}

/** 统一入口：默认 mock；VITE_USE_MOCK=false 时直连真实后端。 */
export async function api(method, path, body) {
  const useMock = import.meta.env.VITE_USE_MOCK !== 'false'
  if (useMock) return mockRequest(method, path, body)
  const res = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  return { ok: res.ok, status: res.status, data }
}

/**
 * last30days-skill-cn — DeepSeek Harness 插件（Host 半边）
 *
 * 工具：
 *   - last30days_research      按主题检索最近 N 天中文平台讨论，输出附来源的报告
 *   - last30days_hot           全网热榜（微博/百度/抖音/头条/B站/知乎，可选科技与 HN）
 *   - last30days_install_skill 把随包的技能写入 ~/.dsh/skills，供技能目录扫描
 *
 * 依赖：Python 3（脚本不带第三方依赖也能跑；jieba / playwright 为可选增强）。
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const PACKAGE_DIR = path.dirname(fileURLToPath(import.meta.url))
const SKILL_DIR = path.join(PACKAGE_DIR, 'skills', 'last30days')
const SCRIPT = path.join(SKILL_DIR, 'scripts', 'last30days.py')
const SKILL_NAME = 'last30days-cn'

export const inject = ['tools']

const DEFAULT_TIMEOUT = 300000
let pythonCache = null

/** 依次尝试 python3 / python / py -3，返回可用的解释器与前置参数。 */
function resolvePython() {
  if (pythonCache) return pythonCache
  const forced = process.env.LAST30DAYS_PYTHON || process.env.PYTHON
  const candidates = forced
    ? [[forced, []]]
    : [
        ['python3', []],
        ['python', []],
        ['py', ['-3']],
      ]
  for (const [bin, prefix] of candidates) {
    try {
      execFileSync(bin, [...prefix, '--version'], { stdio: 'pipe', timeout: 20000 })
      pythonCache = { bin, prefix }
      return pythonCache
    } catch {
      /* 试下一个 */
    }
  }
  throw new Error(
    '找不到 Python 3。请安装 Python 3 并确保 python / python3 在 PATH 中，或用 LAST30DAYS_PYTHON 指定解释器路径。',
  )
}

/** 从混合了进度日志的输出里取出 JSON 主体。 */
function extractJson(text) {
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start === -1 || end <= start) return null
  try {
    return JSON.parse(text.slice(start, end + 1))
  } catch {
    return null
  }
}

function tail(text, limit = 1200) {
  const s = String(text || '').trim()
  return s.length <= limit ? s : s.slice(-limit)
}

function clip(value, limit = 24000) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return text.length <= limit ? text : `${text.slice(0, limit)}\n…（输出已截断，共 ${text.length} 字符）`
}

function runCli(args, timeoutMs) {
  const { bin, prefix } = resolvePython()
  if (!fs.existsSync(SCRIPT)) {
    throw new Error(`技能脚本缺失：${SCRIPT}。请确认包完整（skills/last30days/scripts）。`)
  }
  const env = {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  }
  try {
    const stdout = execFileSync(bin, [...prefix, SCRIPT, ...args], {
      cwd: SKILL_DIR,
      encoding: 'utf8',
      timeout: timeoutMs,
      maxBuffer: 64 * 1024 * 1024,
      env,
      windowsHide: true,
    })
    return { ok: true, stdout, stderr: '' }
  } catch (error) {
    return {
      ok: false,
      stdout: String(error.stdout || ''),
      stderr: String(error.stderr || error.message || error),
    }
  }
}

const outputSpec = {
  schema: {
    type: 'object',
    additionalProperties: true,
  },
  render: (_args, value) => clip(value),
}

function registerTools(ctx) {
  const tools = ctx.get ? ctx.get('tools') : ctx.tools
  if (!tools || typeof tools.register !== 'function') return []

  const disposers = []

  disposers.push(
    tools.register({
      name: 'last30days_research',
      description:
        '检索中国主流平台（微博、小红书、B站、知乎、抖音、微信公众号、百度、今日头条）最近 N 天关于某个主题的真实讨论，按相关度/时效/互动加权排序并跨平台聚类，返回附原始来源的报告。也可用 --global 追加 Hacker News / GitHub / Reddit 等海外来源。',
      parameters: {
        type: 'object',
        properties: {
          topic: { type: 'string', description: '要研究的主题，中文自然语言即可，例如「AI 编程助手」。' },
          days: { type: 'number', description: '回溯天数，默认 30。' },
          mode: {
            type: 'string',
            enum: ['default', 'quick', 'deep'],
            description: 'quick 更快（按问题类型挑选平台），deep 每平台抓更多页，默认 default。',
          },
          sources: {
            type: 'string',
            description: '逗号分隔的平台子集，例如 "bilibili,zhihu,xhs"；留空表示默认 8 个平台。',
          },
          global: { type: 'boolean', description: '同时检索海外来源（Hacker News / GitHub / Reddit）。' },
          emit: {
            type: 'string',
            enum: ['json', 'compact', 'md', 'html-path'],
            description: '输出格式：json 结构化结果（默认）、compact 精简文本、md Markdown、html-path 离线 HTML 报告路径。',
          },
          timeoutMs: { type: 'number', description: '命令超时毫秒数，默认 300000。' },
        },
        required: ['topic'],
        additionalProperties: false,
      },
      output: outputSpec,
      async execute(args = {}) {
        const topic = String(args.topic || '').trim()
        if (!topic) return { ok: false, error: 'topic 不能为空' }
        const emit = String(args.emit || 'json')
        const argv = [topic, '--emit', emit]
        if (args.days) argv.push('--days', String(Math.round(Number(args.days))))
        if (args.mode === 'quick') argv.push('--quick')
        if (args.mode === 'deep') argv.push('--deep')
        if (args.sources) argv.push('--search', String(args.sources))
        if (args.global) argv.push('--global')

        const res = runCli(argv, Number(args.timeoutMs) || DEFAULT_TIMEOUT)
        if (emit === 'json') {
          const data = extractJson(res.stdout)
          if (data) return { ok: res.ok, ...data }
          return {
            ok: false,
            error: res.ok ? '未能解析 JSON 输出' : '研究命令执行失败',
            stderr: tail(res.stderr),
            stdout: tail(res.stdout, 4000),
          }
        }
        return {
          ok: res.ok,
          topic,
          emit,
          text: clip(res.stdout),
          stderr: res.ok ? undefined : tail(res.stderr),
        }
      },
    }),
  )

  disposers.push(
    tools.register({
      name: 'last30days_hot',
      description:
        '查看今天的全网热榜：微博、百度、抖音、今日头条、B站、知乎，可选科技资讯与 Hacker News。可按关键词过滤，返回排名与原始链接。',
      parameters: {
        type: 'object',
        properties: {
          keyword: { type: 'string', description: '只看与这个词相关的热榜条目，留空表示全部。' },
          limit: { type: 'number', description: '每个榜单取前 N 条，默认由脚本决定。' },
          sources: {
            type: 'string',
            description: '逗号分隔的榜单分组，例如 "boards,news,global"。',
          },
          emit: {
            type: 'string',
            enum: ['json', 'compact', 'md', 'html-path'],
            description: '输出格式，默认 json。',
          },
          timeoutMs: { type: 'number', description: '命令超时毫秒数，默认 120000。' },
        },
        additionalProperties: false,
      },
      output: outputSpec,
      async execute(args = {}) {
        const emit = String(args.emit || 'json')
        const argv = ['--hot']
        if (args.keyword) argv.push(String(args.keyword))
        if (args.limit) argv.push('--hot-limit', String(Math.round(Number(args.limit))))
        if (args.sources) argv.push('--hot-sources', String(args.sources))
        argv.push('--emit', emit)

        const res = runCli(argv, Number(args.timeoutMs) || 120000)
        if (emit === 'json') {
          const data = extractJson(res.stdout)
          if (data) return { ok: res.ok, ...data }
          return {
            ok: false,
            error: res.ok ? '未能解析 JSON 输出' : '热榜命令执行失败',
            stderr: tail(res.stderr),
            stdout: tail(res.stdout, 4000),
          }
        }
        return {
          ok: res.ok,
          emit,
          text: clip(res.stdout),
          stderr: res.ok ? undefined : tail(res.stderr),
        }
      },
    }),
  )

  disposers.push(
    tools.register({
      name: 'last30days_install_skill',
      description:
        '把随包的 last30days-cn 技能安装到 ~/.dsh/skills（或 DSH_SKILLS_DIR），让它出现在 DSH 的技能目录里，可通过 /last30days-cn 或自然语言调用。幂等，默认不覆盖已存在的安装。',
      parameters: {
        type: 'object',
        properties: {
          force: { type: 'boolean', description: '覆盖已存在的安装。' },
        },
        additionalProperties: false,
      },
      output: outputSpec,
      async execute(args = {}) {
        const base = process.env.DSH_SKILLS_DIR || path.join(os.homedir(), '.dsh', 'skills')
        const dest = path.join(base, SKILL_NAME)
        if (!fs.existsSync(SKILL_DIR)) {
          return { ok: false, error: `随包技能目录缺失：${SKILL_DIR}` }
        }
        if (fs.existsSync(dest) && !args.force) {
          return { ok: true, installed: false, path: dest, note: '已安装；需要覆盖请传 force=true' }
        }
        fs.mkdirSync(path.dirname(dest), { recursive: true })
        fs.rmSync(dest, { recursive: true, force: true })
        fs.cpSync(SKILL_DIR, dest, { recursive: true })
        return { ok: true, installed: true, path: dest, note: '重启 DSH 或重新加载技能后可见' }
      },
    }),
  )

  return disposers
}

export function apply(ctx) {
  const disposers = registerTools(ctx)
  const dispose = () => {
    for (const d of disposers) {
      try {
        if (typeof d === 'function') d()
      } catch {
        /* noop */
      }
    }
  }
  if (ctx && typeof ctx.effect === 'function') {
    ctx.effect(() => dispose)
  }
  return dispose
}

/**
 * last30days-skill-cn — DeepSeek Harness 插件（Host 半边）
 *
 * 工具：
 *   - last30days_research      按主题检索最近 N 天中文平台讨论，输出附来源的报告
 *   - last30days_hot           全网热榜（微博/百度/抖音/头条/B站/知乎，可选科技与 HN）
 *   - last30days_install_skill 把随包的技能写入 ~/.dsh/skills，供技能目录扫描
 *
 * 依赖：Python 3.8+（脚本不带第三方依赖也能跑；jieba / playwright 为可选增强）。
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'

const execFileAsync = promisify(execFile)

const PACKAGE_DIR = path.dirname(fileURLToPath(import.meta.url))
const SKILL_DIR = path.join(PACKAGE_DIR, 'skills', 'last30days')
const SCRIPT = path.join(SKILL_DIR, 'scripts', 'last30days.py')
const SKILL_NAME = 'last30days-cn'

export const inject = ['tools']

const DEFAULT_TIMEOUT = 300000
let pythonCache = null

/** 依次尝试 python3 / python / py -3，返回可用的解释器与前置参数。 */
async function resolvePython(signal) {
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
      await execFileAsync(bin, [...prefix, '-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'], { timeout: 20000, signal })
      pythonCache = { bin, prefix }
      return pythonCache
    } catch {
      signal?.throwIfAborted()
      /* 试下一个 */
    }
  }
  throw new Error(
    '找不到 Python 3.8+。请安装 Python 3.8+ 并确保 python / python3 在 PATH 中，或用 LAST30DAYS_PYTHON 指定解释器路径。',
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

async function runCli(args, timeoutMs, signal) {
  try {
    const { bin, prefix } = await resolvePython(signal)
    if (!fs.existsSync(SCRIPT)) {
      throw new Error(`技能脚本缺失：${SCRIPT}。请确认包完整（skills/last30days/scripts）。`)
    }
    const env = {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
    }
    const { stdout, stderr } = await execFileAsync(bin, [...prefix, SCRIPT, ...args], {
      cwd: SKILL_DIR,
      encoding: 'utf8',
      timeout: timeoutMs,
      signal,
      maxBuffer: 64 * 1024 * 1024,
      env,
      windowsHide: true,
    })
    return { ok: true, stdout, stderr }
  } catch (error) {
    return {
      ok: false,
      stdout: String(error.stdout || ''),
      stderr: String(error.stderr || error.message || error),
    }
  }
}

function validateArgs(args) {
  for (const [key, max] of [['days', 30], ['limit', 1000], ['timeoutMs', 2147483647]]) {
    if (args[key] !== undefined && (!Number.isSafeInteger(args[key]) || args[key] < 1 || args[key] > max)) {
      return `${key} 必须是 1 到 ${max} 的整数`
    }
  }
  for (const key of ['topic', 'keyword', 'sources']) {
    if (args[key] !== undefined && (typeof args[key] !== 'string' || args[key].includes('\0'))) return `${key} 必须是有效字符串`
  }
  if (args.emit !== undefined && !['json', 'compact', 'md', 'html-path'].includes(args.emit)) return '无效的 emit'
  if (args.mode !== undefined && !['default', 'quick', 'deep'].includes(args.mode)) return '无效的 mode'
  return null
}

const outputSpec = {
  schema: {
    type: 'object',
    additionalProperties: true,
  },
  render: (_args, value) => [{ type: 'text', text: clip(value) }],
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
          days: { type: 'integer', description: '回溯天数，1–30，默认 30。' },
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
      async execute(args = {}, exec = {}) {
        const topic = String(args.topic || '').trim()
        if (!topic) return { ok: false, error: 'topic 不能为空' }
        const error = validateArgs(args)
        if (error) return { ok: false, error }
        const emit = args.emit || 'json'
        const argv = ['--literal-topic', '--emit', emit]
        if (args.days !== undefined) argv.push('--days', String(args.days))
        if (args.mode === 'quick') argv.push('--quick')
        if (args.mode === 'deep') argv.push('--deep')
        if (args.sources) argv.push('--search', String(args.sources))
        if (args.global) argv.push('--global')
        argv.push('--', topic)

        const res = await runCli(argv, args.timeoutMs ?? DEFAULT_TIMEOUT, exec.signal)
        if (emit === 'json') {
          const data = extractJson(res.stdout)
          if (data) return { ...data, ok: res.ok, ...(res.ok ? {} : { stderr: tail(res.stderr) }) }
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
          stderr: res.ok ? '' : tail(res.stderr),
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
          limit: { type: 'integer', description: '每个榜单取前 N 条，1–1000，默认由脚本决定。' },
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
      async execute(args = {}, exec = {}) {
        const error = validateArgs(args)
        if (error) return { ok: false, error }
        const emit = args.emit || 'json'
        const argv = ['--hot', '--literal-topic']
        if (args.limit !== undefined) argv.push('--hot-limit', String(args.limit))
        if (args.sources) argv.push('--hot-sources', String(args.sources))
        argv.push('--emit', emit)
        if (args.keyword) argv.push('--', args.keyword)

        const res = await runCli(argv, args.timeoutMs ?? 120000, exec.signal)
        if (emit === 'json') {
          const data = extractJson(res.stdout)
          if (data) return { ...data, ok: res.ok, ...(res.ok ? {} : { stderr: tail(res.stderr) }) }
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
          stderr: res.ok ? '' : tail(res.stderr),
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
        const base = path.resolve(process.env.DSH_SKILLS_DIR || path.join(os.homedir(), '.dsh', 'skills'))
        const dest = path.join(base, SKILL_NAME)
        let staging
        let backup
        try {
          if (args.force !== undefined && typeof args.force !== 'boolean') throw new Error('force 必须是布尔值')
          if (!fs.existsSync(path.join(SKILL_DIR, 'SKILL.md'))) throw new Error(`随包技能目录缺失：${SKILL_DIR}`)
          const existing = fs.lstatSync(dest, { throwIfNoEntry: false })
          if (existing && (!existing.isDirectory() || existing.isSymbolicLink())) throw new Error('安装目标必须是普通目录，不能是文件或符号链接')
          if (existing && !args.force) {
            return { ok: true, installed: false, path: dest, note: '已安装；需要覆盖请传 force=true' }
          }
          fs.mkdirSync(base, { recursive: true })
          staging = fs.mkdtempSync(path.join(base, '.last30days-stage-'))
          const payload = path.join(staging, 'payload')
          fs.cpSync(SKILL_DIR, payload, { recursive: true })
          // Stage the complete payload before moving an existing installation.
          if (existing) {
            const previous = path.join(staging, 'previous')
            fs.renameSync(dest, previous)
            backup = previous
          }
          try {
            fs.renameSync(payload, dest)
          } catch (error) {
            if (backup) {
              fs.renameSync(backup, dest)
              backup = undefined
            }
            throw error
          }
          backup = undefined
          return { ok: true, installed: true, path: dest, note: '重启 DSH 或重新加载技能后可见' }
        } catch (error) {
          return { ok: false, error: error.message, ...(backup ? { backup } : {}) }
        } finally {
          // Keep the backup for recovery if rollback itself failed.
          if (staging && !backup) {
            try { fs.rmSync(staging, { recursive: true, force: true }) } catch { /* best-effort cleanup */ }
          }
        }
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

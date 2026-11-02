// Offline regression tests: run the wrapper against an isolated Python fixture.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { test, after } from 'node:test'

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'last30days-dsh-test-'))
const skill = path.join(root, 'skills/last30days')
fs.mkdirSync(path.join(skill, 'scripts'), { recursive: true })
fs.copyFileSync(new URL('../index.js', import.meta.url), path.join(root, 'index.mjs'))
fs.writeFileSync(path.join(skill, 'SKILL.md'), '---\nname: last30days-cn\n---\nTest skill\n')
fs.writeFileSync(path.join(skill, 'scripts/last30days.py'), `
import json, sys, time
args = sys.argv[1:]
if '--' in args and args[-1] == 'slow':
    time.sleep(5)
if '--' in args and args[-1] == 'fail':
    print(json.dumps({'ok': True, 'partial': True}))
    print('fixture failure', file=sys.stderr)
    sys.exit(1)
print(json.dumps({'argv': args}))
`)
const oldDir = process.env.DSH_SKILLS_DIR
process.env.DSH_SKILLS_DIR = path.join(root, 'installed')
after(() => {
  if (oldDir === undefined) delete process.env.DSH_SKILLS_DIR
  else process.env.DSH_SKILLS_DIR = oldDir
  fs.rmSync(root, { recursive: true, force: true })
})
const tools = new Map()
let cleanup
const { apply } = await import(pathToFileURL(path.join(root, 'index.mjs')))
const dispose = apply({
  get: () => ({ register(def) { tools.set(def.name, def); return () => tools.delete(def.name) } }),
  effect(fn) { cleanup = fn() },
})
const research = tools.get('last30days_research')
const hot = tools.get('last30days_hot')
const install = tools.get('last30days_install_skill')

test('registers all tools and renders DSH content blocks', () => {
  assert.equal(tools.size, 3)
  assert.deepEqual(hot.output.render({}, { ok: true }), [{ type: 'text', text: '{\n  "ok": true\n}' }])
})
test('passes research options and literal topic as separate argv', async () => {
  const res = await research.execute({ topic: '--diagnose', days: 7, mode: 'deep', sources: 'bilibili', global: true })
  assert.equal(res.ok, true, JSON.stringify(res))
  assert.deepEqual(res.argv, ['--literal-topic', '--emit', 'json', '--days', '7', '--deep', '--search', 'bilibili', '--global', '--', '--diagnose'])
})
test('hot filters remain literal even for management command names', async () => {
  const res = await hot.execute({ keyword: 'setup', limit: 2, sources: 'boards' })
  assert.equal(res.ok, true)
  assert.deepEqual(res.argv, ['--hot', '--literal-topic', '--hot-limit', '2', '--hot-sources', 'boards', '--emit', 'json', '--', 'setup'])
})
test('rejects invalid numeric and format arguments', async () => {
  for (const args of [{days: 0}, {days: 31}, {days: 1.5}, {timeoutMs: -1}, {timeoutMs: Infinity}, {emit: 'bad'}, {topic: 12}]) {
    assert.equal((await research.execute({topic: 'test', ...args})).ok, false)
  }
  assert.equal((await hot.execute({limit: 0})).ok, false)
})
test('text outputs contain only JSON-compatible values', async () => {
  const res = await hot.execute({emit: 'compact'})
  assert.equal(res.ok, true)
  assert.deepEqual(JSON.parse(JSON.stringify(res)), res)
})
test('nonzero exit preserves failure and diagnostics despite payload ok=true', async () => {
  const res = await research.execute({topic: 'fail'})
  assert.equal(res.ok, false)
  assert.equal(res.partial, true)
  assert.match(res.stderr, /fixture failure/)
})
test('timeout does not block the host event loop', async () => {
  let ticked = false
  const timer = setTimeout(() => { ticked = true }, 20)
  const res = await research.execute({topic: 'slow', timeoutMs: 150})
  clearTimeout(timer)
  assert.equal(ticked, true)
  assert.equal(res.ok, false)
})
test('forwards host cancellation to the child process', async () => {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 30)
  const res = await hot.execute({keyword: 'slow'}, {signal: controller.signal})
  clearTimeout(timer)
  assert.equal(res.ok, false)
})
test('install is isolated, idempotent and force replaces only the target', async () => {
  const first = await install.execute()
  assert.equal(first.installed, true)
  const marker = path.join(first.path, 'user-file')
  fs.writeFileSync(marker, 'keep')
  assert.equal((await install.execute()).installed, false)
  assert.equal(fs.readFileSync(marker, 'utf8'), 'keep')
  assert.equal((await install.execute({force: true})).installed, true)
  assert.equal(fs.existsSync(marker), false)
})
test('failed copy preserves the previous installation', async () => {
  const dest = path.join(process.env.DSH_SKILLS_DIR, 'last30days-cn')
  fs.writeFileSync(path.join(dest, 'user-file'), 'keep')
  const original = fs.cpSync
  fs.cpSync = () => { throw new Error('simulated disk full') }
  try { assert.equal((await install.execute({force: true})).ok, false) }
  finally { fs.cpSync = original }
  assert.equal(fs.readFileSync(path.join(dest, 'user-file'), 'utf8'), 'keep')
})
test('failed publish rolls the previous installation back', async () => {
  const dest = path.join(process.env.DSH_SKILLS_DIR, 'last30days-cn')
  const original = fs.renameSync
  fs.renameSync = (src, target) => {
    if (path.basename(src) === 'payload') throw new Error('simulated rename failure')
    return original(src, target)
  }
  try { assert.equal((await install.execute({force: true})).ok, false) }
  finally { fs.renameSync = original }
  assert.equal(fs.readFileSync(path.join(dest, 'user-file'), 'utf8'), 'keep')
})
test('rejects symlink install targets without changing their contents', { skip: process.platform === 'win32' }, async () => {
  const dest = path.join(process.env.DSH_SKILLS_DIR, 'last30days-cn')
  const outside = path.join(root, 'outside')
  fs.mkdirSync(outside)
  fs.writeFileSync(path.join(outside, 'keep'), 'safe')
  fs.rmSync(dest, { recursive: true })
  fs.symlinkSync(outside, dest, 'dir')
  assert.equal((await install.execute({force: true})).ok, false)
  assert.equal(fs.readFileSync(path.join(outside, 'keep'), 'utf8'), 'safe')
  fs.unlinkSync(dest)
})
test('missing Python is returned as a tool error', async () => {
  const previous = process.env.LAST30DAYS_PYTHON
  process.env.LAST30DAYS_PYTHON = path.join(root, 'missing-python')
  try {
    const fresh = await import(`${pathToFileURL(path.join(root, 'index.mjs'))}?missing-python`)
    const registered = new Map()
    const stop = fresh.apply({ tools: { register(def) { registered.set(def.name, def) } } })
    const res = await registered.get('last30days_hot').execute()
    assert.equal(res.ok, false)
    assert.match(res.stderr, /Python/)
    stop()
  } finally {
    if (previous === undefined) delete process.env.LAST30DAYS_PYTHON
    else process.env.LAST30DAYS_PYTHON = previous
  }
})
test('disposes registered tools', () => {
  cleanup()
  dispose()
  assert.equal(tools.size, 0)
})

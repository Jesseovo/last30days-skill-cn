// 本地自测：模拟 DSH 的 ctx，验证插件能注册工具并真实执行
import { apply, inject } from '../index.js'

const registered = new Map()

const fakeCtx = {
  get(name) {
    if (name !== 'tools') return undefined
    return {
      register(def) {
        if (!def.name) throw new Error('tool needs a name')
        if (typeof def.execute !== 'function') throw new Error(`${def.name}: execute must be a function`)
        if (!def.output || typeof def.output.render !== 'function') throw new Error(`${def.name}: output.render required`)
        registered.set(def.name, def)
        return () => registered.delete(def.name)
      },
    }
  },
  effect(fn) {
    fn()
  },
}

console.log('inject =', inject)
const dispose = apply(fakeCtx)
console.log('registered tools =', [...registered.keys()])

const hot = registered.get('last30days_hot')
const res = await hot.execute({ limit: 2, emit: 'json' })
console.log('hot ok =', res.ok)
if (res.boards) {
  for (const [id, board] of Object.entries(res.boards)) {
    console.log(`  ${id}: ${board.items?.length || 0} 条  首条 = ${board.items?.[0]?.title || '-'}`)
  }
} else {
  console.log('  payload keys =', Object.keys(res).join(','))
}

const install = registered.get('last30days_install_skill')
const inst = await install.execute({})
console.log('install_skill =', JSON.stringify(inst))

typeof dispose === 'function' && dispose()
console.log('after dispose, tools =', [...registered.keys()].length)

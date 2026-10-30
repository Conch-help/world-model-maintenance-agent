/**
 * Run the real AGH maintenance task and export the session.
 *
 * Preconditions:
 *   - AGH provider is configured with a valid Agnes API key.
 *   - wm-maintenance-agent MCP server is trusted and enabled.
 *
 * Usage:
 *   AGH_ENTRY=/absolute/path/to/agnes.mjs \
 *   AGH_HOME=/absolute/path/to/agh-home \
 *   PROJECT_ROOT=/absolute/path/to/world-model-maintenance-agent \
 *   node scripts/agh_real_run.mjs
 */
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const project = resolve(process.env.PROJECT_ROOT ?? process.cwd())
const entry = resolve(process.env.AGH_ENTRY ?? '')
const home = resolve(process.env.AGH_HOME ?? '')
if (!process.env.AGH_ENTRY || !process.env.AGH_HOME) throw new Error('AGH_ENTRY and AGH_HOME are required')
const env = { ...process.env, AGH_HOME: home, AGNES_PROFILE: process.env.AGNES_PROFILE ?? 'local-dev' }
const run = (args) => new Promise((resolveRun, reject) => {
  const child = execFile(process.execPath, [entry, ...args], { cwd: project, env, timeout: 180000, maxBuffer: 8 * 1024 * 1024 }, (error, stdout, stderr) => {
    if (error) reject(Object.assign(new Error(`${stderr || String(error)}\nSTDOUT=${stdout}`), { cause: error }))
    else resolveRun({ stdout, stderr })
  })
  child.stdin.end('')
})

await run(['daemon', 'start'])
const config = JSON.parse(await readFile(`${home}/profiles/${env.AGNES_PROFILE}/configuration.json`, 'utf8'))
const account = config.accounts?.find((item) => item.accountId === config.defaultAccountId) ?? config.accounts?.[0]
if (!account) throw new Error('no configured provider account')
const modelSelector = `primary=${account.route}/${account.model}`
const prompt = [
  'Use wm-maint-python to complete an industrial maintenance loop:',
  '1) read the current plant state;',
  '2) plan 12–24 hours of maintenance and production with the world model;',
  '3) verify the plan with the independent high-fidelity digital twin;',
  '4) request approval for the first state-changing action with approved=false;',
  '5) only after explicit human approval, execute with approved=true;',
  '6) export the hash-chained trace and summarize predicted vs verified outcomes.',
].join(' ')
await run(['-p', '--mode', 'json', '--model', modelSelector, prompt])
const sessions = JSON.parse((await run(['sessions', 'list', '--json'])).stdout)
const sessionId = sessions.items[0]?.sessionId
if (!sessionId) throw new Error('no AGH session found')
const exportPath = `${project}/artifacts/agh_real_session.json`
await run(['export', sessionId, '--raw', '--out', exportPath])
console.log(JSON.stringify({ sessionId, exportPath, model: account.model, route: account.route }, null, 2))

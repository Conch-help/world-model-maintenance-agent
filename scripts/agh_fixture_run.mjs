/**
 * AGH integration fixture.
 *
 * This script proves that the project MCP server is mounted, catalogued and
 * invoked through the real AGH process. It deliberately uses a local
 * deterministic model fixture, so it is not evidence of a real Agnes inference.
 * For submission, run the same prompt with the organisers' Agnes key and export
 * the resulting AGH session.
 *
 * Usage from an AGH source checkout:
 *   node --import tsx <this-file>
 *
 * Environment:
 *   AGH_ENTRY     absolute path to built agnes.mjs
 *   AGH_HOME      isolated AGH home directory
 *   PROJECT_ROOT  this project root
 */
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { randomBytes } from 'node:crypto'
import { resolve } from 'node:path'

const project = resolve(process.env.PROJECT_ROOT ?? process.cwd())
const root = resolve(project, '..')
const entry = resolve(process.env.AGH_ENTRY ?? `${root}/work/agh-build/agnes.mjs`)
const home = resolve(process.env.AGH_HOME ?? `${root}/work/agh-home2`)
const env = { ...process.env, AGH_HOME: home, AGNES_PROFILE: 'local-dev' }
const model = 'deepseek-v4-pro'
const apiKey = randomBytes(24).toString('hex')
const requests = []

const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/v1/models') {
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ data: [{ id: model, object: 'model', owned_by: 'fixture' }] }))
    return
  }
  if (req.method !== 'POST' || req.url !== '/v1/chat/completions') { res.writeHead(404).end(); return }
  const chunks = []
  for await (const chunk of req) chunks.push(Buffer.from(chunk))
  const body = JSON.parse(Buffer.concat(chunks).toString())
  const toolNames = Array.isArray(body.tools) ? body.tools.map((t) => t?.function?.name).filter(Boolean) : []
  requests.push({ toolNames, messages: body.messages })
  const findBySuffix = (suffix) => toolNames.find((name) => name.endsWith(suffix))
  const step = requests.length - 1
  let toolName
  let toolArgs = {}
  if (step === 0) toolName = findBySuffix('_plant_read_state')
  else if (step === 1) { toolName = findBySuffix('_world_model_plan'); toolArgs = { horizon: 12 } }
  else if (step === 2) { toolName = findBySuffix('_highfidelity_verify'); toolArgs = { plan_id: 'PLAN-20261008-0' } }
  else if (step === 3) toolName = findBySuffix('_trace_export')
  const event = { id: `wm-fixture-${requests.length}`, object: 'chat.completion.chunk', created: 0, model }
  const delta = toolName
    ? { role: 'assistant', tool_calls: [{ index: 0, id: `wm-call-${step}`, type: 'function', function: { name: toolName, arguments: JSON.stringify(toolArgs) } }] }
    : { role: 'assistant', content: 'AGH world-model maintenance loop complete.' }
  res.writeHead(200, { 'Content-Type': 'text/event-stream' })
  res.write(`data: ${JSON.stringify({ ...event, choices: [{ index: 0, delta, finish_reason: null }] })}\n\n`)
  res.end(`data: ${JSON.stringify({ ...event, choices: [{ index: 0, delta: {}, finish_reason: toolName ? 'tool_calls' : 'stop' }], usage: { prompt_tokens: 8, completion_tokens: 5, total_tokens: 13 } })}\n\ndata: [DONE]\n\n`)
})
await new Promise((resolveServer, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveServer) })
const address = server.address()
const baseUrl = `http://127.0.0.1:${address.port}/v1`

const run = (args, input) => new Promise((resolveRun, reject) => {
  const child = execFile(process.execPath, [entry, ...args], { cwd: project, env, timeout: 120000, maxBuffer: 8 * 1024 * 1024 }, (error, stdout, stderr) => {
    if (error) reject(Object.assign(new Error(`${stderr || String(error)}\nSTDOUT=${stdout}`), { cause: error }))
    else resolveRun({ stdout, stderr })
  })
  child.stdin.end(input ?? '')
})

try {
  const configInput = `Agnes Fixture\n1\n${baseUrl}\n${apiKey}\n1\n1\n`
  await run(['config'], configInput)
  await run(['daemon', 'stop'])
  await run(['daemon', 'start'])
  const cfg = JSON.parse(await readFile(`${home}/profiles/local-dev/configuration.json`, 'utf8'))
  const route = cfg.accounts[0].route
  const prompt = 'Use wm-maint-python to read state, plan maintenance, verify the plan, then export the trace. Do not perform a state-changing action.'
  const answer = await run(['-p', '--mode', 'json', '--model', `primary=${route}/${model}`, prompt])
  const sessions = JSON.parse((await run(['sessions', 'list', '--json'])).stdout)
  const sessionId = sessions.items[0]?.sessionId
  if (!sessionId) throw new Error('no session id')
  const exportPath = `${project}/artifacts/agh_toolchain_session.json`
  await run(['export', sessionId, '--raw', '--out', exportPath])
  console.log('AGH TOOLCHAIN FIXTURE SESSION OK')
  console.log(JSON.stringify({ sessionId, exportPath, requests: requests.map((r) => r.toolNames.filter((n) => n.includes('wm_maint'))), answer: answer.stdout.slice(0,1200) }, null, 2))
} finally {
  await new Promise((resolveServer) => server.close(resolveServer))
}

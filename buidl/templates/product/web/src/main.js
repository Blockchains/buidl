import { createPublicClient, createWalletClient, custom, http, defineChain, formatEther, parseEther } from 'viem'
import content from './content.json'
import project from './project.json'
import { parseArg, formatResult, splitAbi, storageKey } from './abi.js'

const $ = (id) => document.getElementById(id)
const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props)
  for (const k of kids) n.append(k)
  return n
}
const log = (msg) => { $('log').textContent = `${new Date().toLocaleTimeString()}  ${msg}\n` + $('log').textContent }

// ---- chain -------------------------------------------------------------
// Chain comes from the plan (name, id, public RPC, explorer) - no bundled chain registry needed.
const chain = defineChain({
  id: project.chain.id, name: project.chain.name,
  nativeCurrency: { name: 'Ether', symbol: project.chain.symbol || 'ETH', decimals: 18 },
  rpcUrls: { default: { http: [project.chain.rpc] } },
  blockExplorers: project.chain.explorer ? { default: { name: 'Explorer', url: project.chain.explorer } } : undefined,
})
const rpc = project.chain.rpc || chain.rpcUrls.default.http[0]
const publicClient = createPublicClient({ chain, transport: http(rpc) })
const explorer = project.chain.explorer || chain.blockExplorers?.default?.url || ''
let walletClient = null
let account = null
let artifact = null
let address = null

// ---- static content ----------------------------------------------------
document.title = `${project.title} — ${content.hero_sub}`
document.querySelector('meta[name=description]').content = content.hero_sub
$('brand').textContent = project.title
$('hero-title').textContent = content.hero_title
$('hero-sub').textContent = content.hero_sub
$('problem').textContent = content.problem
$('solution').textContent = content.solution
for (const f of content.features) $('features').append(el('div', { className: 'card' }, el('h3', { textContent: f.title }), el('p', { textContent: f.text })))
for (const s of content.how_it_works) $('how-list').append(el('li', { textContent: s }))
for (const t of project.tracks || []) {
  $('track-list').append(el('div', { className: 'card' }, el('h3', { textContent: t.track }), el('p', { className: 'muted', textContent: t.sponsor || '' }), el('p', { textContent: t.integration || t.why || '' })))
}
const blocks = el('p', { className: 'muted', textContent: 'Built from: ' })
for (const b of project.blocks || []) blocks.append(el('a', { className: 'tag', href: `https://github.com/${b}`, textContent: b }))
$('blocks').append(blocks)
for (const d of project.docs || []) $('docs').append(el('li', {}, el('a', { href: d.href, textContent: d.title })))

async function chainLine() {
  try {
    const bn = await publicClient.getBlockNumber()
    $('chain-line').textContent = `Target chain: ${chain.name} (id ${chain.id}) · live block #${bn} via public RPC`
  } catch (e) {
    $('chain-line').textContent = `Target chain: ${chain.name} (id ${chain.id}) · public RPC unreachable: ${e.shortMessage || e.message}`
  }
}
chainLine()

// ---- wallet ------------------------------------------------------------
async function ensureChain() {
  const eth = window.ethereum
  const hex = '0x' + chain.id.toString(16)
  try {
    await eth.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: hex }] })
  } catch (e) {
    if (e.code !== 4902) throw e
    await eth.request({ method: 'wallet_addEthereumChain', params: [{ chainId: hex, chainName: chain.name, nativeCurrency: chain.nativeCurrency, rpcUrls: [rpc], blockExplorerUrls: explorer ? [explorer] : [] }] })
  }
}

$('connect').onclick = async () => {
  if (!window.ethereum) { log('No injected wallet found. Install MetaMask, Rabby or Coinbase Wallet, then reload.'); return }
  try {
    walletClient = createWalletClient({ chain, transport: custom(window.ethereum) })
    ;[account] = await walletClient.requestAddresses()
    await ensureChain()
    const bal = await publicClient.getBalance({ address: account })
    $('wallet-status').textContent = `Connected ${account} on ${chain.name} · balance ${formatEther(bal)} ${chain.nativeCurrency.symbol}`
    $('connect').textContent = account.slice(0, 6) + '…' + account.slice(-4)
    log('wallet connected')
  } catch (e) { log('connect failed: ' + (e.shortMessage || e.message)) }
}

// ---- contract ----------------------------------------------------------
function setAddress(a) {
  address = a
  $('addr').value = a || ''
  if (a) localStorage.setItem(storageKey(project.slug, chain.id), a)
  renderFunctions()
}
$('use-addr').onclick = () => {
  const v = $('addr').value.trim()
  if (!/^0x[0-9a-fA-F]{40}$/.test(v)) return log('not an address')
  setAddress(v)
}

function inputsFor(inputs, prefix) {
  return inputs.map((inp, i) => el('label', { textContent: `${inp.name || 'arg' + i} (${inp.type})` }, el('input', { id: `${prefix}-${i}`, placeholder: inp.type.includes('[') ? '["…"]' : inp.type })))
}
function readInputs(inputs, prefix) {
  return inputs.map((inp, i) => parseArg(inp.type, $(`${prefix}-${i}`).value))
}

function renderDeploy() {
  const { ctor } = splitAbi(artifact.abi)
  const box = $('deploy-box')
  box.replaceChildren()
  const btn = el('button', { className: 'btn', textContent: `Deploy ${project.contract} to ${chain.name}` })
  const row = el('div', { className: 'row' }, ...inputsFor(ctor.inputs, 'ctor'), btn)
  box.append(el('h3', { textContent: 'Deploy (from your wallet, no backend)' }), row)
  btn.onclick = async () => {
    if (!walletClient) return log('connect a wallet first')
    try {
      await ensureChain()
      const hash = await walletClient.deployContract({ abi: artifact.abi, bytecode: artifact.bytecode, args: readInputs(ctor.inputs, 'ctor'), account })
      log(`deploy tx ${hash} ${explorer ? explorer + '/tx/' + hash : ''}`)
      const rcpt = await publicClient.waitForTransactionReceipt({ hash })
      log(`deployed at ${rcpt.contractAddress}`)
      setAddress(rcpt.contractAddress)
    } catch (e) { log('deploy failed: ' + (e.shortMessage || e.message)) }
  }
}

function renderFunctions() {
  const box = $('fns')
  box.replaceChildren()
  if (!artifact) return
  if (!address) { box.append(el('p', { className: 'muted', textContent: 'Deploy or paste a contract address to interact.' })); return }
  box.append(el('p', {}, 'Contract ', el('a', { href: explorer ? `${explorer}/address/${address}` : '#', textContent: address })))
  const { reads, writes } = splitAbi(artifact.abi)
  for (const [kind, list] of [['read', reads], ['write', writes]]) {
    for (const f of list) {
      const id = `${kind}-${f.name}-${f.inputs.length}`
      const btn = el('button', { className: kind === 'read' ? 'btn ghost' : 'btn', textContent: kind === 'read' ? 'Read' : 'Send' })
      const kids = inputsFor(f.inputs, id)
      if (f.stateMutability === 'payable') kids.push(el('label', { textContent: `value (${chain.nativeCurrency.symbol})` }, el('input', { id: `${id}-value`, placeholder: '0.01' })))
      const help = (content.function_help || {})[f.name]
      box.append(el('div', { className: 'fn' }, el('code', { textContent: `${f.name}(${f.inputs.map((x) => x.type).join(', ')})` }),
        help ? el('p', { className: 'muted', textContent: help }) : '', el('div', { className: 'row' }, ...kids, btn)))
      btn.onclick = async () => {
        try {
          const args = readInputs(f.inputs, id)
          if (kind === 'read') {
            const r = await publicClient.readContract({ address, abi: artifact.abi, functionName: f.name, args })
            log(`${f.name} → ${formatResult(r)}`)
          } else {
            if (!walletClient) return log('connect a wallet first')
            await ensureChain()
            const value = f.stateMutability === 'payable' && $(`${id}-value`).value ? parseEther($(`${id}-value`).value) : undefined
            const hash = await walletClient.writeContract({ address, abi: artifact.abi, functionName: f.name, args, account, value })
            log(`${f.name} tx ${hash}`)
            const rcpt = await publicClient.waitForTransactionReceipt({ hash })
            log(`${f.name} ${rcpt.status} in block ${rcpt.blockNumber}`)
          }
        } catch (e) { log(`${f.name} failed: ` + (e.shortMessage || e.message)) }
      }
    }
  }
}

fetch('./contracts/App.json')
  .then((r) => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
  .then((a) => {
    artifact = a
    renderDeploy()
    const fromUrl = new URLSearchParams(location.search).get('address')
    setAddress(fromUrl || project.deployments?.[chain.id] || localStorage.getItem(storageKey(project.slug, chain.id)))
  })
  .catch((e) => log('contract artifact missing: ' + e.message))

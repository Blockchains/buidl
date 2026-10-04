// Pure helpers for the ABI-driven UI (unit-tested in test/abi.test.js, no network).

/** Convert a raw form string into the JS value viem expects for a Solidity type. */
export function parseArg(type, raw) {
  const v = String(raw ?? '').trim()
  if (type.endsWith(']') || type.startsWith('tuple')) {
    const parsed = JSON.parse(v || '[]')
    const inner = type.replace(/\[[0-9]*\]$/, '')
    return Array.isArray(parsed) && type.endsWith(']') ? parsed.map((x) => parseArg(inner, typeof x === 'string' ? x : JSON.stringify(x))) : parsed
  }
  if (/^u?int\d*$/.test(type)) {
    if (!/^-?\d+$/.test(v)) throw new Error(`${type} expects an integer, got "${v}"`)
    return BigInt(v)
  }
  if (type === 'bool') {
    if (!['true', 'false', '1', '0'].includes(v.toLowerCase())) throw new Error(`bool expects true/false, got "${v}"`)
    return v.toLowerCase() === 'true' || v === '1'
  }
  if (type === 'address') {
    if (!/^0x[0-9a-fA-F]{40}$/.test(v)) throw new Error(`address expects 0x + 40 hex chars, got "${v}"`)
    return v
  }
  if (/^bytes\d*$/.test(type)) {
    if (!/^0x([0-9a-fA-F]{2})*$/.test(v)) throw new Error(`${type} expects 0x-prefixed hex`)
    return v
  }
  return v
}

/** JSON-stringify results that may contain bigint. */
export function formatResult(value) {
  return JSON.stringify(value, (_k, x) => (typeof x === 'bigint' ? x.toString() : x), 2)
}

/** Split an ABI into readable and writable functions, sorted by name. */
export function splitAbi(abi) {
  const fns = (abi || []).filter((x) => x.type === 'function')
  const byName = (a, b) => a.name.localeCompare(b.name)
  return {
    reads: fns.filter((f) => f.stateMutability === 'view' || f.stateMutability === 'pure').sort(byName),
    writes: fns.filter((f) => f.stateMutability === 'nonpayable' || f.stateMutability === 'payable').sort(byName),
    ctor: (abi || []).find((x) => x.type === 'constructor') || { inputs: [] },
  }
}

export function storageKey(slug, chainId) {
  return `buidl:${slug}:${chainId}:address`
}

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parseArg, formatResult, splitAbi } from '../src/abi.js'

test('parseArg converts solidity types', () => {
  assert.equal(parseArg('uint256', '42'), 42n)
  assert.equal(parseArg('int8', '-3'), -3n)
  assert.equal(parseArg('bool', 'true'), true)
  assert.equal(parseArg('address', '0x000000000000000000000000000000000000dEaD'), '0x000000000000000000000000000000000000dEaD')
  assert.deepEqual(parseArg('uint256[]', '["1","2"]'), [1n, 2n])
  assert.equal(parseArg('string', ' hi '), 'hi')
  assert.throws(() => parseArg('uint256', 'abc'))
  assert.throws(() => parseArg('address', '0x12'))
})

test('formatResult handles bigint', () => {
  assert.equal(formatResult({ a: 1n }), '{\n  "a": "1"\n}')
})

test('splitAbi separates reads and writes', () => {
  const abi = [
    { type: 'function', name: 'b', stateMutability: 'view', inputs: [], outputs: [] },
    { type: 'function', name: 'a', stateMutability: 'nonpayable', inputs: [], outputs: [] },
    { type: 'constructor', inputs: [] },
  ]
  const s = splitAbi(abi)
  assert.equal(s.reads[0].name, 'b')
  assert.equal(s.writes[0].name, 'a')
})

test('content.json and project.json are complete', () => {
  const content = JSON.parse(readFileSync(new URL('../src/content.json', import.meta.url)))
  const project = JSON.parse(readFileSync(new URL('../src/project.json', import.meta.url)))
  for (const k of ['hero_title', 'hero_sub', 'problem', 'solution', 'features', 'how_it_works']) assert.ok(content[k], `content.${k}`)
  for (const k of ['slug', 'title', 'contract', 'chain', 'repo_url']) assert.ok(project[k], `project.${k}`)
  assert.ok(Number.isInteger(project.chain.id), 'chain.id is an integer')
})

test('compiled contract artifact (after forge build) has abi + bytecode', { skip: !process.env.CHECK_ARTIFACT }, () => {
  const art = JSON.parse(readFileSync(new URL('../public/contracts/App.json', import.meta.url)))
  assert.ok(Array.isArray(art.abi) && art.abi.length > 0)
  assert.match(art.bytecode, /^0x[0-9a-f]{100,}$/i)
})

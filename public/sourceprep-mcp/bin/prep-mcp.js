#!/usr/bin/env node

const { spawn } = require('child_process')

function main() {
  const args = process.argv.slice(2)

  // Important: stdout is reserved for MCP JSON-RPC.
  // Only print errors to stderr.
  const child = spawn('prep', ['mcp', ...args], {
    stdio: 'inherit',
    env: process.env,
  })

  child.on('error', (err) => {
    if (err && err.code === 'ENOENT') {
      console.error('[prep-mcp] Error: `prep` not found on PATH.')
      console.error('[prep-mcp] Install Prep first (engine binary), then retry.')
      console.error('')
      console.error('macOS: brew install --cask prep')
      console.error('Windows: winget install MagneticAnomaly.Prep')
      process.exit(1)
    }

    console.error(`[prep-mcp] Failed to launch Prep: ${String(err)}`)
    process.exit(1)
  })

  child.on('exit', (code, signal) => {
    if (typeof code === 'number') process.exit(code)
    // When terminated by signal, propagate a non-zero exit.
    if (signal) process.exit(1)
    process.exit(1)
  })
}

main()

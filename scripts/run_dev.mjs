import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import process from 'node:process';

const isWindows = process.platform === 'win32';
const rootDir = process.cwd();
const frontendDir = fileURLToPath(new URL('../frontend/', import.meta.url));

const children = new Set();
let shuttingDown = false;

function spawnProcess(command, args, options) {
  const child = spawn(command, args, {
    stdio: 'inherit',
    ...options,
  });
  children.add(child);
  child.on('exit', (code, signal) => {
    children.delete(child);
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    for (const other of children) {
      other.kill('SIGTERM');
    }
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
  return child;
}

function shutdown(signal) {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  for (const child of children) {
    child.kill(signal);
  }
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

spawnProcess(
  isWindows ? 'cmd' : 'bash',
  isWindows ? ['/c', 'start.bat'] : ['./scripts/run_backend.sh'],
  { cwd: rootDir },
);

spawnProcess(
  isWindows ? 'npm.cmd' : 'npm',
  ['run', 'dev'],
  { cwd: frontendDir },
);

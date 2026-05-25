const net = require("node:net");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");

const root = path.resolve(__dirname, "..");
const processes = [];

function npmCommand() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function npmInvocation(args) {
  if (process.platform !== "win32") {
    return { command: npmCommand(), args };
  }
  return { command: "cmd.exe", args: ["/d", "/s", "/c", ["npm", ...args].join(" ")] };
}

function pythonCommand() {
  const venvPython = process.platform === "win32"
    ? path.join(root, "backend", "venv", "Scripts", "python.exe")
    : path.join(root, "backend", "venv", "bin", "python");
  return fs.existsSync(venvPython) ? venvPython : "python";
}

function isPortAvailable(port, host = "127.0.0.1") {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

async function findAvailablePort(preferred, host = "127.0.0.1") {
  for (let port = preferred; port < preferred + 100; port += 1) {
    if (await isPortAvailable(port, host)) return port;
  }
  throw new Error(`No available port found from ${preferred} to ${preferred + 99}`);
}

function spawnService(name, command, args, options) {
  const child = spawn(command, args, {
    cwd: options.cwd || root,
    env: { ...process.env, ...options.env },
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
  });

  processes.push(child);
  const prefix = `[${name}]`;

  child.stdout.on("data", (chunk) => {
    process.stdout.write(`${prefix} ${chunk.toString()}`);
  });

  child.stderr.on("data", (chunk) => {
    process.stderr.write(`${prefix} ${chunk.toString()}`);
  });

  child.on("exit", (code, signal) => {
    if (!shuttingDown) {
      console.log(`${prefix} exited (${signal || code})`);
      shutdown(code || 1);
    }
  });

  return child;
}

let shuttingDown = false;

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of processes) {
    if (!child.killed) {
      if (process.platform === "win32") {
        spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore" });
      } else {
        child.kill("SIGTERM");
      }
    }
  }
  setTimeout(() => process.exit(code), 300);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

async function main() {
  const apiHost = process.env.API_HOST || "127.0.0.1";
  const backendPort = await findAvailablePort(Number(process.env.API_PORT || 8000), apiHost);
  const frontendPort = await findAvailablePort(Number(process.env.VITE_DEV_PORT || 5173), apiHost);
  const runtimePort = await findAvailablePort(Number(process.env.RUNTIME_PORT || 3001), apiHost);

  const apiUrl = `http://${apiHost}:${backendPort}`;
  const frontendUrl = `http://localhost:${frontendPort}`;
  const runtimeUrl = `http://${apiHost}:${runtimePort}`;

  console.log("Starting AI Agent dev stack");
  console.log(`  Backend:  ${apiUrl}`);
  console.log(`  Frontend: ${frontendUrl}`);
  console.log(`  Runtime:  ${runtimeUrl}`);

  const runtimeNpm = npmInvocation(["run", "dev"]);
  spawnService("runtime", runtimeNpm.command, runtimeNpm.args, {
    cwd: path.join(root, "runtime"),
    env: {
      PORT: String(runtimePort),
      RUNTIME_PORT: String(runtimePort),
    },
  });

  spawnService("backend", pythonCommand(), [
    "-m",
    "uvicorn",
    "backend.main:app",
    "--host",
    apiHost,
    "--port",
    String(backendPort),
  ], {
    cwd: root,
    env: {
      API_HOST: apiHost,
      API_PORT: String(backendPort),
      CORS_ORIGINS: `${frontendUrl},http://127.0.0.1:${frontendPort}`,
      RUNTIME_BASE_URL: runtimeUrl,
    },
  });

  const frontendNpm = npmInvocation(["run", "dev", "--", "--host", apiHost]);
  spawnService("frontend", frontendNpm.command, frontendNpm.args, {
    cwd: path.join(root, "frontend"),
    env: {
      VITE_DEV_PORT: String(frontendPort),
      VITE_API_URL: apiUrl,
      VITE_WS_URL: apiUrl,
    },
  });
}

main().catch((error) => {
  console.error(`[dev:all] ${error.message}`);
  shutdown(1);
});

/**
 * Runner — executes the codewise CLI as a child process.
 *
 * Reads config for pythonPath, model, apiKey, extraArgs.
 * Falls back to `codewise` on PATH if no pythonPath is set.
 */

import { execFile } from "child_process";
import * as vscode from "vscode";
import { OutputManager } from "./output";

export class CodewiseRunner {
  constructor(private output: OutputManager) {}

  /**
   * Run a codewise CLI command and return stdout.
   *
   * @param args  CLI arguments (e.g., ["review", "--staged", "--format", "json"])
   * @param cwd   Working directory (repo root)
   */
  async run(args: string[], cwd?: string): Promise<string> {
    const config = vscode.workspace.getConfiguration("codewise");
    const pythonPath = config.get<string>("pythonPath") || "";
    const model = config.get<string>("model") || "";
    const apiKey = config.get<string>("apiKey") || "";
    const extraArgs = config.get<string>("extraArgs") || "";

    // Build command: either `python -m codewise` or bare `codewise`
    let command: string;
    let cmdArgs: string[];

    if (pythonPath) {
      command = pythonPath;
      cmdArgs = ["-m", "codewise", ...args];
    } else {
      command = "codewise";
      cmdArgs = [...args];
    }

    // Inject config-based args
    if (model && !args.includes("--model") && !args.includes("-m")) {
      cmdArgs.push("--model", model);
    }

    if (extraArgs) {
      cmdArgs.push(...extraArgs.split(/\s+/).filter(Boolean));
    }

    // Build environment
    const env: Record<string, string> = { ...process.env } as Record<string, string>;
    if (apiKey) {
      env["CODEWISE_API_KEY"] = apiKey;
    }

    this.output.log(`> ${command} ${cmdArgs.join(" ")}`);

    return new Promise((resolve, reject) => {
      const proc = execFile(
        command,
        cmdArgs,
        {
          cwd,
          env,
          maxBuffer: 10 * 1024 * 1024, // 10 MB
          timeout: 120_000, // 2 min
        },
        (error, stdout, stderr) => {
          if (stderr) {
            this.output.log(`stderr: ${stderr}`);
          }

          if (error) {
            // If there's stdout with JSON, the CLI may have returned findings
            // with a non-zero exit code (fail-on threshold exceeded)
            if (stdout && stdout.includes('"findings"')) {
              resolve(stdout);
              return;
            }
            reject(new Error(stderr || error.message));
            return;
          }

          resolve(stdout);
        }
      );

      // Ensure process is killed on VS Code shutdown
      proc.unref();
    });
  }
}

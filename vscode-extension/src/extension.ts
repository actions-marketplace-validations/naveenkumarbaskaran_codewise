/**
 * Codewise VS Code Extension
 *
 * Wraps the codewise CLI to provide:
 * - Code review with inline diagnostics
 * - Security scanning with SARIF integration
 * - Test generation
 * - Documentation generation
 *
 * Requires: pip install codewise-ai
 */

import * as vscode from "vscode";
import { CodewiseRunner } from "./runner";
import { DiagnosticsManager } from "./diagnostics";
import { StatusBarManager } from "./statusbar";
import { OutputManager } from "./output";

let runner: CodewiseRunner;
let diagnosticsManager: DiagnosticsManager;
let statusBar: StatusBarManager;
let outputManager: OutputManager;

export function activate(context: vscode.ExtensionContext) {
  outputManager = new OutputManager();
  diagnosticsManager = new DiagnosticsManager();
  statusBar = new StatusBarManager();
  runner = new CodewiseRunner(outputManager);

  // Register all commands
  const commands: [string, (...args: any[]) => any][] = [
    ["codewise.reviewFile", () => reviewCurrentFile()],
    ["codewise.reviewWorkspace", () => reviewWorkspace()],
    ["codewise.reviewStaged", () => reviewStaged()],
    ["codewise.securityScan", () => securityScan()],
    ["codewise.securityScanFile", () => securityScanCurrentFile()],
    ["codewise.generateTests", () => generateTests()],
    ["codewise.generateDocs", () => generateDocs()],
    ["codewise.clearDiagnostics", () => diagnosticsManager.clear()],
  ];

  for (const [id, handler] of commands) {
    context.subscriptions.push(vscode.commands.registerCommand(id, handler));
  }

  // Register on-save handler
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      const config = vscode.workspace.getConfiguration("codewise");
      if (config.get<boolean>("reviewOnSave")) {
        reviewFile(doc.uri);
      }
    })
  );

  context.subscriptions.push(diagnosticsManager, statusBar);
  outputManager.log("Codewise extension activated");
}

export function deactivate() {
  diagnosticsManager?.clear();
}

// ── Command Handlers ──────────────────────────────────────────────

async function reviewCurrentFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Codewise: No active file to review.");
    return;
  }
  await reviewFile(editor.document.uri);
}

async function reviewFile(uri: vscode.Uri) {
  const workspaceFolder = vscode.workspace.getWorkspaceFolder(uri);
  const cwd = workspaceFolder?.uri.fsPath;

  statusBar.showRunning("Reviewing…");
  try {
    const result = await runner.run(
      ["review", uri.fsPath, "--format", "json"],
      cwd
    );
    const findings = parseFindings(result);
    diagnosticsManager.setFindings(uri, findings);
    statusBar.showDone(findings.length);
    showSummary("Review", findings);
  } catch (err) {
    statusBar.showError();
    handleError("Review", err);
  }
}

async function reviewWorkspace() {
  const cwd = getWorkspacePath();
  if (!cwd) return;

  statusBar.showRunning("Reviewing changes…");
  try {
    const result = await runner.run(["review", "--format", "json"], cwd);
    const findings = parseFindings(result);
    applyFindingsToWorkspace(findings, cwd);
    statusBar.showDone(findings.length);
    showSummary("Review", findings);
  } catch (err) {
    statusBar.showError();
    handleError("Review", err);
  }
}

async function reviewStaged() {
  const cwd = getWorkspacePath();
  if (!cwd) return;

  statusBar.showRunning("Reviewing staged…");
  try {
    const result = await runner.run(
      ["review", "--staged", "--format", "json"],
      cwd
    );
    const findings = parseFindings(result);
    applyFindingsToWorkspace(findings, cwd);
    statusBar.showDone(findings.length);
    showSummary("Review", findings);
  } catch (err) {
    statusBar.showError();
    handleError("Review", err);
  }
}

async function securityScan() {
  const cwd = getWorkspacePath();
  if (!cwd) return;

  statusBar.showRunning("Security scan…");
  try {
    const result = await runner.run(["security", "--format", "json"], cwd);
    const findings = parseFindings(result);
    applyFindingsToWorkspace(findings, cwd);
    statusBar.showDone(findings.length);
    showSummary("Security", findings);
  } catch (err) {
    statusBar.showError();
    handleError("Security scan", err);
  }
}

async function securityScanCurrentFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Codewise: No active file to scan.");
    return;
  }
  const cwd = vscode.workspace.getWorkspaceFolder(editor.document.uri)?.uri
    .fsPath;

  statusBar.showRunning("Scanning…");
  try {
    const result = await runner.run(
      ["security", editor.document.uri.fsPath, "--format", "json"],
      cwd
    );
    const findings = parseFindings(result);
    diagnosticsManager.setFindings(editor.document.uri, findings);
    statusBar.showDone(findings.length);
    showSummary("Security", findings);
  } catch (err) {
    statusBar.showError();
    handleError("Security scan", err);
  }
}

async function generateTests() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Codewise: No active file.");
    return;
  }
  const config = vscode.workspace.getConfiguration("codewise");
  const framework = config.get<string>("testFramework") || "pytest";
  const cwd = vscode.workspace.getWorkspaceFolder(editor.document.uri)?.uri
    .fsPath;

  statusBar.showRunning("Generating tests…");
  try {
    const result = await runner.run(
      [
        "testgen",
        editor.document.uri.fsPath,
        "--framework",
        framework,
        "--format",
        "json",
      ],
      cwd
    );
    const parsed = safeParseJSON(result);
    if (parsed?.generated_code) {
      const doc = await vscode.workspace.openTextDocument({
        content: parsed.generated_code,
        language: inferLanguage(framework),
      });
      await vscode.window.showTextDocument(doc, { preview: false });
      vscode.window.showInformationMessage(
        `Codewise: Generated ${framework} tests`
      );
    } else {
      outputManager.show(result);
    }
    statusBar.showIdle();
  } catch (err) {
    statusBar.showError();
    handleError("Test generation", err);
  }
}

async function generateDocs() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Codewise: No active file.");
    return;
  }
  const cwd = vscode.workspace.getWorkspaceFolder(editor.document.uri)?.uri
    .fsPath;

  statusBar.showRunning("Generating docs…");
  try {
    const result = await runner.run(
      ["docgen", editor.document.uri.fsPath, "--format", "json"],
      cwd
    );
    const parsed = safeParseJSON(result);
    if (parsed?.documented_code) {
      // Show diff between original and documented code
      const original = editor.document.getText();
      if (parsed.documented_code !== original) {
        const edit = new vscode.WorkspaceEdit();
        const fullRange = new vscode.Range(
          editor.document.positionAt(0),
          editor.document.positionAt(original.length)
        );
        edit.replace(editor.document.uri, fullRange, parsed.documented_code);
        const applied = await vscode.workspace.applyEdit(edit);
        if (applied) {
          vscode.window.showInformationMessage(
            "Codewise: Docs added — undo with Ctrl/Cmd+Z"
          );
        }
      }
    } else {
      outputManager.show(result);
    }
    statusBar.showIdle();
  } catch (err) {
    statusBar.showError();
    handleError("Doc generation", err);
  }
}

// ── Helpers ───────────────────────────────────────────────────────

interface Finding {
  file?: string;
  path?: string;
  line?: number;
  end_line?: number;
  severity: string;
  category?: string;
  message: string;
  suggestion?: string;
  rule_id?: string;
  cwe_id?: string;
}

function parseFindings(output: string): Finding[] {
  const parsed = safeParseJSON(output);
  if (!parsed) return [];
  // codewise JSON output has a "findings" array
  return parsed.findings || parsed.results || [];
}

function safeParseJSON(text: string): any {
  try {
    // Handle case where CLI prints extra lines before JSON
    const jsonStart = text.indexOf("{");
    const jsonEnd = text.lastIndexOf("}");
    if (jsonStart >= 0 && jsonEnd >= 0) {
      return JSON.parse(text.substring(jsonStart, jsonEnd + 1));
    }
    // Try array
    const arrStart = text.indexOf("[");
    const arrEnd = text.lastIndexOf("]");
    if (arrStart >= 0 && arrEnd >= 0) {
      return JSON.parse(text.substring(arrStart, arrEnd + 1));
    }
  } catch {
    return null;
  }
  return null;
}

function getWorkspacePath(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    vscode.window.showWarningMessage("Codewise: No workspace open.");
    return undefined;
  }
  return folders[0].uri.fsPath;
}

function applyFindingsToWorkspace(findings: Finding[], cwd: string) {
  // Group findings by file
  const byFile = new Map<string, Finding[]>();
  for (const f of findings) {
    const filePath = f.file || f.path || "";
    if (!filePath) continue;
    const absPath = filePath.startsWith("/")
      ? filePath
      : `${cwd}/${filePath}`;
    if (!byFile.has(absPath)) byFile.set(absPath, []);
    byFile.get(absPath)!.push(f);
  }

  for (const [absPath, fileFindings] of byFile) {
    const uri = vscode.Uri.file(absPath);
    diagnosticsManager.setFindings(uri, fileFindings);
  }
}

function showSummary(action: string, findings: Finding[]) {
  if (findings.length === 0) {
    vscode.window.showInformationMessage(`Codewise ${action}: No issues found ✓`);
    return;
  }

  const critical = findings.filter(
    (f) => f.severity === "critical" || f.severity === "high"
  ).length;
  const rest = findings.length - critical;

  let msg = `Codewise ${action}: ${findings.length} finding(s)`;
  if (critical > 0) msg += ` — ${critical} critical/high`;
  if (rest > 0) msg += `, ${rest} other`;

  if (critical > 0) {
    vscode.window.showWarningMessage(msg, "Show Problems").then((sel) => {
      if (sel) vscode.commands.executeCommand("workbench.actions.view.problems");
    });
  } else {
    vscode.window.showInformationMessage(msg);
  }
}

function handleError(action: string, err: unknown) {
  const message = err instanceof Error ? err.message : String(err);

  if (message.includes("codewise: command not found") || message.includes("No such file")) {
    vscode.window
      .showErrorMessage(
        `Codewise: CLI not found. Install with: pip install codewise-ai`,
        "Copy Install Command"
      )
      .then((sel) => {
        if (sel) {
          vscode.env.clipboard.writeText("pip install codewise-ai");
        }
      });
  } else {
    vscode.window.showErrorMessage(`Codewise ${action} failed: ${message}`);
  }
  outputManager.log(`ERROR [${action}]: ${message}`);
}

function inferLanguage(framework: string): string {
  switch (framework) {
    case "pytest":
      return "python";
    case "jest":
    case "vitest":
      return "typescript";
    case "go":
      return "go";
    case "junit":
      return "java";
    default:
      return "plaintext";
  }
}

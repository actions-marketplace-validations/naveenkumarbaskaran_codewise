/**
 * Diagnostics Manager — maps codewise findings to VS Code diagnostics.
 *
 * Each finding becomes a squiggly underline in the editor with severity
 * determined by the codewise severity + user's failOn setting.
 */

import * as vscode from "vscode";

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

export class DiagnosticsManager implements vscode.Disposable {
  private collection: vscode.DiagnosticCollection;

  constructor() {
    this.collection = vscode.languages.createDiagnosticCollection("codewise");
  }

  /**
   * Set findings for a specific file URI.
   */
  setFindings(uri: vscode.Uri, findings: Finding[]) {
    const config = vscode.workspace.getConfiguration("codewise");
    const failOn = config.get<string>("failOn") || "none";

    const diagnostics = findings.map((f) => {
      const line = Math.max(0, (f.line || 1) - 1); // 0-indexed
      const endLine = f.end_line ? Math.max(0, f.end_line - 1) : line;

      const range = new vscode.Range(line, 0, endLine, Number.MAX_SAFE_INTEGER);

      const severity = this.mapSeverity(f.severity, failOn);

      let message = f.message;
      if (f.suggestion) {
        message += `\n💡 ${f.suggestion}`;
      }
      if (f.cwe_id) {
        message += `\n🔒 CWE-${f.cwe_id}`;
      }

      const diag = new vscode.Diagnostic(range, message, severity);
      diag.source = "codewise";
      diag.code = f.rule_id || f.category || f.severity;

      return diag;
    });

    this.collection.set(uri, diagnostics);
  }

  /**
   * Clear all diagnostics.
   */
  clear() {
    this.collection.clear();
    vscode.window.showInformationMessage("Codewise: Diagnostics cleared");
  }

  dispose() {
    this.collection.dispose();
  }

  /**
   * Map codewise severity to VS Code diagnostic severity.
   *
   * If the finding's severity meets or exceeds `failOn`, it becomes an Error;
   * otherwise it becomes a Warning. Info-level findings are always Hints.
   */
  private mapSeverity(
    severity: string,
    failOn: string
  ): vscode.DiagnosticSeverity {
    const levels: Record<string, number> = {
      critical: 5,
      high: 4,
      medium: 3,
      low: 2,
      info: 1,
    };

    const severityLevel = levels[severity] ?? 1;
    const failOnLevel = failOn === "none" ? 99 : (levels[failOn] ?? 99);

    if (severity === "info") {
      return vscode.DiagnosticSeverity.Hint;
    }

    if (severityLevel >= failOnLevel) {
      return vscode.DiagnosticSeverity.Error;
    }

    return vscode.DiagnosticSeverity.Warning;
  }
}

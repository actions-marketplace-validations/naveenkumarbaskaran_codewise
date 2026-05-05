/**
 * Status Bar Manager — shows codewise status in the VS Code status bar.
 *
 * States: idle (hidden), running (spinner), done (count), error.
 */

import * as vscode from "vscode";

export class StatusBarManager implements vscode.Disposable {
  private item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      100
    );
    this.item.command = "codewise.reviewFile";
    this.showIdle();
  }

  showIdle() {
    this.item.text = "$(search-fuzzy) Codewise";
    this.item.tooltip = "Click to review current file";
    this.item.backgroundColor = undefined;
    this.item.show();
  }

  showRunning(action: string) {
    this.item.text = `$(sync~spin) Codewise: ${action}`;
    this.item.tooltip = "Running…";
    this.item.backgroundColor = undefined;
    this.item.show();
  }

  showDone(count: number) {
    if (count === 0) {
      this.item.text = "$(check) Codewise: All clear";
      this.item.backgroundColor = undefined;
    } else {
      this.item.text = `$(warning) Codewise: ${count} finding(s)`;
      this.item.backgroundColor = new vscode.ThemeColor(
        "statusBarItem.warningBackground"
      );
    }
    this.item.tooltip = "Click to review current file";
    this.item.show();

    // Reset to idle after 10 seconds
    setTimeout(() => this.showIdle(), 10_000);
  }

  showError() {
    this.item.text = "$(error) Codewise: Error";
    this.item.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.errorBackground"
    );
    this.item.tooltip = "Check Output panel for details";
    this.item.show();

    setTimeout(() => this.showIdle(), 10_000);
  }

  dispose() {
    this.item.dispose();
  }
}

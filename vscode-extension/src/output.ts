/**
 * Output Manager — dedicated output channel for codewise logs.
 */

import * as vscode from "vscode";

export class OutputManager {
  private channel: vscode.OutputChannel;

  constructor() {
    this.channel = vscode.window.createOutputChannel("Codewise");
  }

  log(message: string) {
    const ts = new Date().toISOString().substring(11, 19);
    this.channel.appendLine(`[${ts}] ${message}`);
  }

  show(content: string) {
    this.channel.clear();
    this.channel.appendLine(content);
    this.channel.show(true);
  }
}

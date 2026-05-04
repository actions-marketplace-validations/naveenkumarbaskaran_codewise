"""Tests for diff parsing and file utilities."""

from codewise.core.diff import detect_language, parse_diff, should_include

SAMPLE_DIFF = """\
diff --git a/main.py b/main.py
index abc1234..def5678 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 import os
+import sys

 def hello():
"""


def test_detect_language():
    assert detect_language("main.py") == "python"
    assert detect_language("app.tsx") == "typescript"
    assert detect_language("server.go") == "go"
    assert detect_language("Dockerfile") == "dockerfile"
    assert detect_language("Makefile") == "makefile"
    assert detect_language("unknown.xyz") == "unknown"


def test_parse_diff():
    changes = parse_diff(SAMPLE_DIFF)
    assert len(changes) == 1
    assert changes[0].path == "main.py"
    assert changes[0].language == "python"
    assert "import sys" in changes[0].added_lines


def test_should_include():
    assert should_include("src/main.py", ["**/*"], ["**/*.lock"], None, None)
    assert not should_include("poetry.lock", ["**/*"], ["**/*.lock"], None, None)
    assert not should_include("node_modules/foo.js", ["**/*"], ["**/node_modules/**"], None, None)


def test_should_include_patterns():
    assert should_include("src/app.py", ["src/**"], [], None, None)
    assert not should_include("tests/test.py", ["src/**"], [], None, None)

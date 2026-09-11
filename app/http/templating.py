"""A very small, fast template engine (no third-party dependencies).

Supported syntax::

    {{ expr }}          auto HTML-escaped output
    {{& expr }}         raw (unescaped) output -- use only for trusted markup
    {% if x %} {% elif y %} {% else %} {% endif %}
    {% for a in b %} ... {% endfor %}      (``loop.index0``/``loop.index``)
    {% set name = expr %}
    {% include "partials/foo.html" %}
    {# comment #}

Templates compile once into Python functions and are cached by mtime, so
rendering is a plain function call after the first hit.
"""
from __future__ import annotations

import html
import os
import re
import threading
from types import FunctionType
from typing import Any, Callable, Dict

from .. import config

TOKEN_RE = re.compile(r"(\{\{&?.*?\}\}|\{%.*?%\}|\{#.*?#\})", re.S)

_cache: Dict[str, Any] = {}
_lock = threading.RLock()


def _escape(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Markup):
        return str(value)
    return html.escape(str(value), quote=True)


class Markup(str):
    """String subclass that is emitted verbatim by ``{{ }}``."""


class _Loop:
    __slots__ = ("index0", "index", "first", "last", "length")

    def __init__(self, index0: int, length: int):
        self.index0 = index0
        self.index = index0 + 1
        self.first = index0 == 0
        self.last = index0 == length - 1
        self.length = length


class TemplateError(Exception):
    pass


def _compile(source: str, name: str) -> Callable[[Dict[str, Any]], str]:
    body: list = []
    indent = [1]

    def emit(line: str) -> None:
        body.append("    " * indent[0] + line)

    body.append("def _render(ctx, _inc, _esc, _Loop):")
    emit("_out = []")
    emit("_w = _out.append")
    emit("_g = ctx")
    stack = []

    for tok in TOKEN_RE.split(source):
        if not tok:
            continue
        if tok.startswith("{#"):
            continue
        if tok.startswith("{{"):
            raw = tok.startswith("{{&")
            expr = tok[3:-2] if raw else tok[2:-2]
            expr = expr.strip()
            if not expr:
                continue
            if raw:
                emit("_w(str(%s))" % expr)
            else:
                emit("_w(_esc(%s))" % expr)
            continue
        if tok.startswith("{%"):
            stmt = tok[2:-2].strip()
            head = stmt.split(" ", 1)[0]
            rest = stmt[len(head):].strip()
            if head == "if":
                emit("if %s:" % rest)
                indent[0] += 1
                stack.append("if")
            elif head == "elif":
                indent[0] -= 1
                emit("elif %s:" % rest)
                indent[0] += 1
            elif head == "else":
                indent[0] -= 1
                emit("else:")
                indent[0] += 1
            elif head == "endif":
                indent[0] -= 1
                if not stack or stack.pop() != "if":
                    raise TemplateError("unbalanced endif in %s" % name)
            elif head == "for":
                m = re.match(r"^(.+?)\s+in\s+(.+)$", rest, re.S)
                if not m:
                    raise TemplateError("bad for-loop in %s: %s" % (name, rest))
                target, iterable = m.group(1).strip(), m.group(2).strip()
                seqvar = "_seq%d" % len(stack)
                emit("%s = list(%s)" % (seqvar, iterable))
                emit("for _i%d, (%s) in enumerate(%s):" % (len(stack), target,
                                                          seqvar))
                indent[0] += 1
                emit("loop = _Loop(_i%d, len(%s))" % (len(stack), seqvar))
                emit("ctx['loop'] = loop")
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", target.strip()):
                    # keep the loop variable visible to {% include %}
                    emit("ctx[%r] = %s" % (target, target))
                stack.append("for")
            elif head == "endfor":
                indent[0] -= 1
                if not stack or stack.pop() != "for":
                    raise TemplateError("unbalanced endfor in %s" % name)
            elif head == "set":
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", rest, re.S)
                if m:
                    emit("%s = %s" % (m.group(1), m.group(2)))
                    emit("ctx[%r] = %s" % (m.group(1), m.group(1)))
                else:
                    emit(rest)
            elif head == "include":
                path = rest.strip().strip('"\'')
                emit("_w(_inc(%r, ctx))" % path)
            else:
                raise TemplateError("unknown tag %r in %s" % (head, name))
            continue
        # literal text
        emit("_w(%r)" % tok)

    if stack:
        raise TemplateError("unclosed block(s) %s in %s" % (stack, name))
    emit("return ''.join(_out)")
    src = "\n".join(body)
    ns: Dict[str, Any] = {}
    try:
        exec(compile(src, "<template:%s>" % name, "exec"), ns)
    except SyntaxError as exc:  # pragma: no cover - developer error
        raise TemplateError("syntax error compiling %s: %s" % (name, exc))
    code = ns["_render"].__code__

    def render(ctx: Dict[str, Any]) -> str:
        # Re-binding the compiled code object to a fresh globals mapping lets
        # templates reference context keys as bare names with no per-render
        # compilation cost.
        scope = dict(GLOBALS)
        scope.update(ctx)
        scope["_inc"] = _include
        scope["_esc"] = _escape
        scope["_Loop"] = _Loop
        fn = FunctionType(code, scope, name)
        return fn(scope, _include, _escape, _Loop)

    return render


def _load(path: str) -> Callable[[Dict[str, Any]], str]:
    full = os.path.join(str(config.TEMPLATE_DIR), path)
    try:
        mtime = os.path.getmtime(full)
    except OSError:
        raise TemplateError("template not found: %s" % path)
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
    with open(full, "r", encoding="utf-8") as fh:
        source = fh.read()
    fn = _compile(source, path)
    with _lock:
        _cache[path] = (mtime, fn)
    return fn


def _include(path: str, ctx: Dict[str, Any]) -> str:
    return _load(path)(ctx)


GLOBALS: Dict[str, Any] = {
    "SITE_NAME": config.SITE_NAME,
    "SITE_TAGLINE": config.SITE_TAGLINE,
    "Markup": Markup,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "sorted": sorted,
    "enumerate": enumerate,
    "range": range,
    "list": list,
    "dict": dict,
    "bool": bool,
    "any": any,
    "all": all,
    "sum": sum,
    "reversed": reversed,
}


def register_global(name: str, value: Any) -> None:
    GLOBALS[name] = value


class AttrDict(dict):
    """Dict that also answers attribute access, so templates can write
    ``player.username`` instead of ``player['username']``."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


def wrap(value: Any, depth: int = 0) -> Any:
    """Recursively expose mappings as attribute-friendly dicts."""
    if depth > 12:
        return value
    if isinstance(value, AttrDict):
        return value
    if isinstance(value, dict):
        return AttrDict((k, wrap(v, depth + 1)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return [wrap(v, depth + 1) for v in value]
    return value


def render(path: str, /, **ctx: Any) -> str:
    return _load(path)(wrap(ctx))

"""Bounded, secret-scrubbed data for product surfaces; raw artifacts stay private."""
import re
from app.evaluation.execution_output import sanitize


def scrub(value, secret='', limit=16384):
    if isinstance(value, dict):
        return {key: scrub(item, secret, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item, secret, limit) for item in value]
    if not isinstance(value, str):
        return value
    text = sanitize(value.encode())
    if secret and len(secret) >= 8:
        text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'(?i)\b(?:sk-[a-z0-9_-]{12,}|AKIA[A-Z0-9]{16})\b', '[REDACTED]', text)
    text = re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|password|secret|token)\s*[=:]\s*)[^\s,;]+', r'\1[REDACTED]', text)
    raw = text.encode()
    if len(raw) > limit:
        text = raw[:limit].decode(errors='ignore') + '\n[truncated]'
    return text

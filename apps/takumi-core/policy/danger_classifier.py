import re

from schemas.approval_request import DangerLevel

# ─── Deny by Default ─────────────────────────────────────────────────────────
# These patterns are never allowed regardless of approval.
_DENY_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+-[rf]+",            "destructive file removal"),
    (r"\brmdir\b",              "directory removal"),
    (r"sudo\s+rm\b",            "privileged file removal"),
    (r"curl\s+.+\|\s*bash",     "remote code execution via curl|bash"),
    (r"wget\s+.+\|\s*bash",     "remote code execution via wget|bash"),
    (r"DROP\s+TABLE",           "destructive SQL operation"),
    (r"TRUNCATE\s+TABLE",       "destructive SQL operation"),
    (r"/etc/shadow",            "access to sensitive credential file"),
    (r"/etc/passwd",            "access to sensitive system file"),
    (r":\s*\(\)\s*\{.*\}.*;",   "fork bomb pattern"),
    (r">\s*/dev/sd[a-z]",       "direct disk write"),
]

# ─── Approval Required ────────────────────────────────────────────────────────
# These patterns require explicit approval before execution.
_APPROVAL_REQUIRED_PATTERNS: list[tuple[str, str]] = [
    (r"\bdelete\b",             "file or data deletion"),
    (r"\bremove\b",             "removal operation"),
    (r"\bdrop\b",               "drop operation"),
    (r"\bforce.?push\b",        "force push"),
    (r"\bpush\s+to\b",          "push to remote"),
    (r"\bdeploy\b",             "deployment operation"),
    (r"\bpublish\b",            "publish operation"),
    (r"\bsecret\b",             "secret handling"),
    (r"\btoken\b",              "token handling"),
    (r"\bpassword\b",           "password handling"),
    (r"\bcredential",           "credential handling"),
    (r"\bapi.?key\b",           "API key handling"),
    (r"\bproduction\b",         "production environment"),
    (r"\bprod\b",               "production environment"),
    (r"\bchmod\b",              "permission change"),
    (r"\bchown\b",              "ownership change"),
    (r"\bpermission\b",         "permission change"),
    (r"write\s+to\s+/",         "write to system path"),
    (r"\boverwrite\b",          "overwrite operation"),
    (r"\btruncate\b",           "truncate operation"),
]


def classify(task_description: str) -> tuple[DangerLevel, str]:
    """Classify a task description into a danger level.

    Returns:
        (DangerLevel, reason: str)
    """
    for pattern, label in _DENY_PATTERNS:
        if re.search(pattern, task_description, re.IGNORECASE):
            return DangerLevel.DENY, f"Denied: {label} (matched: {pattern!r})"

    for pattern, label in _APPROVAL_REQUIRED_PATTERNS:
        if re.search(pattern, task_description, re.IGNORECASE):
            return DangerLevel.APPROVAL_REQUIRED, f"Requires approval: {label} (matched: {pattern!r})"

    return DangerLevel.AUTO_ALLOW, "No dangerous patterns detected"

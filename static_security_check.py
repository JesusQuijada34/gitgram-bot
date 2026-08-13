import ast
from pathlib import Path

for name in ("main.py", "github_service.py", "database.py", "ai_agent.py"):
    ast.parse(Path(name).read_text(encoding="utf-8"), filename=name)

main = Path("main.py").read_text(encoding="utf-8")
service = Path("github_service.py").read_text(encoding="utf-8")
assert "MAX_PENDING_ZIP_BYTES" in main
assert "await update.message.delete()" in main
assert "re.fullmatch" in main
assert "import io" in service
assert "_safe_zip_path" in service
assert "MAX_MEMBER_BYTES" in service
assert "MAX_TOTAL_BYTES" in service
assert "shell=True" not in main + service
assert "extractall" not in main + service
print("GITGRAM_STATIC_SECURITY_CHECK_OK")

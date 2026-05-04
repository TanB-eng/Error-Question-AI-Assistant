from pathlib import Path


def main() -> int:
    root = Path("backend/app")
    allowed = root / "core" / "settings.py"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path == allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if "os.getenv" in text or "os.environ" in text:
            offenders.append(str(path))
    if offenders:
        print("Raw environment access is only allowed in backend/app/core/settings.py")
        for offender in offenders:
            print(offender)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

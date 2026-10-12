"""離線專案指令；所有來源與報告均使用 Excel。"""

import argparse
from pathlib import Path
import zipfile

from .analysis import export
from .core import ROOT, QualityError, connect, import_report, mode_path
from .generate import generate


def package():
    for path in ROOT.glob("data/*/archive"):
        if (path / ".import.lock").exists() or list(path.glob("*.pending")):
            raise QualityError("存在匯入鎖或中斷備份，不能打包，請先恢復")
    target = ROOT / "deliverables/作品交付.zip"
    target.parent.mkdir(exist_ok=True)
    excluded = {".git", ".github", "venv6", "__pycache__", ".pytest_cache", "deliverables"}
    directories = {"config", "data", "docs", "quality", "sql", "tests"}
    files = {"README.md", "requirements.txt", ".gitignore"}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if relative.parts[0] not in directories and str(relative) not in files:
                continue
            if relative.as_posix() == "docs/voicebook-guide.md":
                continue
            if any(part in excluded for part in relative.parts):
                continue
            if path.is_file() and not path.is_symlink() and not path.name.startswith("~$") and (not path.name.startswith(".") or path.name == ".gitignore") and not path.name.endswith((".tmp", ".pending", ".pyc", ".tmp.xlsx", "-journal", "-wal", "-shm")):
                bundle.write(path, relative)
    return target


def main():
    parser = argparse.ArgumentParser(description="電子組裝產線品質異常分析｜合成資料（Synthetic Data）")
    parser.add_argument("command", choices=["generate", "run", "import", "export", "package"], help="generate 生成；run 匯入全日報並分析；import 修正版；export 分析；package 打包")
    parser.add_argument("--mode", choices=["case", "demo"], default="case", help="隔離的資料模式")
    parser.add_argument("--file", help="專案相對 Excel 路徑")
    parser.add_argument("--yes", action="store_true", help="確認整日替換")
    args = parser.parse_args()
    try:
        if args.command == "package":
            print(f"交付包已建立：{package().relative_to(ROOT)}")
            return
        base = mode_path(args.mode)
        if args.command == "generate":
            print(f"已建立 {generate(args.mode, base)} 份合成日報")
            return
        db = connect(base / "quality.sqlite3")
        try:
            def confirm(summary):
                return args.yes or input("確認完整快照整日替換？輸入 是：").strip() == "是"
            if args.command == "import":
                if not args.file:
                    raise QualityError("import 必須指定 --file")
                source = Path(args.file)
                if source.is_absolute() or ".." in source.parts:
                    raise QualityError("--file 請使用專案根目錄相對路徑")
                print(import_report(db, ROOT / source, base / "archive", base / "output/檢查報告.xlsx", confirm))
            elif args.command == "run":
                sources = sorted((base / "raw").glob("*.xlsx"))
                if not sources:
                    raise QualityError("沒有日報，請先 generate")
                for source in sources:
                    print(import_report(db, source, base / "archive", base / "output/檢查報告.xlsx", confirm))
            if args.command in ("run", "export"):
                if (base / "archive/.import.lock").exists() or list((base / "archive").glob("*.pending")):
                    raise QualityError("封存有鎖或中斷殘留，禁止輸出，請先恢復")
                data = export(db, base / "output/品質分析.xlsx")
                p = data["fact_production"]
                print(f"全量輸出完成；投入／不良板／缺陷：{p.input_boards.sum()}／{p.bad_boards.sum()}／{p.defect_count.sum()}")
        finally:
            db.close()
    except (QualityError, OSError) as exc:
        parser.exit(1, f"錯誤：{exc}\n")


if __name__ == "__main__":
    main()

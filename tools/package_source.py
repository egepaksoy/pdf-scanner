"""Build a source-only archive without local documents or Python environments."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".gitignore", ".gitattributes", ".editorconfig", "main.py", "baslat.bat",
    "requirements.txt", "README.md", "PERFORMANS_README.md", "GITHUB_YUKLEME.md",
)


def source_files() -> list[Path]:
    paths = [ROOT / name for name in ROOT_FILES]
    paths.append(ROOT / ".github" / "workflows" / "tests.yml")
    for directory in ("app", "tests", "tools"):
        paths.extend((ROOT / directory).rglob("*.py"))
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Kaynak dosyası eksik veya bağlantı: {path}")
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Proje dışına çıkan kaynak: {path}")
    return sorted(set(paths))


def main() -> None:
    paths = source_files()
    output = ROOT / "dist" / "muhur-kontrol-source.zip"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, arcname=path.relative_to(ROOT).as_posix())
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Kaynak arşivi doğrulanamadı.")
    print(f"{len(paths)} kaynak dosyası paketlendi: {output}")


if __name__ == "__main__":
    main()

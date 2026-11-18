import ast
from pathlib import Path


def get_all_python_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts]


def extract_imported_modules(py_file: Path, base_package: str = "backend.app") -> list[str]:
    """Parse a python file using AST and return a list of imported module strings.

    Resolves relative imports based on the file's position relative to the repository.
    """
    with open(py_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(py_file))

    imported_modules: list[str] = []

    # Calculate package of current file, e.g. "backend.app.domain.common"
    parts = py_file.resolve().parts
    try:
        backend_idx = parts.index("backend")
        file_pkg_parts = parts[backend_idx:-1]
        current_pkg = ".".join(file_pkg_parts)
    except ValueError:
        current_pkg = base_package

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imported_modules.append(node.module)
            elif node.level > 0:
                # Relative import: resolve package
                pkg_parts = current_pkg.split(".")
                # node.level = 1 means same directory (slice len - 0)
                # node.level = 2 means parent directory (slice len - 1)
                pop_count = node.level - 1
                if pop_count == 0:
                    resolved_base = ".".join(pkg_parts)
                elif pop_count < len(pkg_parts):
                    resolved_base = ".".join(pkg_parts[:-pop_count])
                else:
                    resolved_base = ""

                if node.module:
                    imported_modules.append(f"{resolved_base}.{node.module}" if resolved_base else node.module)
                else:
                    imported_modules.append(resolved_base)

    return imported_modules


def test_domain_layer_boundaries():
    """Domain layer must be pure and framework-agnostic.

    It MUST NOT import Application, Infrastructure, API, FastAPI, Starlette, or SQLAlchemy.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    domain_dir = repo_root / "backend" / "app" / "domain"
    domain_files = get_all_python_files(domain_dir)

    forbidden_prefixes = (
        "backend.app.application",
        "backend.app.infrastructure",
        "backend.app.api",
        "fastapi",
        "starlette",
        "sqlalchemy",
    )

    violations = []
    for file_path in domain_files:
        imports = extract_imported_modules(file_path)
        for mod in imports:
            for forbidden in forbidden_prefixes:
                if mod == forbidden or mod.startswith(f"{forbidden}."):
                    violations.append(f"{file_path.name} imports forbidden module: {mod}")

    assert not violations, f"Domain boundary violations detected:\n" + "\n".join(violations)


def test_application_layer_boundaries():
    """Application layer coordinates use cases.

    It MAY import Domain.
    It MUST NOT import Infrastructure, API, FastAPI, Starlette, or SQLAlchemy.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    app_dir = repo_root / "backend" / "app" / "application"
    app_files = get_all_python_files(app_dir)

    forbidden_prefixes = (
        "backend.app.infrastructure",
        "backend.app.api",
        "fastapi",
        "starlette",
        "sqlalchemy",
    )

    violations = []
    for file_path in app_files:
        imports = extract_imported_modules(file_path)
        for mod in imports:
            for forbidden in forbidden_prefixes:
                if mod == forbidden or mod.startswith(f"{forbidden}."):
                    violations.append(f"{file_path.name} imports forbidden module: {mod}")

    assert not violations, f"Application boundary violations detected:\n" + "\n".join(violations)


def test_infrastructure_layer_boundaries():
    """Infrastructure layer implements ports.

    It MAY import Domain and Application.
    It MUST NOT import Presentation/API directly unless specifically acting as HTTP client.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    infra_dir = repo_root / "backend" / "app" / "infrastructure"
    infra_files = get_all_python_files(infra_dir)

    forbidden_prefixes = (
        "backend.app.api",
    )

    violations = []
    for file_path in infra_files:
        imports = extract_imported_modules(file_path)
        for mod in imports:
            for forbidden in forbidden_prefixes:
                if mod == forbidden or mod.startswith(f"{forbidden}."):
                    violations.append(f"{file_path.name} imports forbidden module: {mod}")

    assert not violations, f"Infrastructure boundary violations detected:\n" + "\n".join(violations)

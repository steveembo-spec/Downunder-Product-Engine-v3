import importlib
import json
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dpe_v3.config import PROJECT_ROOT


PLUGIN_PACKAGE = "dpe_v3.supplier_plugins"
CONFIG_FILE = PROJECT_ROOT / "config" / "suppliers.json"


@dataclass
class SupplierPluginStatus:
    key: str
    supplier_name: str
    module_name: str
    enabled: bool
    installed: bool
    configured: bool
    status: str
    input_file: str
    file_exists: bool
    file_size_kb: float


def load_configuration() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {"enabled_suppliers": []}

    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {"enabled_suppliers": []}


def get_enabled_supplier_keys() -> set[str]:
    config = load_configuration()
    enabled_suppliers = config.get("enabled_suppliers", [])

    if not isinstance(enabled_suppliers, list):
        return set()

    return {
        str(name).strip().lower()
        for name in enabled_suppliers
        if str(name).strip()
    }


def _iter_plugin_module_names() -> list[str]:
    package = importlib.import_module(PLUGIN_PACKAGE)

    module_names = []

    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        if module_name.startswith("_"):
            continue

        if module_name == "loader":
            continue

        module_names.append(module_name)

    return sorted(module_names)


def _load_plugin_module(module_name: str):
    return importlib.import_module(f"{PLUGIN_PACKAGE}.{module_name}")


def _find_supplier_input_file(module) -> Path | None:
    for attr_name in dir(module):
        if not attr_name.endswith("_FILE"):
            continue

        value = getattr(module, attr_name)

        if isinstance(value, Path):
            return value

    return None


def discover_plugins():
    enabled = get_enabled_supplier_keys()
    plugins = []

    for module_name in _iter_plugin_module_names():
        if enabled and module_name.lower() not in enabled:
            continue

        module = _load_plugin_module(module_name)
        plugins.append(module)

    plugins.sort(key=lambda p: getattr(p, "SUPPLIER_NAME", p.__name__))

    return plugins


def discover_plugin_statuses() -> list[SupplierPluginStatus]:
    enabled = get_enabled_supplier_keys()
    statuses: list[SupplierPluginStatus] = []

    for module_name in _iter_plugin_module_names():
        configured = module_name.lower() in enabled if enabled else False
        enabled_state = configured if enabled else True

        supplier_name = module_name.replace("_", " ").title()
        status = "Installed"
        input_file = ""
        file_exists = False
        file_size_kb = 0.0

        try:
            module = _load_plugin_module(module_name)

            supplier_name = str(
                getattr(
                    module,
                    "SUPPLIER_NAME",
                    supplier_name,
                )
            )

            supplier_file = _find_supplier_input_file(module)

            if supplier_file:
                input_file = str(supplier_file)
                file_exists = supplier_file.exists()

                if file_exists:
                    file_size_kb = supplier_file.stat().st_size / 1024

            if enabled:
                status = "Enabled" if enabled_state else "Installed, disabled"

            if enabled_state and supplier_file and not file_exists:
                status = "Enabled, missing file"

        except Exception as exc:
            status = f"Plugin error: {exc}"
            enabled_state = False

        statuses.append(
            SupplierPluginStatus(
                key=module_name.lower(),
                supplier_name=supplier_name,
                module_name=f"{PLUGIN_PACKAGE}.{module_name}",
                enabled=enabled_state,
                installed=True,
                configured=configured,
                status=status,
                input_file=input_file,
                file_exists=file_exists,
                file_size_kb=file_size_kb,
            )
        )

    statuses.sort(key=lambda item: item.supplier_name)

    return statuses


def discover_enabled_supplier_file_statuses() -> list[SupplierPluginStatus]:
    return [
        supplier
        for supplier in discover_plugin_statuses()
        if supplier.enabled
    ]


def load_all_suppliers():
    suppliers = discover_plugins()

    print(f"Supplier plugins enabled: {len(suppliers)}")

    products = []

    for supplier in suppliers:
        print(f"Loading {supplier.SUPPLIER_NAME}...")
        products.extend(supplier.load())

    return products
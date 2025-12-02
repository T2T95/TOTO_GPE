from pathlib import Path
import platform
from .services import (
    ensure_fw_storage,
    list_rules,
    add_rule_interactive,
    remove_rule_by_index,
    generate_windows_netsh,
    generate_linux_iptables,
    apply_windows_netsh,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _pause() -> None:
    input("Appuyez sur Entrée pour continuer...")


def _menu() -> None:
    print("=== Firewall ===")
    print("1. Lister les règles")
    print("2. Ajouter une règle")
    print("3. Supprimer une règle")
    print("4. Générer script Windows (netsh)")
    print("5. Générer script Linux (iptables)")
    print("6. Appliquer (Windows, admin)")
    print("7. Retour")


def run_firewall_module() -> None:
    root = _project_root()
    ensure_fw_storage(root)

    while True:
        print("\033[2J\033[H", end="")
        _menu()
        choice = input("Sélectionnez une option: ").strip()

        if choice == "1":
            rules = list_rules(root)
            if not rules:
                print("Aucune règle.")
            else:
                for i, r in enumerate(rules):
                    print(
                        f"[{i}] {r['action'].upper()} {r.get('direction','out')} proto={r.get('protocol','any')} "
                        f"remote={r.get('remote','any')} localport={r.get('localport','any')} "
                        f"remoteport={r.get('remoteport','any')} name={r.get('name','')}"
                    )
            _pause()
        elif choice == "2":
            ok, msg = add_rule_interactive(root)
            print(msg)
            _pause()
        elif choice == "3":
            idx = input("Index de la règle à supprimer: ").strip()
            try:
                i = int(idx)
            except Exception:
                print("Index invalide")
                _pause()
                continue
            ok, msg = remove_rule_by_index(root, i)
            print(msg)
            _pause()
        elif choice == "4":
            path = generate_windows_netsh(root)
            print(f"Script généré: {path}")
            _pause()
        elif choice == "5":
            path = generate_linux_iptables(root)
            print(f"Script généré: {path}")
            _pause()
        elif choice == "6":
            if not platform.system().lower().startswith("win"):
                print("Option Windows uniquement.")
                _pause()
                continue
            path, code = apply_windows_netsh(root)
            print(f"Application via netsh (code {code}) script: {path}")
            _pause()
        elif choice == "7":
            return
        else:
            print("Choix invalide.")
            _pause()


__all__ = ["run_firewall_module"]


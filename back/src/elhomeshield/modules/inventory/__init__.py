from pathlib import Path
import platform
import shutil
import subprocess
from .services import (
    ensure_inventory_storage,
    export_csv,
    enrich_with_names,
    smart_scan,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _pause() -> None:
    input("Appuyez sur Entree pour continuer...")


def _menu() -> None:
    print("=== Device Inventory ===")
    print("1. Scanner (auto: arp-scan/nmap/fallback)")
    print("2. Exporter en CSV")
    print("3. Aide (rafraichir ARP)")
    print("4. Retour")


def _help_refresh_arp() -> None:
    sysname = platform.system().lower()
    print("Conseils pour rafraichir l'ARP avant scan:")
    if sysname.startswith("win"):
        print("- Ouvrez une invite cmd/PowerShell en Admin si necessaire.")
        print("- Optionnel: pinguer votre sous-reseau: for /L %i in (1,1,254) do ping -n 1 192.168.1.%i (adaptez le prefixe)")
    else:
        print("- Optionnel: nmap -sn 192.168.1.0/24 (si nmap installe) ou 'for i in {1..254}; do ping -c1 -W1 192.168.1.$i; done'")


def _ensure_tools_for_scan() -> None:
    # Windows: installer Nmap/Npcap automatiquement si absent
    if not platform.system().lower().startswith("win"):
        return
    if shutil.which("nmap"):
        return
    script = _project_root() / "tools" / "inventory" / "install_nmap_windows.ps1"
    ps = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell"
    if not script.exists() or not ps:
        return
    print("Installation de Nmap/Npcap (Windows)...")
    try:
        subprocess.Popen([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]) or None
    except Exception:
        pass


def run_inventory_module() -> None:
    root = _project_root()
    ensure_inventory_storage(root)

    while True:
        print("\033[2J\033[H", end="")
        _menu()
        choice = input("Selectionnez une option: ").strip()

        if choice == "1":
            _ensure_tools_for_scan()
            rows = smart_scan(None)
            try:
                rows = enrich_with_names(rows, max_lookups=50)
            except Exception:
                pass
            if not rows:
                print("Aucun voisin detecte. Essayez d'actualiser l'ARP (option 3).")
            else:
                print(f"Appareils detectes: {len(rows)}")
                for r in rows[:20]:
                    name = r.get('name','')
                    name_seg = f" {name}" if name else ""
                    print(f"- {r['ip']:<15}{name_seg:<32} {r.get('mac','--'):<17}  {r.get('state',''):<10}  {r.get('iface','')}")
                if len(rows) > 20:
                    print(f"... et {len(rows)-20} de plus")
            _pause()
        elif choice == "2":
            path = export_csv(root)
            print(f"Exporte: {path}")
            _pause()
        elif choice == "3":
            _help_refresh_arp()
            _pause()
        elif choice == "4":
            return
        else:
            print("Choix invalide.")
            _pause()


__all__ = ["run_inventory_module"]



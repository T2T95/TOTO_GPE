import subprocess
import platform
import shutil
from pathlib import Path
from .services import (
    ensure_dns_storage,
    load_blocklist,
    load_allowlist,
    add_to_blocklist,
    remove_from_blocklist,
    is_domain_blocked,
    generate_dnsmasq_blocklist,
    import_from_url,
    hagezi_profiles,
)


def _project_root() -> Path:
    # back/src/elhomeshield/modules/dns/__init__.py -> parents[4] == back/
    return Path(__file__).resolve().parents[4]


def _pause() -> None:
    input("Appuyez sur Entrée pour continuer...")


def _print_status(root: Path) -> None:
    ensure_dns_storage(root)
    bl = load_blocklist(root)
    al = load_allowlist(root)
    print("=== DNS Status ===")
    print(f"Blocklist: {len(bl)} domaines")
    print(f"Allowlist: {len(al)} domaines")
    examples = sorted(list(bl))[:5]
    if examples:
        print("Exemples blocklist:", ", ".join(examples))


def _prompt_domain(prompt: str) -> str:
    return input(prompt).strip()


def _menu() -> None:
    print("=== DNS Anti-phishing ===")
    print("1. Statut (tailles block/allow)")
    print("2. Ajouter domaine à la blocklist")
    print("3. Retirer domaine de la blocklist")
    print("4. Tester un domaine (bloqué ?)")
    print("5. Générer config dnsmasq (dry-run)")
    print("6. Importer Hagezi (profils)")
    print("7. Importer depuis une URL")
    print("8. Installer dnsmasq natif (Linux)")
    print("9. Auto-setup Windows (Docker, 1-clic)")
    print("10. Démarrer dnsmasq (Docker)")
    print("11. Retour")


def _run_setup_linux(root_back: Path) -> None:
    if not platform.system().lower().startswith("linux"):
        print("Option disponible uniquement sur Linux.")
        return
    profs = hagezi_profiles()
    keys = list(profs.keys())
    print("Profils Hagezi:")
    for i, k in enumerate(keys, start=1):
        print(f"  {i}. {k}")
    sel = input("Choisissez un profil (numéro, défaut 1): ").strip() or "1"
    try:
        idx = int(sel) - 1
        profile = keys[idx]
    except Exception:
        print("Sélection invalide.")
        return
    script = root_back / "tools" / "dns" / "setup_all_linux.sh"
    if not script.exists():
        print(f"Script introuvable: {script}")
        return
    cmd = ["bash", str(script), f"--profile={profile}"]
    print("Exécution du setup natif Linux... Cela peut demander le mot de passe sudo.")
    try:
        code = subprocess.call(cmd)
        print(f"Setup terminé avec code {code}.")
    except FileNotFoundError:
        print("bash introuvable. Installez bash et réessayez.")


def _run_docker_dns(root_back: Path) -> None:
    script_ps1 = root_back / "tools" / "dns" / "run_docker.ps1"
    script_sh = root_back / "tools" / "dns" / "run_docker.sh"
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        if not shutil.which("powershell") and not shutil.which("powershell.exe"):
            print("PowerShell non trouvé.")
            return
        ps = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell"
        cmd = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_ps1), "-SetDns"]
    else:
        if not shutil.which("bash"):
            print("bash non trouvé.")
            return
        cmd = ["bash", str(script_sh)]
    try:
        code = subprocess.call(cmd)
        print(f"Commande terminée avec code {code}.")
    except Exception as e:
        print(f"Erreur d'exécution: {e}")


def _ensure_generated_blocklist(root_back: Path, profile: str = "light") -> None:
    ensure_dns_storage(root_back)
    bl = load_blocklist(root_back)
    if not bl:
        profs = hagezi_profiles()
        url = profs.get(profile)
        if url:
            print(f"Import Hagezi '{profile}' en cours...")
            ok, msg, _ = import_from_url(root_back, url)
            print(msg)
    out = generate_dnsmasq_blocklist(root_back)
    print(f"Config dnsmasq générée: {out}")


def _auto_setup_windows(root_back: Path) -> None:
    if not platform.system().lower().startswith("win"):
        print("Option disponible uniquement sur Windows.")
        return
    script_ps1 = root_back / "tools" / "dns" / "run_docker.ps1"
    if not script_ps1.exists():
        print(f"Script introuvable: {script_ps1}")
        return
    _ensure_generated_blocklist(root_back, profile="light")
    ps = shutil.which("powershell.exe") or shutil.which("powershell")
    if not ps:
        print("PowerShell introuvable.")
        return
    cmd = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_ps1), "-Recreate", "-SetDns"]
    try:
        code = subprocess.call(cmd)
        print(f"Auto-setup Windows terminé avec code {code}.")
    except Exception as e:
        print(f"Erreur d'exécution: {e}")


def run_dns_module() -> None:
    root = _project_root()
    ensure_dns_storage(root)

    while True:
        print("\033[2J\033[H", end="")
        _menu()
        choice = input("Sélectionnez une option: ").strip()

        if choice == "1":
            _print_status(root)
            _pause()
        elif choice == "2":
            domain = _prompt_domain("Domaine à ajouter (ex: phishing.com): ")
            ok, msg = add_to_blocklist(root, domain)
            print(msg)
            _pause()
        elif choice == "3":
            domain = _prompt_domain("Domaine à retirer: ")
            ok, msg = remove_from_blocklist(root, domain)
            print(msg)
            _pause()
        elif choice == "4":
            domain = _prompt_domain("Domaine à tester: ")
            blocked = is_domain_blocked(root, domain)
            print(f"Résultat: {'BLOQUÉ' if blocked else 'autorisé'}")
            _pause()
        elif choice == "5":
            out_path = generate_dnsmasq_blocklist(root)
            print(f"Fichier généré: {out_path}")
            _pause()
        elif choice == "6":
            profs = hagezi_profiles()
            print("Profils Hagezi disponibles:")
            for i, (k, url) in enumerate(profs.items(), start=1):
                print(f"  {i}. {k} -> {url}")
            sel = input("Choisissez un profil (numéro): ").strip()
            try:
                idx = int(sel) - 1
                key = list(profs.keys())[idx]
            except Exception:
                print("Sélection invalide.")
                _pause()
                continue
            ok, msg, _ = import_from_url(root, profs[key])
            print(msg)
            _pause()
        elif choice == "7":
            url = _prompt_domain("URL de la blocklist (Hagezi ou autre): ")
            ok, msg, _ = import_from_url(root, url)
            print(msg)
            _pause()
        elif choice == "8":
            _run_setup_linux(root)
            _pause()
        elif choice == "9":
            _auto_setup_windows(root)
            _pause()
        elif choice == "10":
            _run_docker_dns(root)
            _pause()
        elif choice == "11":
            return
        else:
            print("Choix invalide.")
            _pause()


__all__ = ["run_dns_module"]

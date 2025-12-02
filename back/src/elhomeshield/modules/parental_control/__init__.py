from pathlib import Path
from .services import (
    ensure_parental_storage,
    list_categories,
    add_domain_to_category,
    remove_domain_from_category,
    set_active_categories,
    get_active_categories,
    get_schedule,
    set_schedule_enabled,
    set_schedule_range,
    apply_parental_to_dns,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _pause() -> None:
    input("Appuyez sur Entree pour continuer...")


def _menu() -> None:
    print("=== Parental Control ===")
    print("1. Statut")
    print("2. Gerer categories (ajouter/retirer domaine)")
    print("3. Selectionner categories actives")
    print("4. Programmer horaires (activer/desactiver)")
    print("5. Appliquer maintenant (generer DNS)")
    print("6. Retour")


def _print_status(root: Path) -> None:
    cats = list_categories(root)
    active = get_active_categories(root)
    sched = get_schedule(root)
    print("Categories disponibles:")
    for k, domains in cats.items():
        marker = "*" if k in active else " "
        print(f" {marker} {k}: {len(domains)} domaines")
    print(f"Horaires actives: {'oui' if sched.get('enabled') else 'non'}")


def _manage_categories(root: Path) -> None:
    while True:
        cats = list_categories(root)
        names = list(cats.keys())
        print("Categories:")
        for i, k in enumerate(names, start=1):
            print(f"  {i}. {k} ({len(cats[k])} domaines)")
        print("  X. Retour")
        sel = input("Choisissez une categorie: ").strip().lower()
        if sel in {"x", "q", "retour"}:
            return
        try:
            idx = int(sel) - 1
            cat = names[idx]
        except Exception:
            print("Selection invalide.")
            _pause()
            continue
        action = input("(A)jouter, (R)etirer, (L)ister, (B)ack: ").strip().lower()
        if action == "a":
            d = input("Domaine a ajouter (ex: example.com): ").strip()
            ok, msg = add_domain_to_category(root, cat, d)
            print(msg)
            _pause()
        elif action == "r":
            d = input("Domaine a retirer: ").strip()
            ok, msg = remove_domain_from_category(root, cat, d)
            print(msg)
            _pause()
        elif action == "l":
            for d in sorted(cats.get(cat, []))[:50]:
                print("-", d)
            _pause()
        else:
            continue


def _select_active_categories(root: Path) -> None:
    cats = list_categories(root)
    names = list(cats.keys())
    print("Selectionnez les categories actives (sep par virgules):")
    print(", ".join(names))
    line = input("Actives: ").strip()
    chosen = [x.strip() for x in line.split(",") if x.strip()]
    ok, msg = set_active_categories(root, chosen)
    print(msg)
    _pause()


def _configure_schedule(root: Path) -> None:
    sched = get_schedule(root)
    print(f"Horaires actives: {'oui' if sched.get('enabled') else 'non'}")
    toggle = input("Activer les horaires ? (o/n): ").strip().lower()
    set_schedule_enabled(root, toggle == "o")
    if toggle == "o":
        print("Plage quotidienne HH:MM-HH:MM, ex: 22:00-06:00")
        rng = input("Plage: ").strip()
        ok, msg = set_schedule_range(root, rng)
        print(msg)
    _pause()


def run_parental_control_module() -> None:
    root = _project_root()
    ensure_parental_storage(root)

    while True:
        print("\033[2J\033[H", end="")
        _menu()
        choice = input("Selectionnez une option: ").strip()

        if choice == "1":
            _print_status(root)
            _pause()
        elif choice == "2":
            _manage_categories(root)
        elif choice == "3":
            _select_active_categories(root)
        elif choice == "4":
            _configure_schedule(root)
        elif choice == "5":
            out = apply_parental_to_dns(root)
            print(f"DNS mis a jour: {out}")
            _pause()
        elif choice == "6":
            return
        else:
            print("Choix invalide.")
            _pause()


__all__ = ["run_parental_control_module"]


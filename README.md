## 📄 README (Base minimale)

# 🛡️ Elhomeshield — Base du projet

Ce dépôt contient la base réutilisable du projet: un CLI Python minimal, une structure modulaire prête à étendre, et une vérification de licence locale par adresse MAC. Cette branche est la branche principale (main).

---

## 📦 Structure du projet (squelette)

```
back/elhomeshield.py            # Entrée CLI (backend)
back/src/
  elhomeshield/
    cli.py                      # Menu CLI (placeholder)
    license.py                  # Vérification licence locale (MAC)
    modules/
      dns/__init__.py           # Module DNS Anti-phishing (placeholder)
      segmentation/__init__.py  # Module Segmentation IoT (placeholder)
      firewall/__init__.py      # Module Firewall (placeholder)
      parental_control/__init__.py # Module Parental Control (placeholder)
      inventory/__init__.py     # Module Device Inventory (placeholder)
      vpn/__init__.py           # Module VPN WireGuard (placeholder)
back/licenses/
  fake_macs.txt                 # Liste de MAC autorisées (une par ligne)
  seed_mac.txt                  # Fichier bootstrap auto (optionnel)
back/requirements.txt
```

---

## ▶️ Lancer la base

1) Optionnel: ajouter votre MAC (format AA:BB:CC:DD:EE:FF)
   - Éditer `back/licenses/fake_macs.txt` et ajouter une ligne avec votre MAC, ou
   - Créer `back/licenses/seed_mac.txt` avec votre MAC (le script la migre automatiquement).

2) Lancer le CLI
```bash
# Option 1 (recommandé): script runner
python run.py --mac   # ajoute la MAC locale puis lance le backend

# Option 2: lancer directement le backend
cd back
python3 elhomeshield.py
```

Menu affiché (placeholders vides): DNS Anti-phishing, Segmentation IoT, Firewall, Parental Control, Device Inventory, VPN WireGuard.

---

## 🏃 Script runner (run.py)

- `--mac` : détecte la MAC locale, l’ajoute dans `back/licenses/fake_macs.txt`, puis lance le backend.
- Sans option : lance directement le backend.

Exemples:
```bash
python run.py --mac
python run.py
```

Sous Windows, vous pouvez aussi utiliser:
```powershell
py run.py --mac
```

---

## 🔐 Licence locale (MAC)

- Le programme lit `back/licenses/fake_macs.txt` et vérifie si la MAC locale y est présente.
- Vous pouvez bootstrap avec `back/licenses/seed_mac.txt` (sera migré vers `fake_macs.txt`).

---

## 🔀 Workflow Git (branche principale)

- Développement sur des branches de fonctionnalité dérivées de `main`:
  - `git checkout -b feature/<nom-fonctionnalite>`
  - Commits atomiques et messages clairs
  - Pull request vers `main`
- `main` reste stable: uniquement squelette et code validé.

---

## 📝 Remarques

- Cette base ne contient que des placeholders; aucun module n’est implémenté.
- Ajoutez vos fichiers au sein de chaque dossier de module quand vous développez (ex: `config/`, `services/`).
import sys
import re
import uuid
import subprocess
import shutil
import platform
from pathlib import Path


def normalize_mac(mac_address: str) -> str:
	if not mac_address:
		return ""
	# Conserver uniquement les hex, regrouper par 2, joindre avec ':' en majuscules
	hex_only = re.sub(r"[^0-9A-Fa-f]", "", mac_address)
	if len(hex_only) < 12:
		return ""
	pairs = [hex_only[i : i + 2] for i in range(0, 12, 2)]
	return ":".join(p.upper() for p in pairs[:6])


def _find_system_macs() -> set[str]:
	"""Essaye d'extraire des MACs via les outils système (Windows/Linux/macOS)."""
	macs: set[str] = set()
	mac_re = re.compile(r"([0-9A-Fa-f]{2}([:-])){5}[0-9A-Fa-f]{2}")

	def run_and_collect(cmd: list[str]) -> None:
		try:
			out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="ignore")
		except Exception:
			return
		for m in mac_re.findall(out):
			addr = m[0]
			nm = normalize_mac(addr)
			if nm:
				macs.add(nm)

	system = platform.system().lower()
	if system.startswith("win"):
		if shutil.which("getmac"):
			run_and_collect(["getmac", "/v", "/fo", "csv"])
			run_and_collect(["getmac"])
		if shutil.which("ipconfig"):
			run_and_collect(["ipconfig", "/all"])
	else:
		if shutil.which("ip"):
			run_and_collect(["ip", "link"])
		if shutil.which("ifconfig"):
			run_and_collect(["ifconfig"]) if system == "darwin" else run_and_collect(["ifconfig", "-a"])

	return macs


def get_local_mac_candidates() -> set[str]:
	"""Retourne un ensemble de MAC candidates détectées localement.

	Utilise uuid.getnode() pour obtenir la MAC principale.
	"""
	candidates: set[str] = set()
	try:
		mac_int = uuid.getnode()
		if mac_int and mac_int != uuid.getnode.__code__.co_argcount:  # simple garde
			hex_str = f"{mac_int:012x}"
			candidates.add(normalize_mac(hex_str))
	except Exception:
		pass
	return {m for m in candidates if m}


def get_local_mac_candidates() -> set[str]:
	"""Retourne un ensemble de MAC candidates détectées localement.

	Combine uuid.getnode() et une détection basée sur les interfaces.
	"""
	candidates: set[str] = set()
	try:
		mac_int = uuid.getnode()
		if mac_int:
			hex_str = f"{mac_int:012x}"
			nm = normalize_mac(hex_str)
			if nm:
				candidates.add(nm)
	except Exception:
		pass

	candidates |= _find_system_macs()
	return {m for m in candidates if m}

def read_fake_macs(licenses_dir: Path) -> set[str]:
	file_path = licenses_dir / "fake_macs.txt"
	if not file_path.exists():
		return set()
	entries: set[str] = set()
	for line in file_path.read_text(encoding="utf-8").splitlines():
		norm = normalize_mac(line.strip())
		if norm:
			entries.add(norm)
	return entries


def write_fake_macs(licenses_dir: Path, macs: set[str]) -> None:
	licenses_dir.mkdir(parents=True, exist_ok=True)
	file_path = licenses_dir / "fake_macs.txt"
	ordered = sorted(macs)
	file_path.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")


def validate_or_exit(project_root: Path) -> None:
	licenses_dir = project_root / "licenses"
	allowed = read_fake_macs(licenses_dir)

	# Essayer de détecter une MAC ajoutée lors de l'installation (fichier seed)
	seed_path = licenses_dir / "seed_mac.txt"
	if seed_path.exists():
		seed_content = seed_path.read_text(encoding="utf-8").strip()
		seed_norm = normalize_mac(seed_content)
		if seed_norm and seed_norm not in allowed:
			allowed.add(seed_norm)
			write_fake_macs(licenses_dir, allowed)
			seed_path.unlink(missing_ok=True)

	# Valider: si aucune entrée, refuser
	if not allowed:
		print("Aucune licence trouvée.\nVeuillez acheter une licence ou ajouter votre MAC dans licenses/fake_macs.txt")
		sys.exit(2)

	local_macs = get_local_mac_candidates()
	if not local_macs:
		print("Impossible de détecter la MAC locale.\nAjoutez manuellement votre MAC dans licenses/fake_macs.txt")
		sys.exit(3)

		if not (allowed & local_macs):
			print("Licence invalide pour cet appareil.")
			try:
				print("- MAC(s) détectée(s): " + ", ".join(sorted(local_macs)))
			except Exception:
				pass
			print("- Conseil: Copiez l'une des MACs ci-dessus dans licenses/fake_macs.txt")
			sys.exit(4)

	return


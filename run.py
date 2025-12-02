import argparse
import subprocess
import sys
from pathlib import Path
import uuid


def normalize_mac(mac_address: str) -> str:
	hex_only = "".join(ch for ch in mac_address if ch.isalnum())
	if len(hex_only) < 12:
		return ""
	pairs = [hex_only[i : i + 2] for i in range(0, 12, 2)]
	return ":".join(p.upper() for p in pairs[:6])


def get_local_mac() -> str:
	try:
		mac_int = uuid.getnode()
		if not mac_int:
			return ""
		hex_str = f"{mac_int:012x}"
		return normalize_mac(hex_str)
	except Exception:
		return ""


def ensure_mac_in_list(project_root: Path, mac: str) -> None:
	licenses_dir = project_root / "back" / "licenses"
	licenses_dir.mkdir(parents=True, exist_ok=True)
	fake_file = licenses_dir / "fake_macs.txt"
	entries: set[str] = set()
	if fake_file.exists():
		for line in fake_file.read_text(encoding="utf-8").splitlines():
			norm = normalize_mac(line.strip())
			if norm:
				entries.add(norm)
	if mac:
		entries.add(mac)
	fake_file.write_text("\n".join(sorted(entries)) + ("\n" if entries else ""), encoding="utf-8")


def main(argv: list[str]) -> int:
	parser = argparse.ArgumentParser(description="Runner Elhomeshield (backend)")
	parser.add_argument("--mac", action="store_true", help="Ajouter automatiquement la MAC locale à back/licenses/fake_macs.txt avant de lancer")
	args = parser.parse_args(argv)

	project_root = Path(__file__).resolve().parent
	if args.mac:
		local_mac = get_local_mac()
		if not local_mac:
			print("Impossible de détecter la MAC locale.")
		else:
			ensure_mac_in_list(project_root, local_mac)
			print(f"MAC ajoutée/confirmée: {local_mac}")

	# Lancer le backend
	backend_entry = project_root / "back" / "elhomeshield.py"
	if not backend_entry.exists():
		print("Entrée backend introuvable: back/elhomeshield.py")
		return 2
	cmd = [sys.executable, str(backend_entry)]
	return subprocess.call(cmd)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))


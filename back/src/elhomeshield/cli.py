from pathlib import Path
from .license import validate_or_exit
from .modules.dns import run_dns_module
from .modules.segmentation import run_segmentation_module
from .modules.firewall import run_firewall_module
from .modules.parental_control import run_parental_control_module
from .modules.inventory import run_inventory_module
from .modules.vpn import run_vpn_module


def clear_screen() -> None:
	print("\033[2J\033[H", end="")


def menu() -> None:
	print("=== Elhomeshield CLI ===")
	print("1. DNS Filter Anti-phishing (placeholder)")
	print("2. Segmentation IoT (placeholder)")
	print("3. Firewall (placeholder)")
	print("4. Parental Control (placeholder)")
	print("5. Device Inventory (placeholder)")
	print("6. VPN WireGuard (placeholder)")
	print("7. Quitter")


def run_cli() -> int:
	# S'assure que la licence est valide avant d'accéder au menu
	project_root = Path(__file__).resolve().parents[2]
	validate_or_exit(project_root)

	while True:
		clear_screen()
		menu()
		choice = input("Sélectionnez une option: ").strip()
		if choice == "1":
			run_dns_module()
			input("Appuyez sur Entrée pour revenir au menu...")
		elif choice == "2":
			run_segmentation_module()
			input("Appuyez sur Entrée pour revenir au menu...")
		elif choice == "3":
			run_firewall_module()
			input("Appuyez sur Entrée pour revenir au menu...")
		elif choice == "4":
			run_parental_control_module()
			input("Appuyez sur Entrée pour revenir au menu...")
		elif choice == "5":
			run_inventory_module()
			input("Appuyez sur Entrée pour revenir au menu...")
		elif choice == "6":
			run_vpn_module()
			input("Appuyez sur Entrée pour revenir au menu...")
		elif choice == "7":
			print("Au revoir.")
			return 0
		else:
			print("Choix invalide.")
			input("Appuyez sur Entrée pour continuer...")

	return 0


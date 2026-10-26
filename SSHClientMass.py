import getpass
import time
from datetime import datetime
from pathlib import Path

import paramiko
import pandas as pd

from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    NoValidConnectionsError,
    SSHException,
)


INVENTORY_FILE = Path("hosts.txt")
REPORT_DIR = Path("reports")
COMMAND_TIMEOUT = 60
CONNECT_TIMEOUT = 10


def load_hosts(filename):
    """Charge les hôtes depuis un fichier texte."""
    with open(filename, "r", encoding="utf-8") as file:
        return [
            line.strip()
            for line in file
            if line.strip() and not line.lstrip().startswith("#")
        ]


def ssh_execution(username, password, host, command):
    """Exécute une commande SSH et retourne un résultat structuré."""

    result = {
        "Hote": host,
        "Statut": "ERREUR",
        "Code retour": None,
        "Duree (s)": 0,
        "Sortie standard": "",
        "Erreur standard": "",
    }

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    start_time = time.monotonic()

    try:
        print(f"[CONNEXION] {host}")

        ssh.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=CONNECT_TIMEOUT,
            banner_timeout=CONNECT_TIMEOUT,
            auth_timeout=CONNECT_TIMEOUT,
            look_for_keys=False,
            allow_agent=False,
        )

        stdin, stdout, stderr = ssh.exec_command(
            command,
            timeout=COMMAND_TIMEOUT,
            get_pty=True,
        )

        # Ferme l'entrée standard pour les commandes non interactives.
        stdin.close()

        # Récupération des deux flux et du code de retour.
        result["Sortie standard"] = stdout.read().decode(
            "utf-8", errors="replace"
        ).strip()

        result["Erreur standard"] = stderr.read().decode(
            "utf-8", errors="replace"
        ).strip()

        result["Code retour"] = stdout.channel.recv_exit_status()

        result["Statut"] = (
            "OK" if result["Code retour"] == 0 else "ECHEC"
        )

    except AuthenticationException:
        result["Erreur standard"] = "Échec de l'authentification SSH"

    except BadHostKeyException:
        result["Erreur standard"] = "La clé SSH du serveur a changé"

    except NoValidConnectionsError as exc:
        result["Erreur standard"] = f"Connexion impossible : {exc}"

    except (TimeoutError, OSError) as exc:
        result["Erreur standard"] = f"Erreur réseau ou timeout : {exc}"

    except SSHException as exc:
        result["Erreur standard"] = f"Erreur SSH : {exc}"

    except Exception as exc:
        result["Erreur standard"] = (
            f"Erreur inattendue : {type(exc).__name__}: {exc}"
        )

    finally:
        ssh.close()
        result["Duree (s)"] = round(time.monotonic() - start_time, 2)

    print(
        f"[{result['Statut']}] {host} "
        f"(code={result['Code retour']}, "
        f"{result['Duree (s)']} s)"
    )

    return result


def generate_reports(results, command):
    """Génère les rapports TXT et Excel."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    txt_file = REPORT_DIR / f"rapport_ssh_{timestamp}.txt"
    xlsx_file = REPORT_DIR / f"rapport_ssh_{timestamp}.xlsx"

    df = pd.DataFrame(results)

    # Rapport texte détaillé
    with open(txt_file, "w", encoding="utf-8") as file:
        file.write("RAPPORT D'EXECUTION SSH\n")
        file.write("=" * 70 + "\n")
        file.write(f"Date : {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        file.write(f"Commande : {command}\n")
        file.write(f"Nombre de machines : {len(results)}\n")
        file.write(f"Succès : {(df['Statut'] == 'OK').sum()}\n")
        file.write(f"Échecs : {(df['Statut'] != 'OK').sum()}\n")
        file.write("=" * 70 + "\n\n")

        for result in results:
            file.write(f"HOTE : {result['Hote']}\n")
            file.write(f"STATUT : {result['Statut']}\n")
            file.write(f"CODE RETOUR : {result['Code retour']}\n")
            file.write(f"DUREE : {result['Duree (s)']} s\n")

            file.write("\n--- SORTIE STANDARD ---\n")
            file.write(result["Sortie standard"] or "(vide)")
            file.write("\n\n--- ERREUR STANDARD ---\n")
            file.write(result["Erreur standard"] or "(vide)")
            file.write("\n\n" + "-" * 70 + "\n\n")

    # Rapport Excel : synthèse + détails
    summary = pd.DataFrame(
        [
            {"Indicateur": "Date", "Valeur": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )},
            {"Indicateur": "Commande", "Valeur": command},
            {"Indicateur": "Machines", "Valeur": len(results)},
            {"Indicateur": "Succès", "Valeur": int(
                (df["Statut"] == "OK").sum()
            )},
            {"Indicateur": "Échecs", "Valeur": int(
                (df["Statut"] != "OK").sum()
            )},
        ]
    )

    with pd.ExcelWriter(xlsx_file, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Synthese", index=False)
        df.to_excel(writer, sheet_name="Details", index=False)

        # Ajustement simple de la largeur des colonnes
        for sheet_name in ("Synthese", "Details"):
            worksheet = writer.sheets[sheet_name]

            for column_cells in worksheet.columns:
                max_length = max(
                    len(str(cell.value or ""))
                    for cell in column_cells
                )
                worksheet.column_dimensions[
                    column_cells[0].column_letter
                ].width = min(max_length + 2, 60)

    print("\nRapports générés :")
    print(f" - TXT  : {txt_file}")
    print(f" - Excel: {xlsx_file}")


def launcher():
    print("=== SSH COMMAND RUNNER ===\n")

    if not INVENTORY_FILE.exists():
        print(f"Fichier d'inventaire introuvable : {INVENTORY_FILE}")
        return

    try:
        hosts = load_hosts(INVENTORY_FILE)
    except OSError as exc:
        print(f"Impossible de lire l'inventaire : {exc}")
        return

    if not hosts:
        print("Aucun hôte dans l'inventaire.")
        return

    print(f"{len(hosts)} machine(s) chargée(s).\n")

    command = input("Commande à exécuter : ").strip()

    if not command:
        print("La commande ne peut pas être vide.")
        return

    username = input("Utilisateur SSH : ").strip()
    password = getpass.getpass("Mot de passe SSH : ")

    results = []

    for host in hosts:
        result = ssh_execution(
            username=username,
            password=password,
            host=host,
            command=command,
        )
        results.append(result)

    generate_reports(results, command)


if __name__ == "__main__":
    launcher()

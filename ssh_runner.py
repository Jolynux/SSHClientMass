
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
DEFAULT_SSH_PORT = 22


def load_hosts(filename):
    """Charge les hôtes et leurs ports depuis un fichier texte.

    Formats acceptés :
        VM1
        PORT=8222
        VM2:2222

    Le port par défaut est 22.
    Un port spécifique à un hôte est prioritaire sur le port global.
    """

    default_port = DEFAULT_SSH_PORT
    hosts = []

    with open(filename, "r", encoding="utf-8") as file:
        lines = [
            line.strip()
            for line in file
            if line.strip() and not line.lstrip().startswith("#")
        ]

    # Lecture du port global.
    for line in lines:
        if line.upper().startswith("PORT="):
            port_str = line.split("=", 1)[1].strip()

            try:
                default_port = int(port_str)
            except ValueError:
                raise ValueError(
                    f"Port global invalide dans l'inventaire : {line}"
                )

            if not 1 <= default_port <= 65535:
                raise ValueError(
                    f"Port global hors limites : {default_port}"
                )

    # Lecture des hôtes.
    for line in lines:
        if line.upper().startswith("PORT="):
            continue

        if ":" in line:
            host, port_str = line.rsplit(":", 1)

            try:
                port = int(port_str)
            except ValueError:
                raise ValueError(
                    f"Port invalide dans l'entrée : {line}"
                )

            if not 1 <= port <= 65535:
                raise ValueError(
                    f"Port hors limites dans l'entrée : {line}"
                )
        else:
            host = line
            port = default_port

        host = host.strip()

        if not host:
            raise ValueError(
                f"Nom d'hôte vide dans l'entrée : {line}"
            )

        hosts.append({
            "host": host,
            "port": port,
        })

    return hosts


def ssh_execution(username, password, host, port, command):
    """Exécute une commande SSH et retourne un résultat structuré."""

    result = {
        "Hote": host,
        "Port": port,
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
        print(f"[CONNEXION] {host}:{port}")

        ssh.connect(
            hostname=host,
            port=port,
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

        # Récupération des sorties.
        result["Sortie standard"] = stdout.read().decode(
            "utf-8", errors="replace"
        ).strip()

        result["Erreur standard"] = stderr.read().decode(
            "utf-8", errors="replace"
        ).strip()

        # Récupération du code retour.
        result["Code retour"] = stdout.channel.recv_exit_status()

        result["Statut"] = (
            "OK" if result["Code retour"] == 0 else "ECHEC"
        )

    except AuthenticationException:
        result["Erreur standard"] = (
            "Échec de l'authentification SSH"
        )

    except BadHostKeyException:
        result["Erreur standard"] = (
            "La clé SSH du serveur a changé"
        )

    except NoValidConnectionsError as exc:
        result["Erreur standard"] = (
            f"Connexion impossible : {exc}"
        )

    except (TimeoutError, OSError) as exc:
        result["Erreur standard"] = (
            f"Erreur réseau ou timeout : {exc}"
        )

    except SSHException as exc:
        result["Erreur standard"] = f"Erreur SSH : {exc}"

    except Exception as exc:
        result["Erreur standard"] = (
            f"Erreur inattendue : {type(exc).__name__}: {exc}"
        )

    finally:
        ssh.close()
        result["Duree (s)"] = round(
            time.monotonic() - start_time, 2
        )

    print(
        f"[{result['Statut']}] {host}:{port} "
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

    # Calcul de la synthèse.
    success_count = int((df["Statut"] == "OK").sum())
    failure_count = len(results) - success_count

    report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Rapport texte détaillé.
    with open(txt_file, "w", encoding="utf-8") as file:
        file.write("RAPPORT D'EXECUTION SSH\n")
        file.write("=" * 70 + "\n")
        file.write(f"Date : {report_date}\n")
        file.write(f"Commande : {command}\n")
        file.write(f"Nombre de machines : {len(results)}\n")
        file.write(f"Succès : {success_count}\n")
        file.write(f"Échecs : {failure_count}\n")
        file.write("=" * 70 + "\n\n")

        for result in results:
            file.write(f"HOTE : {result['Hote']}\n")
            file.write(f"PORT SSH : {result['Port']}\n")
            file.write(f"STATUT : {result['Statut']}\n")
            file.write(
                f"CODE RETOUR : {result['Code retour']}\n"
            )
            file.write(f"DUREE : {result['Duree (s)']} s\n")

            file.write("\n--- SORTIE STANDARD ---\n")
            file.write(result["Sortie standard"] or "(vide)")
            file.write("\n\n--- ERREUR STANDARD ---\n")
            file.write(result["Erreur standard"] or "(vide)")
            file.write("\n\n" + "-" * 70 + "\n\n")

    # Rapport Excel : synthèse + détails.
    summary = pd.DataFrame([
        {
            "Indicateur": "Date",
            "Valeur": report_date,
        },
        {
            "Indicateur": "Commande",
            "Valeur": command,
        },
        {
            "Indicateur": "Machines",
            "Valeur": len(results),
        },
        {
            "Indicateur": "Succès",
            "Valeur": success_count,
        },
        {
            "Indicateur": "Échecs",
            "Valeur": failure_count,
        },
    ])

    with pd.ExcelWriter(xlsx_file, engine="openpyxl") as writer:
        summary.to_excel(
            writer,
            sheet_name="Synthese",
            index=False,
        )

        df.to_excel(
            writer,
            sheet_name="Details",
            index=False,
        )

        # Ajustement de la largeur des colonnes.
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
    """Point d'entrée du programme."""

    print("=== SSH COMMAND RUNNER ===\n")

    if not INVENTORY_FILE.exists():
        print(
            f"Fichier d'inventaire introuvable : "
            f"{INVENTORY_FILE}"
        )
        return

    try:
        hosts = load_hosts(INVENTORY_FILE)

    except (OSError, ValueError) as exc:
        print(f"Impossible de charger l'inventaire : {exc}")
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

    if not username:
        print("L'utilisateur SSH ne peut pas être vide.")
        return

    password = getpass.getpass("Mot de passe SSH : ")

    results = []

    for entry in hosts:
        result = ssh_execution(
            username=username,
            password=password,
            host=entry["host"],
            port=entry["port"],
            command=command,
        )

        results.append(result)

    generate_reports(results, command)


if __name__ == "__main__":
    launcher()

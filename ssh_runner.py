
import getpass
import time
import socket
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
DEFAULT_OS = "auto"

# Types pris en charge
SUPPORTED_OS = {
    "auto",
    "linux",
    "windows",
    "macos",
    "shell",
    "network",
    "cisco_ios",
    "junos",
    "fortios",
}


def load_hosts(filename):
    """Charge les hôtes, les ports et les types depuis l'inventaire.

    Formats acceptés :
        VM1
        PORT=8222
        OS=windows
        VM2:2222
        VM3;os=linux;port=2200
        SWITCH1;os=cisco_ios
    """

    default_port = DEFAULT_SSH_PORT
    default_os = DEFAULT_OS
    hosts = []

    with open(filename, "r", encoding="utf-8") as file:
        lines = [
            line.strip()
            for line in file
            if line.strip()
            and not line.lstrip().startswith("#")
        ]

    # Paramètres globaux
    for line in lines:
        key, separator, value = line.partition("=")

        if not separator:
            continue

        key = key.strip().upper()
        value = value.strip()

        if key == "PORT":
            try:
                default_port = int(value)
            except ValueError as exc:
                raise ValueError(
                    f"Port global invalide : {line}"
                ) from exc

            if not 1 <= default_port <= 65535:
                raise ValueError(
                    f"Port global hors limites : {default_port}"
                )

        elif key == "OS":
            default_os = value.lower()

            if default_os not in SUPPORTED_OS:
                raise ValueError(
                    f"Type global non pris en charge : {value}"
                )

    # Entrées des hôtes
    for line in lines:
        key, separator, _ = line.partition("=")

        if separator and key.strip().upper() in {"PORT", "OS"}:
            continue

        parts = [part.strip() for part in line.split(";")]
        address = parts[0]

        if not address:
            raise ValueError(
                f"Nom d'hôte vide : {line}"
            )

        host = address
        port = default_port
        os_type = default_os

        # Compatibilité avec l'ancien format HOST:PORT.
        # Pour IPv6, utiliser HOST;port=PORT.
        if ":" in address:
            candidate_host, candidate_port = address.rsplit(":", 1)

            if candidate_port.isdigit():
                host = candidate_host.strip()
                port = int(candidate_port)

        # Paramètres spécifiques à l'hôte
        for option in parts[1:]:
            if not option:
                continue

            key, separator, value = option.partition("=")

            if not separator:
                raise ValueError(
                    f"Option invalide dans l'entrée : {option}"
                )

            key = key.strip().lower()
            value = value.strip()

            if key == "port":
                try:
                    port = int(value)
                except ValueError as exc:
                    raise ValueError(
                        f"Port invalide dans l'entrée : {line}"
                    ) from exc

            elif key == "os":
                os_type = value.lower()

            else:
                raise ValueError(
                    f"Option inconnue '{key}' dans : {line}"
                )

        if not 1 <= port <= 65535:
            raise ValueError(
                f"Port hors limites dans l'entrée : {line}"
            )

        if os_type not in SUPPORTED_OS:
            raise ValueError(
                f"Type d'hôte non pris en charge : {os_type}"
            )

        if not host:
            raise ValueError(
                f"Nom d'hôte vide dans l'entrée : {line}"
            )

        hosts.append({
            "host": host,
            "port": port,
            "os": os_type,
        })

    return hosts


def detect_os(ssh):
    """Détecte Linux, macOS ou Windows lorsque c'est possible.

    Retourne 'unknown' si le shell ne permet pas de conclure.
    """

    probes = [
        (
            "uname -s",
            lambda output: (
                "macos"
                if "darwin" in output.lower()
                else "linux"
                if "linux" in output.lower()
                else None
            ),
        ),
        (
            "cmd.exe /c ver",
            lambda output: (
                "windows"
                if "windows" in output.lower()
                else None
            ),
        ),
    ]

    for command, identify in probes:
        try:
            stdin, stdout, stderr = ssh.exec_command(
                command,
                timeout=5,
                get_pty=False,
            )

            channel = stdout.channel

            # Attendre une réponse, sans bloquer indéfiniment.
            deadline = time.monotonic() + 5

            while (
                not channel.exit_status_ready()
                and time.monotonic() < deadline
            ):
                time.sleep(0.1)

            if not channel.exit_status_ready():
                channel.close()
                continue

            output = stdout.read().decode(
                "utf-8", errors="replace"
            )

            detected = identify(output)

            if detected:
                return detected

        except (SSHException, OSError, TimeoutError):
            continue

    return "unknown"



NETWORK_TYPES = {
    "network",
    "cisco_ios",
    "junos",
    "fortios",
}


def execute_shell(ssh, command):
    """Exécute une commande via le canal SSH non interactif."""

    stdin, stdout, stderr = ssh.exec_command(
        command,
        timeout=COMMAND_TIMEOUT,
        get_pty=False,
    )

    stdin.close()
    channel = stdout.channel
    deadline = time.monotonic() + COMMAND_TIMEOUT

    output = bytearray()
    errors = bytearray()

    while True:
        received_data = False

        while channel.recv_ready():
            output.extend(channel.recv(65536))
            received_data = True

        while channel.recv_stderr_ready():
            errors.extend(channel.recv_stderr(65536))
            received_data = True

        if channel.exit_status_ready():
            # Lire les dernières données disponibles.
            while channel.recv_ready():
                output.extend(channel.recv(65536))

            while channel.recv_stderr_ready():
                errors.extend(channel.recv_stderr(65536))

            break

        if time.monotonic() >= deadline:
            channel.close()
            raise TimeoutError(
                f"La commande a dépassé {COMMAND_TIMEOUT} secondes"
            )

        if not received_data:
            time.sleep(0.05)

    exit_code = channel.recv_exit_status()

    return (
        output.decode("utf-8", errors="replace").strip(),
        errors.decode("utf-8", errors="replace").strip(),
        exit_code,
    )


def execute_network_cli(ssh, command):
    """Exécute une commande dans une CLI interactive.

    Le code retour est généralement indisponible de façon
    portable sur les équipements réseau.
    """

    channel = ssh.invoke_shell(
        term="vt100",
        width=200,
        height=1000,
    )

    channel.settimeout(0.2)

    # Consommer la bannière et l'invite initiale.
    initial_deadline = time.monotonic() + 2

    while time.monotonic() < initial_deadline:
        try:
            if channel.recv_ready():
                channel.recv(65536)
            else:
                time.sleep(0.05)
        except (socket.timeout, TimeoutError):
            break

    channel.send(command + "\n")

    output = bytearray()
    deadline = time.monotonic() + COMMAND_TIMEOUT
    last_data_time = time.monotonic()
    idle_timeout = 1.5

    try:
        while time.monotonic() < deadline:
            try:
                if channel.recv_ready():
                    chunk = channel.recv(65536)

                    if not chunk:
                        break

                    output.extend(chunk)
                    last_data_time = time.monotonic()

                elif time.monotonic() - last_data_time >= idle_timeout:
                    break

                else:
                    time.sleep(0.05)

            except (socket.timeout, TimeoutError):
                if time.monotonic() - last_data_time >= idle_timeout:
                    break

    finally:
        channel.close()

    if time.monotonic() >= deadline:
        raise TimeoutError(
            f"La CLI est restée active plus de {COMMAND_TIMEOUT} secondes"
        )

    return (
        output.decode("utf-8", errors="replace").strip(),
        "",
        None,
    )


def ssh_execution(username, password, host, port, command, os_type="auto"):
    """Exécute une commande SSH avec sélection du mode d'exécution."""

    result = {
        "Hote": host,
        "Port": port,
        "OS": os_type,
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

        effective_os = os_type.lower()

        if effective_os == "auto":
            effective_os = detect_os(ssh)

        result["OS"] = effective_os

        if effective_os in NETWORK_TYPES:
            stdout_text, stderr_text, exit_code = (
                execute_network_cli(ssh, command)
            )
        else:
            # linux, macos, windows, shell ou unknown :
            # utiliser le shell configuré sur le serveur SSH.
            stdout_text, stderr_text, exit_code = (
                execute_shell(ssh, command)
            )

        result["Sortie standard"] = stdout_text
        result["Erreur standard"] = stderr_text
        result["Code retour"] = exit_code

        if exit_code is None:
            # La CLI réseau ne fournit pas de code portable.
            result["Statut"] = "OK" if stdout_text else "INDETERMINE"
        else:
            result["Statut"] = (
                "OK" if exit_code == 0 else "ECHEC"
            )

    except AuthenticationException:
        result["Erreur standard"] = (
            "Échec de l'authentification SSH"
        )

    except BadHostKeyException:
        result["Erreur standard"] = (
            "La clé SSH du serveur ne correspond pas "
            "à celle enregistrée"
        )

    except NoValidConnectionsError as exc:
        result["Erreur standard"] = f"Connexion impossible : {exc}"

    except (TimeoutError, socket.timeout) as exc:
        result["Erreur standard"] = f"Timeout : {exc}"

    except OSError as exc:
        result["Erreur standard"] = f"Erreur réseau : {exc}"

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
        f"OS={result['OS']} "
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
            file.write(f"TYPE OS : {result['OS']}\n")
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
            os_type=entry["os"],
        )

        results.append(result)

    generate_reports(results, command)


if __name__ == "__main__":
    launcher()

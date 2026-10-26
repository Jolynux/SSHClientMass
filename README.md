# SSH Command Runner

**🇬🇧 English** | [🇫🇷 Français](#français)

A lightweight Python tool to execute commands remotely on multiple machines over SSH and generate detailed reports in TXT and Excel formats.

The tool is designed for system administration, Linux server management, troubleshooting, and repetitive operational tasks.

## Features

- **Multi-host execution:** Run the same command on multiple SSH servers sequentially.
- **Flexible SSH ports:**
  - Default port: `22`
  - Global port configuration for all hosts.
  - Individual port configuration for specific hosts.
- **Password authentication:** Enter SSH credentials interactively. Passwords are not stored in the inventory file.
- **Execution tracking:** Record execution status, return code, duration, standard output, and standard error.
- **Automatic reporting:** Generate detailed TXT reports and Excel workbooks.
- **Excel summary:** Includes execution statistics and detailed results for each host.
- **Inventory file:** Manage target hosts in a simple text file.
- **Error handling:** Handle common authentication, network, timeout, and SSH errors.

## Requirements

- Python 3.9 or later recommended.
- Network connectivity to the target SSH servers.
- SSH access and a valid account on each target host.

Python dependencies:

- [Paramiko](https://www.paramiko.org/) — SSH connections and remote command execution.
- [Pandas](https://pandas.pydata.org/) — Report data processing.
- [OpenPyXL](https://openpyxl.readthedocs.io/) — Excel report generation.

## Installation

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install paramiko pandas openpyxl
```

## Configuration

Create a `hosts.txt` file in the same directory as the script.

### 1. Default SSH port

If no port is specified, the tool uses port `22`.

```text
# Production servers
192.168.1.10
192.168.1.11
server01.example.com
```

### 2. Global SSH port

Use `PORT=<port>` to set a default port for all hosts that do not explicitly specify one.

```text
PORT=8222

192.168.1.10
192.168.1.11
server01.example.com
```

All three hosts will use port `8222`.

### 3. Individual SSH ports

Specify a port directly after the hostname, separated by a colon.

```text
server01:2222
server02:4222
server03:3456
```

Each host will use its configured port.

### 4. Mixed configuration

Global and individual ports can be combined.

```text
# Global default port
PORT=8222

# Uses port 8222
server01.example.com

# Uses port 2222
server02.example.com:2222

# Uses port 3456
192.168.1.50:3456

# Uses port 8222
192.168.1.51
```

**Port precedence:**

1. Individual host port, if specified.
2. Global port, if configured.
3. Default port `22`, otherwise.

Lines starting with `#` and blank lines are ignored.

> **Note:** The `HOST:PORT` syntax is intended for hostnames and IPv4 addresses. IPv6 addresses require additional parsing support.

## Usage

Run the script:

```bash
python ssh_runner.py
```

The program will prompt for:

1. The command to execute.
2. The SSH username.
3. The SSH password.

Example:

```text
=== SSH COMMAND RUNNER ===

4 machine(s) chargée(s).

Commande à exécuter : uptime
Utilisateur SSH : admin
Mot de passe SSH:
```

The command is executed sequentially on each configured host.

Example console output:

```text
[CONNEXION] server01.example.com:8222
[OK] server01.example.com:8222 (code=0, 0.84 s)

[CONNEXION] server02.example.com:2222
[OK] server02.example.com:2222 (code=0, 1.12 s)
```

The exact output depends on the target servers and the command executed.

## Reports

Reports are automatically generated in the `reports/` directory.

```text
reports/
├── rapport_ssh_20261026_180000.txt
└── rapport_ssh_20261026_180000.xlsx
```

Filenames include a timestamp to distinguish separate executions.

### TXT report

Contains:

- Execution date and command.
- Number of hosts, successes, and failures.
- Hostname and SSH port.
- Execution status and return code.
- Execution duration.
- Standard output and standard error.

### Excel report

The workbook contains two worksheets:

| Worksheet | Description |
|---|---|
| `Synthese` | Execution date, command, number of hosts, successes, and failures. |
| `Details` | Per-host port, status, return code, duration, standard output, and standard error. |

Column widths are adjusted automatically for readability.

## Error handling

The script handles common errors, including:

- SSH authentication failures.
- SSH host key mismatches.
- Connection failures.
- Network errors and timeouts.
- SSH protocol errors.
- Unexpected exceptions.

A failed connection is recorded in the report so that execution can continue with the remaining hosts.

## Security considerations

- **Host key verification:** The current implementation uses Paramiko's `AutoAddPolicy()`, which automatically trusts previously unknown SSH host keys. This is convenient for testing but is not recommended for sensitive environments. Verify host keys and use a trusted `known_hosts` configuration in production.
- **Credentials:** Passwords are requested interactively and are not written to `hosts.txt` or the generated reports. Avoid running the tool in environments that record terminal input.
- **Command execution:** Commands run with the privileges of the specified SSH account. Use least-privilege accounts and review commands before execution.
- **Timeouts:** Connection and command timeouts are configurable through `CONNECT_TIMEOUT` and `COMMAND_TIMEOUT`.
- **Network access:** Ensure that firewalls and SSH services allow connections to the configured ports.

## Limitations

- Hosts are processed sequentially, not concurrently.
- Password authentication is configured explicitly; SSH agent and private-key authentication are disabled in the current implementation.
- Interactive remote commands requiring additional input are not supported.
- The current inventory format does not support IPv6 address parsing with ports.

## Project structure

```text
.
├── ssh_runner.py
├── hosts.txt
├── reports/
└── README.md
```

The `reports/` directory is created automatically when reports are generated.

## License

Choose a license appropriate for your project and add a `LICENSE` file to the repository. For example, MIT is a common choice for open-source tools.

---

# Français

Un outil Python léger permettant d'exécuter des commandes à distance sur plusieurs machines via SSH et de générer des rapports détaillés aux formats TXT et Excel.

Ce projet est destiné à l'administration système, à la gestion de serveurs Linux, au dépannage et à l'automatisation de tâches opérationnelles répétitives.

## Fonctionnalités

- **Exécution multi-hôtes :** exécution séquentielle d'une même commande sur plusieurs serveurs SSH.
- **Gestion flexible des ports SSH :**
  - Port par défaut : `22`.
  - Configuration d'un port global pour tous les hôtes.
  - Configuration d'un port individuel pour chaque machine.
- **Authentification par mot de passe :** saisie interactive des identifiants SSH. Les mots de passe ne sont pas enregistrés dans l'inventaire.
- **Suivi des exécutions :** statut, code retour, durée, sortie standard et erreur standard.
- **Génération automatique de rapports :** fichiers TXT détaillés et classeurs Excel.
- **Synthèse Excel :** statistiques globales et résultats détaillés par machine.
- **Fichier d'inventaire :** gestion des machines cibles dans un simple fichier texte.
- **Gestion des erreurs :** prise en charge des erreurs courantes d'authentification, de réseau, de timeout et de protocole SSH.

## Prérequis

- Python 3.9 ou supérieur recommandé.
- Connectivité réseau vers les serveurs SSH cibles.
- Un accès SSH valide sur chaque machine distante.

Dépendances Python :

- [Paramiko](https://www.paramiko.org/) — Connexions SSH et exécution de commandes distantes.
- [Pandas](https://pandas.pydata.org/) — Traitement des données des rapports.
- [OpenPyXL](https://openpyxl.readthedocs.io/) — Génération des rapports Excel.

## Installation

Cloner le dépôt :

```bash
git clone <URL_DE_VOTRE_DEPOT>
cd <NOM_DE_VOTRE_DEPOT>
```

Créer et activer un environnement virtuel (recommandé) :

```bash
python -m venv .venv
```

Linux / macOS :

```bash
source .venv/bin/activate
```

Windows PowerShell :

```powershell
.\.venv\Scripts\Activate.ps1
```

Installer les dépendances :

```bash
python -m pip install paramiko pandas openpyxl
```

## Configuration

Créer un fichier `hosts.txt` dans le même répertoire que le script.

### 1. Port SSH par défaut

Si aucun port n'est spécifié, le programme utilise le port `22`.

```text
# Serveurs de production
192.168.1.10
192.168.1.11
server01.example.com
```

### 2. Port SSH global

Utiliser `PORT=<port>` pour définir un port par défaut pour toutes les machines qui ne disposent pas d'un port spécifique.

```text
PORT=8222

192.168.1.10
192.168.1.11
server01.example.com
```

Les trois machines utiliseront le port `8222`.

### 3. Ports SSH individuels

Indiquer le port après le nom de la machine, séparé par deux-points.

```text
server01:2222
server02:4222
server03:3456
```

Chaque machine utilisera le port configuré.

### 4. Configuration mixte

Les ports globaux et individuels peuvent être combinés.

```text
# Port global par défaut
PORT=8222

# Utilise le port 8222
server01.example.com

# Utilise le port 2222
server02.example.com:2222

# Utilise le port 3456
192.168.1.50:3456

# Utilise le port 8222
192.168.1.51
```

**Ordre de priorité des ports :**

1. Port individuel de la machine, s'il est défini.
2. Port global, s'il est configuré.
3. Port par défaut `22`, dans les autres cas.

Les lignes commençant par `#` et les lignes vides sont ignorées.

> **Remarque :** la syntaxe `HOTE:PORT` est prévue pour les noms d'hôtes et les adresses IPv4. La prise en charge des adresses IPv6 nécessite une adaptation du parsing.

## Utilisation

Lancer le script :

```bash
python ssh_runner.py
```

Le programme demande successivement :

1. La commande à exécuter.
2. L'utilisateur SSH.
3. Le mot de passe SSH.

Exemple :

```text
=== SSH COMMAND RUNNER ===

4 machine(s) chargée(s).

Commande à exécuter : uptime
Utilisateur SSH : admin
Mot de passe SSH:
```

La commande est exécutée séquentiellement sur chaque machine configurée.

Exemple de sortie console :

```text
[CONNEXION] server01.example.com:8222
[OK] server01.example.com:8222 (code=0, 0.84 s)

[CONNEXION] server02.example.com:2222
[OK] server02.example.com:2222 (code=0, 1.12 s)
```

La sortie exacte dépend des serveurs cibles et de la commande exécutée.

## Rapports générés

Les rapports sont automatiquement enregistrés dans le répertoire `reports/`.

```text
reports/
├── rapport_ssh_20261026_180000.txt
└── rapport_ssh_20261026_180000.xlsx
```

Les noms des fichiers contiennent un horodatage permettant de distinguer les différentes exécutions.

### Rapport TXT

Il contient :

- La date d'exécution et la commande.
- Le nombre de machines, de succès et d'échecs.
- Le nom de chaque machine et son port SSH.
- Le statut d'exécution et le code retour.
- La durée d'exécution.
- La sortie standard et l'erreur standard.

### Rapport Excel

Le classeur contient deux feuilles :

| Feuille | Description |
|---|---|
| `Synthese` | Date, commande, nombre de machines, succès et échecs. |
| `Details` | Port, statut, code retour, durée, sortie standard et erreur standard pour chaque machine. |

La largeur des colonnes est ajustée automatiquement pour améliorer la lisibilité.

## Gestion des erreurs

Le script gère notamment :

- Les échecs d'authentification SSH.
- Les changements de clé d'hôte SSH.
- Les échecs de connexion.
- Les erreurs réseau et les timeouts.
- Les erreurs du protocole SSH.
- Les exceptions inattendues.

Une connexion en échec est consignée dans le rapport, puis le programme poursuit le traitement des autres machines.

## Sécurité

- **Vérification des clés SSH :** l'implémentation actuelle utilise `AutoAddPolicy()`, qui accepte automatiquement les clés d'hôte inconnues. Cette approche est pratique pour les tests, mais déconseillée dans un environnement sensible. En production, il est préférable de vérifier les clés et d'utiliser un fichier `known_hosts` de confiance.
- **Identifiants :** les mots de passe sont demandés de manière interactive et ne sont enregistrés ni dans `hosts.txt` ni dans les rapports. Éviter les environnements qui enregistrent les saisies du terminal.
- **Exécution des commandes :** les commandes s'exécutent avec les privilèges du compte SSH utilisé. Privilégier les comptes à privilèges minimaux et vérifier les commandes avant leur exécution.
- **Timeouts :** les délais de connexion et d'exécution sont configurables via `CONNECT_TIMEOUT` et `COMMAND_TIMEOUT`.
- **Accès réseau :** vérifier que les pare-feu et les services SSH autorisent les connexions sur les ports configurés.

## Limitations

- Les machines sont traitées séquentiellement, et non en parallèle.
- L'authentification par mot de passe est explicitement configurée ; l'agent SSH et l'authentification par clé privée sont désactivés dans l'implémentation actuelle.
- Les commandes interactives nécessitant des saisies supplémentaires ne sont pas prises en charge.
- Le format d'inventaire actuel ne gère pas le parsing des adresses IPv6 accompagnées d'un port.

## Structure du projet

```text
.
├── ssh_runner.py
├── hosts.txt
├── reports/
└── README.md
```

Le répertoire `reports/` est créé automatiquement lors de la génération des rapports.

## Licence

Choisissez une licence adaptée à votre projet et ajoutez un fichier `LICENSE` au dépôt. La licence MIT est un choix courant pour les projets open source.

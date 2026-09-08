# mail_mcp — serveur MCP stdio

Serveur MCP qui parle IMAP. Aucun appel à un modèle ici — c'est le rôle du `daemon/` (phase 2).

## Installation

```bash
cd mcp_server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

```bash
cp .env.example .env
# édite .env avec tes identifiants (voir .env.example pour Gmail)
```

Les identifiants ne sont jamais lus ailleurs que dans l'environnement (`.env` local, non commité).

## Tools exposés

Lecture (destinés à être passés au modèle par le daemon) :

- `list_recent(folder="INBOX", limit=20, since=None)`
- `get_email(message_id)`
- `search_emails(query, limit=20)`

Écriture (présents ici pour être appelables via CLI/inspector, mais **jamais** passés
au modèle par le daemon — voir la contrainte de sécurité du projet) :

- `move_to_folder(message_id, folder)`
- `move_to_trash(message_id)` — jamais d'EXPUNGE, mémorise le dossier d'origine
- `restore(message_id)` — restaure depuis la Corbeille vers le dossier mémorisé
- `unsubscribe(message_id)` — POST one-click (RFC 8058) si supporté, sinon retourne l'URL sans l'ouvrir

## Tester avec l'inspector MCP

```bash
npx @modelcontextprotocol/inspector mail-mcp
```

Ou sans installation du package, directement depuis les sources :

```bash
npx @modelcontextprotocol/inspector python3 -m mail_mcp.server
```

L'inspector doit lister les 7 tools et permettre d'appeler `list_recent` sans écrire de code.

## Notes d'implémentation

- Le dossier Corbeille est résolu dynamiquement via l'attribut IMAP `\Trash`
  (RFC 6154, annoncé par Gmail) plutôt que codé en dur — évite un nom de dossier
  localisé qui casserait selon la langue du compte.
- `message_id` désigne partout la valeur de l'en-tête `Message-ID`, pas l'UID IMAP
  interne (qui n'est pas stable entre dossiers). Les tools de lecture/écriture
  cherchent le message dans `INBOX` puis dans la Corbeille.
- `move`/`move_to_trash` utilisent l'extension IMAP `MOVE` (RFC 6851, supportée par
  Gmail) via `imap-tools`, qui ne fait jamais de `STORE \Deleted` + `EXPUNGE`.

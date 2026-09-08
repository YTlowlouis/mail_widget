# mail_daemon — client MCP + boucle Claude

Lit les mails via `mcp_server` (jamais directement), fait résumer/classer les nouveaux fils
par Claude, écrit `~/.cache/mail-widget/state.json`. N'appelle jamais IMAP directement.

## Installation

```bash
cd daemon
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

```bash
cp .env.example .env
# édite .env: au minimum ANTHROPIC_API_KEY
```

Les identifiants IMAP restent dans `mcp_server/.env` (déjà configuré en phase 1) — le daemon
les charge automatiquement de là, inutile de les dupliquer.

Si `mcp_server` et `daemon` utilisent des venvs séparés (le cas par défaut), mets le chemin
absolu de `mail-mcp` dans `MAIL_MCP_COMMAND` (voir `.env.example`), sinon le daemon ne le
trouvera pas dans son PATH.

## Lancer manuellement

```bash
mail-widget-daemon
```

Poll toutes les 3 minutes (`MAIL_WIDGET_POLL_SECONDS`), écrit l'état dans
`~/.cache/mail-widget/state.json` après chaque cycle.

## Vérifier le résultat

```bash
cat ~/.cache/mail-widget/state.json | jq
```

Chaque entrée de `threads` : `thread_key`, `message_ids`, `subject`, `from`, `date`,
`is_unread`, `message_count`, `resume`, `urgence` (`action`/`info`/`bruit`), `raison`.

## Actions (CLI, jamais appelée par le modèle)

```bash
mail-widget-ctl trash <message_id>
mail-widget-ctl archive <message_id> [--folder "..."]
mail-widget-ctl restore <message_id>
mail-widget-ctl unsubscribe <message_id>
```

Chaque commande ouvre sa propre session MCP courte, appelle un seul tool d'écriture du
serveur MCP, affiche le résultat en JSON sur stdout, et quitte (code 1 en cas d'erreur).

## systemd (service utilisateur)

```bash
mkdir -p ~/.config/systemd/user
cp systemd/mail-widget-daemon.service ~/.config/systemd/user/
# édite les chemins WorkingDirectory/ExecStart dans le fichier copié si besoin
systemctl --user daemon-reload
systemctl --user enable --now mail-widget-daemon
journalctl --user -u mail-widget-daemon -f
```

## Garanties de sécurité (rappel)

- Le modèle ne reçoit que `list_recent`, `get_email`, `search_emails` comme tools
  (`mcp_tools.READ_TOOL_NAMES`) — jamais les tools d'écriture, même si le serveur MCP les
  expose tous. Voir `mcp_tools.list_read_tools`.
- Les actions d'écriture (`actions.py`, exposées via `cli.py`) appellent le serveur MCP
  directement, sans jamais passer par une boucle d'agent Claude.
- Le corps de chaque mail est délimité par `<email>...</email>` dans le prompt et présenté
  explicitement comme des données, pas des instructions (voir `classifier.SYSTEM_PROMPT`).
  Il est déjà HTML-strippé et tronqué à ~2000 caractères par `mcp_server`.
- La sortie du modèle est demandée avec un schéma pydantic strict (`schema.py`,
  `output_format=EmailClassification`). Si elle ne valide pas, elle est rejetée : le fil
  n'est marqué "vu" nulle part et sera retenté au prochain poll, jamais affiché comme une
  vraie classification inventée.
- Aucun outil d'envoi de mail n'existe nulle part dans le projet.

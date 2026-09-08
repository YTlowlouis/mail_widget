# mail_daemon — client MCP + boucle Groq

Lit les mails via `mcp_server` (jamais directement), fait résumer/classer les nouveaux fils
par un modèle Groq, écrit `~/.cache/mail-widget/state.json`. N'appelle jamais IMAP directement.

Groq n'a pas d'équivalent au `tool_runner` d'Anthropic (pas de helper MCP côté client, pas de
structured output natif fiable multi-modèles) : la boucle d'agent (appel modèle -> tool_calls
-> exécution -> réponse) et la validation du JSON de sortie sont donc implémentées à la main
dans `classifier.py`, plutôt que déléguées au SDK.

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
# édite .env: au minimum GROQ_API_KEY
```

Clé API Groq (gratuite pour démarrer, pas de carte bancaire requise) :
https://console.groq.com -> API Keys -> Create API Key

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
`~/.cache/mail-widget/state.json` après chaque cycle. Modèle par défaut :
`openai/gpt-oss-20b` (configurable via `MAIL_WIDGET_MODEL`).

## Vérifier le résultat

```bash
cat ~/.cache/mail-widget/state.json | jq
```

Chaque entrée de `threads` : `thread_key`, `message_ids`, `subject`, `from`, `date`,
`is_unread`, `message_count`, `resume`, `urgence` (`action`/`info`/`bruit`), `raison`,
`otp_code` (string ou `null`). `otp_code` est extrait par regex déterministe du corps du
message représentatif (`otp.py`), jamais deviné par le modèle — un code n'est retourné que
s'il est trouvé à proximité d'un mot-clé lié à la vérification/l'authentification.

## Actions (CLI, jamais appelée par le modèle)

```bash
mail-widget-ctl trash <message_id>
mail-widget-ctl archive <message_id> [--folder "..."]
mail-widget-ctl restore <message_id>
mail-widget-ctl unsubscribe <message_id>
mail-widget-ctl reply <message_id> "corps du brouillon"
```

Chaque commande ouvre sa propre session MCP courte, appelle un seul tool d'écriture du
serveur MCP, affiche le résultat en JSON sur stdout, et quitte (code 1 en cas d'erreur).
`reply` enregistre un brouillon dans le dossier Brouillons — n'envoie jamais rien.

```bash
mail-widget-ctl reload
```

Force un cycle de poll immédiat (au lieu d'attendre jusqu'à `MAIL_WIDGET_POLL_SECONDS`) et
réécrit `state.json`. Contrairement aux autres commandes, `reload` a besoin de
`GROQ_API_KEY` (elle classe les nouveaux mails, donc appelle le modèle) — erreur claire si
absente plutôt qu'un échec silencieux. Peut tourner en parallèle du daemon en arrière-plan
sans risque de corruption (SQLite sérialise les écritures concurrentes).

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
  expose tous. Voir `mcp_tools.list_read_tools`. La boucle manuelle dans `classifier.py`
  refuse en plus explicitement tout appel de tool hors de cette liste, en défense
  supplémentaire (`_execute_tool_call`).
- Les actions d'écriture (`actions.py`, exposées via `cli.py`) appellent le serveur MCP
  directement, sans jamais passer par une boucle d'agent.
- Le corps de chaque mail est délimité par `<email>...</email>` dans le prompt et présenté
  explicitement comme des données, pas des instructions (voir `classifier.SYSTEM_PROMPT`).
  Il est déjà HTML-strippé et tronqué à ~2000 caractères par `mcp_server`.
- La sortie du modèle doit être un objet JSON à trois champs, validé strictement contre le
  schéma pydantic `EmailClassification` (`schema.py`). Si le JSON est absent, malformé, ou ne
  valide pas le schéma, il est rejeté : le fil n'est marqué "vu" nulle part et sera retenté au
  prochain poll, jamais affiché comme une vraie classification inventée.
- Aucun outil d'envoi de mail n'existe nulle part dans le projet.

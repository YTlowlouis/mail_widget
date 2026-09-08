# widget — AGS/Astal (GTK4)

Lit `~/.cache/mail-widget/state.json` écrit par le daemon, l'affiche, et appelle
`mail-widget-ctl` pour les actions. Ce dossier n'importe et n'appelle **jamais** l'API du
modèle ni IMAP directement — c'est ce qui garantit que le widget reste instantané.

## Installation des dépendances (Ubuntu)

Le CLI `ags` (le "runner" de projets Astal/Gnim en TypeScript) est écrit en Go et s'appuie
sur des bibliothèques système compilées en Vala. Sur une distribution non-Arch comme Ubuntu,
la voie la plus fiable est celle documentée officiellement par le projet, via Nix (Nix
fonctionne très bien sur Ubuntu, ce n'est pas propre à NixOS) :

```bash
# 1. Installer Nix si ce n'est pas déjà fait: https://nixos.org/download
sh <(curl -L https://nixos.org/nix/install) --daemon

# 2. Entrer dans un environnement de dev avec ags + astal + gtk4-layer-shell fournis
nix develop github:aylur/ags
```

Alternative sans Nix (installation manuelle, plus de travail) : suivre la doc d'installation
d'Astal (dépendances système : `meson`, `vala`, `gobject-introspection`, `gtk3`,
`gtk-layer-shell`, `gtk4`, `gtk4-layer-shell`), compiler `astal-io`/`astal3`/`astal4` avec
meson, puis compiler le CLI `ags` avec Go (`cd cli && go build`) depuis le dépôt
[Aylur/ags](https://github.com/Aylur/ags) — il faut aussi `gjs`, `dart-sass`,
`blueprint-compiler` et `nodejs` disponibles dans le PATH au runtime.

Il faut aussi `wl-clipboard` (fournit `wl-copy`, utilisé pour "Copier le code OTP" et pour le
lien de désabonnement) :

```bash
sudo apt install wl-clipboard
```

## Lancer le widget

Depuis la racine du dépôt :

```bash
ags run widget
```

`ags` détecte `widget/app.ts` comme point d'entrée, le bundle (esbuild) et le lance avec
`gjs`. Aucune étape de build séparée n'est nécessaire pour du développement — relance
`ags run widget` après chaque modification (pas de hot-reload dans cette configuration
minimale).

Si `mail-widget-ctl` n'est pas dans le PATH du widget (venvs séparés), pointe dessus :

```bash
export MAIL_WIDGET_CTL=/chemin/vers/mail_widget/daemon/.venv/bin/mail-widget-ctl
ags run widget
```

## Ce que fait chaque fichier

- `app.ts` — point d'entrée, démarre l'application GTK.
- `src/state.ts` — lit `state.json`, le surveille avec `monitorFile` (rechargement
  automatique à chaque écriture atomique du daemon), valide strictement chaque entrée avant
  de l'exposer (un objet mal formé est ignoré, jamais affiché à moitié).
- `src/ctl.ts` — appelle `mail-widget-ctl` (argv en tableau, jamais une chaîne shell — aucun
  risque d'injection même si un Message-ID ou un texte de mail contient des caractères
  spéciaux).
- `src/clipboard.ts` — copie via `wl-copy`, texte transmis par stdin (jamais par argv).
- `src/proc.ts` — wrapper bas niveau commun (`Gio.Subprocess`) utilisé par les deux fichiers
  ci-dessus.
- `src/MailWidget.tsx` — fenêtre principale (liste des fils).
- `src/ThreadCard.tsx` — une carte par fil : résumé, badge d'urgence, actions rapides.

## Actions rapides et garanties de sécurité

- **Archiver / Corbeille / Désabonner** appellent `mail-widget-ctl`, qui appelle le serveur
  MCP directement — jamais le modèle.
- **Corbeille** ouvre une fenêtre d'annulation de 8 secondes ("Annuler" → `restore`) avant de
  faire disparaître les boutons d'action normaux — jamais de suppression définitive, jamais
  d'EXPUNGE (déjà garanti côté `mcp_server`, l'UI respecte juste la même logique).
- **Copier le code** n'apparaît que si `otp_code` est non-null dans `state.json` — extrait
  par regex déterministe côté daemon (`otp.py`), jamais deviné par le modèle ni par le
  widget.
- **Désabonner** : si le mail ne supporte que le lien classique (pas de RFC 8058 one-click),
  le lien est copié dans le presse-papiers plutôt qu'ouvert automatiquement — cohérent avec
  le fait que `mcp_server.unsubscribe` ne l'ouvre jamais lui-même.

## Non testé dans cette session

Je n'ai pas d'environnement GTK4/Wayland/Hyprland disponible ici pour lancer et voir ce
widget réellement s'afficher. Le code est écrit contre l'API réelle d'AGS 3.1.2/Astal/Gnim
(vérifiée en récupérant les sources depuis GitHub, pas de mémoire), mais **c'est à toi de le
lancer et de me dire ce qui ne va pas** — erreurs de compilation TypeScript, styles cassés,
comportement des actions, etc.

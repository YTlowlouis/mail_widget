# Prompt pour Claude Design — refonte UI du widget mail

## Contexte

C'est un **widget de bureau Hyprland/Wayland**, pas une page web : une fenêtre GTK4 ancrée
en haut à droite de l'écran (layer-shell), largeur fixe étroite (~380-420px), hauteur qui
peut aller jusqu'à ~640-700px de liste scrollable. Thème sombre par défaut (cohérent avec un
environnement Hyprland typique). Pas d'images/avatars — que du texte, des badges de couleur,
et des boutons compacts.

Elle affiche mes mails résumés et triés par urgence par un LLM, avec des actions rapides.
Peut afficher 20-30 fils de discussion en liste scrollable.

## Écran principal (fenêtre unique)

**En-tête** : titre "Mail" à gauche, bouton "Recharger" à droite (petit, texte seul, devient
"Chargement…" et se désactive pendant l'opération — peut prendre plusieurs secondes).

Sous l'en-tête, en cas de problème : une bande d'erreur (fond rosé/rouge translucide, texte
lisible, se referme d'elle-même).

**Liste de fils** (dans une zone scrollable) : une carte compacte par fil de discussion,
triée du plus récent au plus ancien.

## Contenu d'une carte

Données disponibles pour chaque fil :
- `urgence` : `"action"` (nécessite une réponse/décision), `"info"` (utile à savoir, pas
  d'action), ou `"bruit"` (notification automatique/newsletter) — doit être visible d'un
  coup d'œil, code couleur clair et cohérent dans toute l'UI (ex: rouge/rose = action, bleu =
  info, gris = bruit)
- `from` : adresse ou nom de l'expéditeur
- `date`
- `resume` : un résumé en une phrase généré par le modèle (remplace le sujet à l'affichage)
- `message_count` : si > 1, le fil regroupe plusieurs mails (ex: 7 notifications GitHub sur
  la même PR) — à indiquer discrètement ("7 messages dans ce fil")
- `is_unread` : à distinguer visuellement (les mails lus doivent se fondre un peu plus)
- `otp_code` : optionnel, un code de vérification à 4-8 chiffres extrait du mail — quand
  présent, un bouton "Copier XXXXXX" doit être bien visible (c'est une action à faible
  friction, l'utilisateur veut cliquer vite et coller ailleurs)

**Actions rapides par carte** (boutons compacts, en bas de la carte) :
- Copier le code (conditionnel, voir ci-dessus)
- Répondre — révèle une zone de texte multi-lignes + bouton "Enregistrer le brouillon"
  (jamais d'envoi automatique — le brouillon part dans Gmail, l'utilisateur relit et envoie
  lui-même)
- Archiver
- Corbeille — après clic, remplace temporairement les boutons par une barre "Déplacé vers la
  corbeille" + bouton "Annuler" pendant 8 secondes, avant que la carte disparaisse pour de
  bon
- Désabonner — si un lien de désabonnement classique (pas de one-click) est utilisé, un
  message "Lien copié" doit s'afficher (le lien est copié dans le presse-papiers, jamais
  ouvert automatiquement)

**Messages d'état transitoires** : une ligne de texte discrète apparaît/disparaît sous le
résumé pour confirmer une action ("Archivé", "Code copié", "Brouillon enregistré", ou un
message d'erreur) — visible quelques secondes puis s'efface.

**État vide** : si aucun fil, un message centré "Aucun mail à afficher".

## Contraintes de design

- Palette sombre, lisible, pas trop chargée — c'est un widget qu'on regarde en coin d'œil
  entre deux tâches, pas une appli qu'on utilise à plein écran.
- Hiérarchie visuelle claire entre "action" (doit sauter aux yeux) et "bruit" (doit
  s'effacer).
- Boutons compacts (petite taille de police, padding réduit) — beaucoup d'actions doivent
  tenir sur une carte étroite sans wrapper sur 3 lignes.
- Densité : viser environ 90-120px de hauteur par carte pour qu'une dizaine de mails restent
  visibles sans trop scroller.
- Pas de fioritures inutiles (pas d'avatars, pas d'illustrations) — c'est un outil de
  productivité, la vitesse de lecture prime sur l'esthétique décorative.

## Ce qui ne doit pas changer

L'implémentation (AGS/Astal, GTK4, layer-shell) impose des contraintes que le design doit
respecter : polices/tailles en unités GTK classiques (pas de web fonts exotiques),
composants standards (box, button, label, revealer, scrolledwindow) plutôt que des mises en
page CSS avancées type grid/flexbox complexe. Un design trop "web" serait difficile à
retraduire fidèlement en CSS GTK.

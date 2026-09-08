// Appelle mail-widget-ctl (daemon/mail_daemon/cli.py) pour les actions d'écriture.
// Ce fichier n'appelle jamais l'API du modèle ni IMAP directement — c'est tout l'intérêt
// de l'architecture: le widget ne fait qu'exécuter la CLI et lire son résultat.
import GLib from "gi://GLib?version=2.0"
import { run } from "./proc"

// Si mcp_server/daemon/widget ne partagent pas le même venv, mail-widget-ctl peut ne pas
// être dans le PATH du widget: MAIL_WIDGET_CTL permet de pointer vers le binaire exact,
// comme MAIL_MCP_COMMAND côté daemon.
const CTL_COMMAND = GLib.getenv("MAIL_WIDGET_CTL") ?? "mail-widget-ctl"

export interface CtlResult {
  status: string
  message_id?: string
  detail?: string | null
  url?: string | null
  [key: string]: unknown
}

async function runCtl(args: string[]): Promise<CtlResult> {
  let stdout: string, stderr: string, exitCode: number
  try {
    ;({ stdout, stderr, exitCode } = await run([CTL_COMMAND, ...args]))
  } catch (error) {
    // Le process n'a même pas pu être lancé (binaire introuvable/pas exécutable) — l'erreur
    // GLib brute ("g_spawn_sync failed", "Failed to execute child process"...) ne dit pas
    // pourquoi, donc on donne le diagnostic exact plutôt que de la laisser remonter telle quelle.
    throw new Error(
      `Impossible de lancer "${CTL_COMMAND}" (${error}). ` +
        `Vérifie qu'il existe et qu'il est exécutable, ou exporte MAIL_WIDGET_CTL vers son ` +
        `chemin absolu (ex: daemon/.venv/bin/mail-widget-ctl) dans le terminal qui lance le widget.`,
    )
  }
  // mail-widget-ctl écrit toujours exactement une ligne de JSON sur stdout, succès ou
  // échec (voir cli.py). stderr n'est utilisé qu'en dernier recours, si la commande n'a
  // pas pu être lancée du tout (ex: binaire introuvable).
  const raw = stdout || stderr

  let parsed: CtlResult
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error(raw || `${CTL_COMMAND} a échoué (code ${exitCode})`)
  }

  if (parsed.status === "error") {
    throw new Error(typeof parsed.detail === "string" ? parsed.detail : `${CTL_COMMAND}: échec`)
  }

  return parsed
}

export const trash = (messageId: string) => runCtl(["trash", messageId])
export const archive = (messageId: string) => runCtl(["archive", messageId])
export const restore = (messageId: string) => runCtl(["restore", messageId])
export const unsubscribe = (messageId: string) => runCtl(["unsubscribe", messageId])
// Enregistre un brouillon de réponse (jamais envoyée, voir mcp_server.save_draft_reply).
export const reply = (messageId: string, body: string) => runCtl(["reply", messageId, body])
// Force un cycle de poll immédiat côté daemon. Peut prendre plusieurs secondes (voire
// dizaines de secondes s'il y a beaucoup de nouveaux mails) — pas de timeout imposé ici.
export const reload = () => runCtl(["reload"])

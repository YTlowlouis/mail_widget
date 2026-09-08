import Pango from "gi://Pango"
import GLib from "gi://GLib?version=2.0"
import { Gtk } from "ags/gtk4"
import { createState } from "ags"
import { dismissThread, type Thread } from "./state"
import * as ctl from "./ctl"
import { copyToClipboard } from "./clipboard"

const UNDO_WINDOW_SECONDS = 8
const STATUS_MESSAGE_SECONDS = 5

const URGENCE_LABEL: Record<Thread["urgence"], string> = {
  action: "Action",
  info: "Info",
  bruit: "Bruit",
}

function formatDate(iso: string): string {
  const date = GLib.DateTime.new_from_iso8601(iso, null)
  if (!date) return iso
  return date.to_local().format("%d/%m %H:%M") ?? iso
}

export default function ThreadCard({ thread }: { thread: Thread }) {
  // Le fil peut contenir plusieurs messages (regroupement par In-Reply-To/References,
  // ex: notifications GitHub) — les actions portent sur le plus récent du fil.
  const targetId = thread.message_ids[thread.message_ids.length - 1]

  const [busy, setBusy] = createState<string | null>(null)
  const [trashed, setTrashed] = createState(false)
  const [status, setStatus] = createState<string | null>(null)
  // Pas un state réactif: juste l'id du timer d'annulation en cours, pour pouvoir
  // l'annuler proprement si "Annuler" est cliqué avant son expiration.
  let undoTimeoutId: number | null = null

  function showStatus(message: string) {
    setStatus(message)
    GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, STATUS_MESSAGE_SECONDS, () => {
      setStatus((current) => (current === message ? null : current))
      return GLib.SOURCE_REMOVE
    })
  }

  async function handleArchive() {
    setBusy("archive")
    try {
      await ctl.archive(targetId)
      // Pas de fenêtre d'annulation ici (ce n'est pas une suppression) — retrait immédiat,
      // sans attendre le prochain cycle du daemon pour confirmer.
      dismissThread(thread.thread_key)
    } catch (error) {
      showStatus(String(error))
    } finally {
      setBusy(null)
    }
  }

  async function handleTrash() {
    setBusy("trash")
    try {
      await ctl.trash(targetId)
      setTrashed(true)
      // Après la fenêtre d'annulation, le fil disparaît vraiment de la liste (via
      // dismissThread) plutôt que de repasser en mode normal comme si de rien n'était —
      // sans attendre le prochain cycle du daemon (jusqu'à 3 minutes) pour confirmer.
      undoTimeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, UNDO_WINDOW_SECONDS, () => {
        undoTimeoutId = null
        dismissThread(thread.thread_key)
        return GLib.SOURCE_REMOVE
      })
    } catch (error) {
      showStatus(String(error))
    } finally {
      setBusy(null)
    }
  }

  async function handleRestore() {
    if (undoTimeoutId !== null) {
      GLib.source_remove(undoTimeoutId)
      undoTimeoutId = null
    }
    setBusy("restore")
    try {
      await ctl.restore(targetId)
      setTrashed(false)
      showStatus("Restauré")
    } catch (error) {
      showStatus(String(error))
    } finally {
      setBusy(null)
    }
  }

  async function handleUnsubscribe() {
    setBusy("unsubscribe")
    try {
      const result = await ctl.unsubscribe(targetId)
      if (result.status === "posted") {
        showStatus("Désabonnement effectué")
      } else if (result.status === "link_only" && typeof result.url === "string") {
        // Jamais ouvert automatiquement (voir mcp_server.unsubscribe) — copié pour que
        // l'utilisateur l'ouvre lui-même s'il le souhaite.
        await copyToClipboard(result.url)
        showStatus("Lien de désabonnement copié")
      } else {
        showStatus(typeof result.detail === "string" ? result.detail : "Désabonnement impossible")
      }
    } catch (error) {
      showStatus(String(error))
    } finally {
      setBusy(null)
    }
  }

  async function handleCopyOtp() {
    if (!thread.otp_code) return
    try {
      await copyToClipboard(thread.otp_code)
      showStatus("Code copié")
    } catch (error) {
      showStatus(String(error))
    }
  }

  return (
    <box orientation={Gtk.Orientation.VERTICAL} class={`thread-card urgence-${thread.urgence}`} spacing={4}>
      <box spacing={6}>
        <label label={URGENCE_LABEL[thread.urgence]} class={`badge badge-${thread.urgence}`} />
        <label label={thread.from} class="from" ellipsize={Pango.EllipsizeMode.END} hexpand xalign={0} />
        <label label={formatDate(thread.date)} class="date" />
      </box>

      <label label={thread.resume} class="resume" xalign={0} wrap wrapMode={Pango.WrapMode.WORD_CHAR} />

      {thread.message_count > 1 && (
        <label label={`${thread.message_count} messages dans ce fil`} class="count" xalign={0} />
      )}

      <revealer revealChild={status((s) => s !== null)} transitionType={Gtk.RevealerTransitionType.SLIDE_DOWN}>
        <label label={status((s) => s ?? "")} class="status-message" xalign={0} wrap />
      </revealer>

      <revealer revealChild={trashed} transitionType={Gtk.RevealerTransitionType.SLIDE_DOWN}>
        <box spacing={4} class="undo-bar">
          <label label="Déplacé vers la corbeille" hexpand xalign={0} />
          <button onClicked={handleRestore} sensitive={busy((b) => b === null)} class="action-btn">
            <label label="Annuler" />
          </button>
        </box>
      </revealer>

      <revealer revealChild={trashed((t) => !t)} transitionType={Gtk.RevealerTransitionType.SLIDE_DOWN}>
        <box spacing={4} class="actions">
          {thread.otp_code && (
            <button onClicked={handleCopyOtp} sensitive={busy((b) => b === null)} class="action-btn otp-btn">
              <label label={`Copier ${thread.otp_code}`} />
            </button>
          )}
          <button onClicked={handleArchive} sensitive={busy((b) => b === null)} class="action-btn">
            <label label="Archiver" />
          </button>
          <button onClicked={handleTrash} sensitive={busy((b) => b === null)} class="action-btn">
            <label label="Corbeille" />
          </button>
          <button onClicked={handleUnsubscribe} sensitive={busy((b) => b === null)} class="action-btn">
            <label label="Désabonner" />
          </button>
        </box>
      </revealer>
    </box>
  )
}

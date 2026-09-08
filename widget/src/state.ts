// Lit et surveille ~/.cache/mail-widget/state.json écrit par le daemon.
// Ce fichier n'appelle jamais l'API du modèle ni IMAP: seule lecture d'un fichier local,
// c'est ce qui garantit que le widget reste instantané et n'attend jamais le réseau.
import GLib from "gi://GLib?version=2.0"
import { readFileAsync, monitorFile } from "ags/file"
import { createState } from "ags"

export type Urgence = "action" | "info" | "bruit"

export interface Thread {
  thread_key: string
  message_ids: string[]
  subject: string
  from: string
  date: string
  is_unread: boolean
  message_count: number
  resume: string
  urgence: Urgence
  raison: string
  otp_code: string | null
}

interface StateFile {
  generated_at: string
  threads: Thread[]
}

const STATE_PATH =
  GLib.getenv("MAIL_WIDGET_STATE_PATH") ??
  GLib.build_filenamev([GLib.get_home_dir(), ".cache", "mail-widget", "state.json"])

const [threads, setThreads] = createState<Thread[]>([])
const [lastError, setLastError] = createState<string | null>(null)
const [generatedAt, setGeneratedAt] = createState<string | null>(null)

function isThread(value: unknown): value is Thread {
  if (typeof value !== "object" || value === null) return false
  const t = value as Record<string, unknown>
  return (
    typeof t.thread_key === "string" &&
    Array.isArray(t.message_ids) &&
    typeof t.subject === "string" &&
    typeof t.from === "string" &&
    typeof t.date === "string" &&
    typeof t.is_unread === "boolean" &&
    typeof t.message_count === "number" &&
    typeof t.resume === "string" &&
    (t.urgence === "action" || t.urgence === "info" || t.urgence === "bruit") &&
    typeof t.raison === "string" &&
    (t.otp_code === null || typeof t.otp_code === "string")
  )
}

async function reload() {
  let text: string
  try {
    text = await readFileAsync(STATE_PATH)
  } catch {
    // Pas d'erreur affichée: normal tant que le daemon n'a pas encore tourné une fois.
    return
  }

  let data: unknown
  try {
    data = JSON.parse(text)
  } catch (error) {
    // Peut arriver si le fichier est lu pendant une réécriture malgré l'os.replace atomique
    // côté daemon (fenêtre de course très courte) — on ignore, le prochain événement du
    // moniteur ou le prochain cycle de poll du daemon redéclenchera une lecture propre.
    setLastError(`state.json illisible: ${error}`)
    return
  }

  if (typeof data !== "object" || data === null || !Array.isArray((data as StateFile).threads)) {
    setLastError("state.json a un format inattendu")
    return
  }

  // Validation stricte, comme la sortie du modèle côté daemon: une entrée mal formée est
  // ignorée plutôt qu'affichée à moitié ou interprétée au hasard.
  const valid = (data as StateFile).threads.filter(isThread)
  setThreads(valid)
  setGeneratedAt((data as StateFile).generated_at ?? null)
  setLastError(null)
}

monitorFile(STATE_PATH, () => {
  reload()
})

reload()

export { threads, lastError, generatedAt }

// Copie dans le presse-papiers via wl-copy (standard sur Hyprland/wlroots).
// Le texte passe par stdin, jamais par un argv shell: aucun risque d'injection, même pour
// un code OTP ou une URL de désabonnement extraits d'un mail non fiable.
import { run } from "./proc"

export async function copyToClipboard(text: string): Promise<void> {
  const { exitCode, stderr } = await run(["wl-copy"], text)
  if (exitCode !== 0) {
    throw new Error(stderr || "wl-copy a échoué (installé ?)")
  }
}

// Wrapper bas niveau autour de Gio.Subprocess, utilisé par ctl.ts et clipboard.ts.
//
// On n'utilise pas les helpers execAsync/exec d'ags/process ici: ils rejettent la promesse
// sur un code de sortie non nul (perdant stdout au passage) et n'acceptent pas de contenu à
// écrire sur stdin. On a besoin des deux (lire stdout même en cas d'échec pour mail-widget-ctl,
// écrire sur stdin pour wl-copy) donc on appelle directement l'API GJS/Gio.
//
// argv est toujours un tableau, jamais une chaîne passée à un shell: aucune interpolation,
// donc aucun risque d'injection même si un Message-ID ou un texte de mail contient des
// caractères spéciaux (<, >, ;, `, ...).
import Gio from "gi://Gio?version=2.0"

export interface ProcessResult {
  stdout: string
  stderr: string
  exitCode: number
}

export function run(argv: string[], stdin: string | null = null): Promise<ProcessResult> {
  return new Promise((resolve, reject) => {
    let process: Gio.Subprocess
    try {
      process = Gio.Subprocess.new(
        argv,
        Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE,
      )
    } catch (error) {
      reject(error)
      return
    }

    process.communicate_utf8_async(stdin, null, (_source, res) => {
      try {
        const [, stdout, stderr] = process.communicate_utf8_finish(res)
        resolve({
          stdout: stdout.trim(),
          stderr: stderr.trim(),
          exitCode: process.get_exit_status(),
        })
      } catch (error) {
        reject(error)
      }
    })
  })
}

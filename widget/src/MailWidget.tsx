import app from "ags/gtk4/app"
import { Astal, Gtk } from "ags/gtk4"
import { For } from "ags"
import { threads, lastError } from "./state"
import ThreadCard from "./ThreadCard"

const { TOP, RIGHT } = Astal.WindowAnchor

export default function MailWidget() {
  return (
    <window
      visible
      name="mail-widget"
      class="MailWidget"
      anchor={TOP | RIGHT}
      exclusivity={Astal.Exclusivity.NORMAL}
      application={app}
    >
      <box orientation={Gtk.Orientation.VERTICAL} class="root" widthRequest={380}>
        <box class="header" spacing={6}>
          <label label="Mail" xalign={0} hexpand class="title" />
        </box>

        <label
          label={lastError((e) => e ?? "")}
          class="error-banner"
          visible={lastError((e) => e !== null)}
          wrap
          xalign={0}
        />

        <label
          label="Aucun mail à afficher"
          class="empty"
          visible={threads((t) => t.length === 0)}
        />

        <scrolledwindow vexpand class="thread-list-scroll" heightRequest={640}>
          <box orientation={Gtk.Orientation.VERTICAL} spacing={6} class="thread-list">
            <For each={threads}>{(thread) => <ThreadCard thread={thread} />}</For>
          </box>
        </scrolledwindow>
      </box>
    </window>
  )
}

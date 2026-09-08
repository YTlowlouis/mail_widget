import app from "ags/gtk4/app"
import style from "./style.scss"
import MailWidget from "./src/MailWidget"

app.start({
  instanceName: "mail-widget",
  css: style,
  main: MailWidget,
})

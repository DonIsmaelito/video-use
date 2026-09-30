import { build } from "esbuild";
import { readFile, writeFile } from "node:fs/promises";
const result = await build({
  entryPoints: ["app.js"],
  bundle: true,
  write: false,
  format: "iife",
  target: "es2022",
  minify: true,
});
const font = (
  await readFile("../../../studio/public/fonts/space-grotesk.woff2")
).toString("base64");
const html = (await readFile("template.html", "utf8")).replace(
  "/* FONT_DATA */",
  font,
);
await writeFile(
  "card.html",
  html.replace("/* APP_BUNDLE */", () =>
    result.outputFiles[0].text.replaceAll("</script", "<\\/script"),
  ),
);

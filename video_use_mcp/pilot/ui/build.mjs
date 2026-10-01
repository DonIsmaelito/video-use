import { build } from "esbuild";
import { readFile, writeFile } from "node:fs/promises";
const result = await build({entryPoints:["app.js"],bundle:true,write:false,format:"iife",target:"es2022",minify:true});
const html=await readFile("template.html","utf8");
const logo=await readFile(new URL("../../../website/public/brand/browser-use.svg",import.meta.url),"utf8");
const mark=logo.replace("<svg ",'<svg aria-hidden="true" focusable="false" ');
await writeFile("card.html",html.replace("<!-- PRODUCT_MARK -->",()=>mark).replace("/* APP_BUNDLE */",()=>result.outputFiles[0].text.replaceAll("</script","<\\/script")));

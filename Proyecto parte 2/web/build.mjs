// Construye el reporte interactivo y la presentación a partir de los artefactos.
//
// Arquitectura "calcular una vez, explorar muchas": los notebooks dejan tablas
// pequeñas en artifacts/ (y el proyecto 1 en su propia carpeta); este script
// las junta en un solo objeto DATOS y lo incrusta, con D3, los estilos y los
// módulos de gráficos, en dos HTML autocontenidos que funcionan sin internet.
//
// Uso: cd web && npm install && npm run build
import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(AQUI, "..");
const ART = join(RAIZ, "artifacts");
const ART_P1 = join(RAIZ, "..", "Proyecto parte 1", "artifacts");

const leer = (ruta) => readFileSync(ruta, "utf8");
const json = (ruta) => JSON.parse(leer(ruta));

// Todas las tablas pN_*.json de la parte 2, menos el índice.
const DATOS = { p2: {}, proyecto1: {} };
// Los identificadores de nodo son enteros de 64 bits que JavaScript no representa
// con exactitud; la web usa índices posicionales, así que esa columna se descarta.
// Las tablas que la web no usa (las de pares completos) no se incrustan.
const NO_INCRUSTAR = new Set(["p4_pares_afines", "p1_catalogo", "p1_plan"]);
for (const f of readdirSync(ART).filter((f) => /^p\d_.*\.json$/.test(f))) {
  const nombre = f.replace(".json", "");
  if (NO_INCRUSTAR.has(nombre)) continue;
  const tabla = json(join(ART, f));
  DATOS.p2[nombre] = Array.isArray(tabla) ? tabla.map(({ nodo, ...resto }) => resto) : tabla;
}
// Del proyecto 1 solo lo que el repaso necesita: portada, bitácora, concentración y reglas.
for (const f of ["p1_portada", "p1_bitacora", "p1_concentracion", "p1_postores_metodo", "p5_reglas",
                 "p2_casos", "p1_competencia", "p1_estacionalidad"]) {
  const ruta = join(ART_P1, f + ".json");
  if (existsSync(ruta)) {
    // El proyecto 1 se generó en otra máquina; si algún archivo no es UTF-8 se lee como Latin-1.
    const bruto = readFileSync(ruta);
    let texto = bruto.toString("utf8");
    if (texto.includes("�")) texto = bruto.toString("latin1");
    DATOS.proyecto1[f] = JSON.parse(texto);
  }
}

const d3 = leer(join(AQUI, "node_modules", "d3", "dist", "d3.min.js"));
const estilos = leer(join(AQUI, "src", "estilos.css"));
const graficos = leer(join(AQUI, "src", "graficos.js"));
const modulos = leer(join(AQUI, "src", "modulos.js"));

const opcional = (f) => existsSync(join(AQUI, "src", f)) ? leer(join(AQUI, "src", f)) : "";

function armar(plantilla, destino) {
  let html = leer(join(AQUI, "src", plantilla))
    .replace("<!--CONTENIDO-->", () => opcional("contenido_reporte.html"))
    .replace("<!--DIAPOSITIVAS-->", () => opcional("diapositivas.html"));
  // Figuras estáticas de los notebooks: <!--FIG:nombre--> se reemplaza por el SVG de figs/ como imagen incrustada.
  html = html.replace(/<!--FIG:([\w]+)-->/g, (_, f) =>
    `<img class="figura-nb" alt="${f}" src="data:image/svg+xml;base64,${readFileSync(join(RAIZ, "figs", f + ".svg")).toString("base64")}">`);
  const datos = JSON.stringify(DATOS).replace(/</g, "\\u003c");
  html = html
    .replace("/*ESTILOS*/", () => estilos)
    .replace("/*D3*/", () => d3)
    .replace("/*DATOS*/", () => `const DATOS = ${datos};`)
    .replace("/*GRAFICOS*/", () => graficos)
    .replace("/*MODULOS*/", () => modulos);
  // El selector entre proyectos va al final del body; el mismo archivo lo usa GitHub Pages para el proyecto 1.
  const selector = opcional("selector.html");
  html = html.includes("</body>") ? html.replace("</body>", () => selector + "\n</body>") : html + selector;
  mkdirSync(dirname(destino), { recursive: true });
  writeFileSync(destino, html);
  console.log(`${destino.replace(RAIZ + "/", "")}: ${(html.length / 1024).toFixed(0)} KB`);
}

armar("reporte.html", join(RAIZ, "docs", "index.html"));
armar("presentacion.html", join(RAIZ, "presentacion", "index.html"));
const tablas = Object.keys(DATOS.p2).length + Object.keys(DATOS.proyecto1).length;
console.log(`${tablas} tablas incrustadas`);

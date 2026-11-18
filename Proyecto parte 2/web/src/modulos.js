// Módulos de hallazgo. Cada uno dibuja en un contenedor y es el mismo en el
// reporte y en la presentación; solo cambia el tamaño de letra por CSS.
// Las cifras salen siempre de DATOS, nunca se escriben a mano en el gráfico.
const T = (n) => DATOS.p2[n] || [];

// En las listas de señales no se muestra el nombre de proveedores que son personas naturales.
// Si la tabla trae el tipo se usa; si no, un nombre sin marcador de persona jurídica se trata como persona.
const JURIDICA = /\b(S\.?\s?A\.?\s?C?\.?|S\.?\s?A\.?\s?A\.?|E\.?\s?I\.?\s?R\.?\s?L(TDA)?\.?|S\.?\s?R\.?\s?L\.?|SAC|EIRL|SRL|SA|LTDA|LIMITED|INC|GMBH|CONSORCIO|SOCIEDAD|EMPRESA|CORPORACION|GRUPO|INVERSIONES|COMPA[NÑ]IA|SUCURSAL|SERVICIOS|CONSTRUCTORA|COMERCIAL|LABORATORIOS?|INSTITUTO|DROGUERIA|DISTRIBUIDORA|CONTRATISTAS|IMPORTACIONES|INDUSTRIAS|NEGOCIACIONES|REPRESENTACIONES|ASOCIADOS|PERU|S\.?A\.?S)\b/i;
const privado = (nombre, tipo) => (tipo ? tipo === "persona natural" : !JURIDICA.test(nombre || "")) ? "persona natural, nombre reservado" : (nombre || "");
const P1 = (n) => DATOS.proyecto1[n] || [];

function control(raiz, etiqueta, min, max, paso, valor, alCambiar, formato = (v) => v) {
  const lab = document.createElement("label");
  lab.className = "control";
  lab.innerHTML = `<span>${etiqueta}</span><input type="range" min="${min}" max="${max}" step="${paso}" value="${valor}"><output></output>`;
  const inp = lab.querySelector("input"), out = lab.querySelector("output");
  const disparar = () => { out.textContent = formato(+inp.value); alCambiar(+inp.value); };
  inp.addEventListener("input", disparar);
  raiz.appendChild(lab);
  return { inp, disparar };
}
function chips(raiz, opciones, valor, alCambiar) {
  const c = document.createElement("div");
  c.className = "chips";
  opciones.forEach((o) => {
    const b = document.createElement("button");
    b.className = "chip"; b.type = "button"; b.textContent = o.t; b.setAttribute("aria-pressed", o.v === valor);
    b.onclick = () => { c.querySelectorAll(".chip").forEach((x) => x.setAttribute("aria-pressed", "false")); b.setAttribute("aria-pressed", "true"); alCambiar(o.v); };
    c.appendChild(b);
  });
  raiz.appendChild(c);
}
function partes(el, ...clases) {
  el.innerHTML = "";
  return clases.map((c) => { const d = document.createElement("div"); d.className = c; el.appendChild(d); return d; });
}
const leyenda = (el, items) => {
  el.innerHTML = items.map(([c, t]) => `<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;font-size:.92em;color:var(--tinta2)"><i style="width:11px;height:11px;border-radius:50%;background:${c};display:inline-block"></i>${t}</span>`).join("");
};

const MODULOS = {
  // ------------------------------------------------ Del proyecto 1 a este
  repaso(el) {
    const portada = P1("p1_portada")[0] || {};
    const conc = Object.fromEntries(P1("p1_concentracion").map((r) => [r.tramo, r]));
    const comp = P1("p1_competencia")[0] || {};
    const reglas = P1("p5_reglas");
    const resol = T("p1_resolucion");
    const cons = resol.find((r) => r.tipo === "consorcio") || {};
    const tarjetas = [
      [G.fmtN(portada.procesos_limpios), `procesos limpios de ${G.fmtN(portada.procesos_crudos)} crudos en el proyecto 1: la tabla analítica que este proyecto vuelve a leer`],
      [G.fmtN(conc["top 1 %"]?.pct_del_monto, 0) + " %", `del monto adjudicado lo gana el 1 % de los proveedores; Gini de ${G.fmtN(conc["top 1 %"]?.gini, 2)}`],
      [G.fmtN(comp.pct_postor_unico, 0) + " %", `de los procesos de menos de 50 mil soles tiene un solo postor: el indicador que la Parte I convierte en rasgo`],
      [G.fmtN(cons.identificadores), `códigos de consorcio que MinHash y LSH del proyecto 1 enseñaron a deduplicar; aquí son ${G.fmtN(cons.proveedores)} consorcios`],
    ];
    const [cif, txt] = partes(el, "cifras", "");
    cif.innerHTML = tarjetas.map(([n, t]) => `<div class="cifra"><div class="n">${n}</div><div class="t">${t}</div></div>`).join("");
    if (reglas.length) {
      const r = reglas[0];
      txt.innerHTML = `<p class="lectura" style="margin-top:18px">La canasta de las reglas de asociación no fue el proceso, porque el 98 % tenía un solo ítem, sino <b>lo que una entidad compra en un mes</b>. Con esa canasta salieron reglas como <b>${r.antecedente.toLowerCase()}</b> lleva a <b>${r.consecuente.toLowerCase()}</b> (lift ${G.fmtN(r.lift, 0)}), la huella de los programas alimentarios. Este proyecto toma esa misma idea y la vuelve matriz: <b>entidad por familia de producto</b>, que alimenta el recomendador.</p>`;
    }
  },

  // Reglas de asociación del proyecto 1: la canasta mensual por entidad.
  reglasP1(el, o = {}) {
    const r = P1("p5_reglas").slice(0, o.compacto ? 4 : 8);
    const t = (x) => G.corto(x.toLowerCase().replace(/ o anchov$/, ""), 34);
    el.innerHTML = `<p class="mini">Reglas de asociación del proyecto 1, canasta mensual por entidad</p><table class="datos"><tr><th>si compra</th><th>también compra</th><th class="num">confianza</th><th class="num">lift</th></tr>` +
      r.map((x) => `<tr><td>${x.antecedente.split(" + ").map(t).join(" + ")}</td><td>${t(x.consecuente)}</td><td class="num">${G.fmtN(100 * x.confianza)} %</td><td class="num">${G.fmtN(x.lift)}</td></tr>`).join("") + "</table>";
  },

  concentracionP1(el, o = {}) {
    const c = P1("p1_concentracion"), comp = P1("p1_competencia");
    const [t1, g1, t2, g2] = partes(el, "mini", "", "mini", "");
    t1.textContent = "Concentración: % del monto que gana cada tramo de proveedores";
    G.barrasH(g1, c.map((r) => ({ cat: r.tramo, val: r.pct_del_monto })), { orden: "dato", izq: 110, ancho: 600, paso: o.compacto ? 44 : 30, max: 100, fmt: (v) => G.fmtN(v) + " %",
      color: (x, i) => i === 0 ? G.css("--s2") : G.css("--s1") });
    if (o.compacto) { t2.remove(); g2.remove(); return; }
    t2.textContent = "Competencia: % de procesos con un solo postor, por monto";
    G.barrasH(g2, comp.map((r) => ({ cat: r.tramo.replace(/^\d\. /, "").replace("mas", "más"), val: r.pct_postor_unico })), { orden: "dato", izq: 150, ancho: 600, paso: 21, fmt: (v) => G.fmtN(v) + " %",
      color: (x, i) => i === 0 ? G.css("--s2") : G.css("--neutro") });
  },

  // Silueta y SSE por k, la evidencia de la elección de k = 4.
  siluetaK(el, o = {}) {
    const d = T("p2_eleccion_k").filter((r) => r.k <= 10);
    const [t, g] = partes(el, "mini", "");
    t.textContent = "Silueta según k: máxima en 4";
    const r = G.lineas(g, [{ nombre: "silueta", puntos: d.map((x) => ({ x: x.k, y: x.silueta_propia })), color: G.css("--s1") }],
      { ancho: 600, alto: 220, der: 70, dy: [0.2, 0.4], ex: "k", tx: 8 });
    const k4 = d.find((x) => x.k === 4);
    r.g.append("circle").attr("cx", r.x(4)).attr("cy", r.y(k4.silueta_propia)).attr("r", 7).attr("fill", G.css("--s2"));
  },

  // Tabla de los cuatro perfiles con los indicadores que los separan.
  tablaPerfiles(el, o = {}) {
    const d = [...T("p2_perfiles")].sort((a, b) => b.proveedores - a.proveedores);
    el.innerHTML = `<p class="mini">Los cuatro perfiles, indicadores medianos</p><table class="datos"><tr><th>perfil</th><th class="num">proveedores</th><th class="num">entidades</th><th class="num">cuota del cliente principal</th><th class="num">postor único</th></tr>` +
      d.map((r) => `<tr${r.perfil.startsWith("cautivo") ? " style='color:var(--s2);font-weight:700'" : ""}><td>${r.perfil}</td><td class="num">${G.fmtN(r.proveedores)}</td><td class="num">${G.fmtN(r.n_entidades)}</td><td class="num">${G.fmtN(100 * r.cuota_cliente_top)} %</td><td class="num">${G.fmtN(100 * r.pct_postor_unico)} %</td></tr>`).join("") + "</table>";
  },

  // ------------------------------------------------ Parte I
  resolucion(el, o = {}) {
    const d = T("p1_resolucion").map((r) => ({ cat: r.tipo, publicados: r.identificadores, reales: r.proveedores }));
    const [g, l] = partes(el, "", "");
    const filas = d.flatMap((r) => [{ cat: r.cat + " · publicados", val: r.publicados, s: 0 }, { cat: r.cat + " · reales", val: r.reales, s: 1 }]);
    G.barrasH(g, filas, { orden: "dato", izq: 250, color: (x) => x.s ? G.css("--s1") : G.css("--neutro"), paso: o.modo === "presentacion" ? 52 : 22,
      tip: (x) => `${x.cat}: ${G.fmtN(x.val)}` });
    leyenda(l, [[G.css("--neutro"), "identificadores publicados"], [G.css("--s1"), "proveedores reales tras la resolución"]]);
  },

  grafoCriterio(el) {
    const d = T("p1_sensibilidad_grafo");
    const topes = [...new Set(d.map((r) => r.tope))], minimos = [...new Set(d.map((r) => r.minimo))];
    let tope = 50, minimo = 2;
    const [c1, c2, g] = partes(el, "controles", "controles", "");
    c1.insertAdjacentHTML("beforeend", "<span class='control'>Tope de participantes por proceso</span>");
    chips(c1, topes.map((v) => ({ t: String(v), v })), tope, (v) => { tope = v; dibujar(); });
    c2.insertAdjacentHTML("beforeend", "<span class='control'>Mínimo de procesos compartidos</span>");
    chips(c2, minimos.map((v) => ({ t: String(v), v })), minimo, (v) => { minimo = v; dibujar(); });
    function dibujar() {
      const filas = d.map((r) => ({ cat: `tope ${r.tope}, mínimo ${r.minimo}`, val: r.aristas, r }));
      G.barrasH(g, filas, { orden: "dato", izq: 190, dur: 300,
        color: (x) => x.r.tope === tope && x.r.minimo === minimo ? G.css("--s1") : G.css("--neutro"),
        tip: (x) => `${G.fmtN(x.r.aristas)} aristas entre ${G.fmtN(x.r.nodos)} nodos` });
    }
    dibujar();
  },

  // ------------------------------------------------ Parte II
  kmeansVivo(el, o = {}) {
    const pts = T("p2_puntos");
    const X = pts.map((p) => [p.pc1, p.pc2, p.pc3, p.pc4, p.pc5, p.pc6]);
    const elec = Object.fromEntries(T("p2_eleccion_k").map((r) => [r.k, r]));
    // Centroides del notebook con k = 4 y su perfil: cada grupo del navegador se nombra por el más cercano.
    const nombrePerfil = Object.fromEntries(T("p2_perfiles").map((r) => [r.cluster, r.perfil]));
    const ref = T("p2_centroides").filter((r) => r.k === 4)
      .map((r) => ({ perfil: nombrePerfil[r.cluster], c: [r.pc1, r.pc2, r.pc3, r.pc4, r.pc5, r.pc6] }));
    const colorPerfil = (n) => n?.startsWith("cautivo") ? G.css("--s2") : n?.startsWith("gran") ? G.css("--s1") :
      n?.startsWith("competitivo") ? G.css("--s3") : n?.startsWith("contratista") ? G.css("--s4") : G.css("--neutro");
    const [c, info, g, ley] = partes(el, "controles", "lectura", "", "");
    ley.style.marginTop = "6px";
    function dibujar(k) {
      const { etq } = G.kmeans(X, k, 3);
      // Centro de cada grupo en las 6 componentes y el perfil del notebook más cercano.
      const suma = Array.from({ length: k }, () => new Array(6).fill(0)), n = new Array(k).fill(0);
      X.forEach((x, i) => { n[etq[i]]++; x.forEach((v, d) => (suma[etq[i]][d] += v)); });
      const cercano = suma.map((s, q) => {
        const m = s.map((v) => v / Math.max(1, n[q]));
        return ref.reduce((a, r) => { const d = r.c.reduce((t, v, j) => t + (v - m[j]) ** 2, 0); return d < a.d ? { d, perfil: r.perfil } : a; }, { d: Infinity }).perfil;
      });
      const biyectivo = new Set(cercano).size === k && k === ref.length;
      const pal = G.SERIES().concat(["#5FA8D3", "#A0522D", "#2F4858"]);
      const color = cercano.map((pf, q) => biyectivo ? colorPerfil(pf) : pal[q % pal.length]);
      const p = pts.map((q, i) => ({ x: q.pc1, y: q.pc2, grupo: etq[i],
        etiqueta: `${privado(q.nombre)}<br>grupo ${etq[i] + 1}, se parece al perfil ${cercano[etq[i]]}` }));
      G.dispersion(g, p, { ancho: 760, alto: o.modo === "presentacion" ? 450 : 420, r: 2.4, ex: "componente principal 1", ey: "componente principal 2",
        color: (q) => color[q.grupo] });
      const orden = d3.range(k).sort((a, b) => n[b] - n[a]);
      leyenda(ley, orden.map((q) => [color[q], biyectivo ? `${cercano[q]} (${G.fmtN(100 * n[q] / X.length)} %)`
        : `grupo ${q + 1}: se parece a ${cercano[q]} (${G.fmtN(100 * n[q] / X.length)} %)`]));
      const e = elec[k];
      info.innerHTML = e ? `Con k = <b>${k}</b>: silueta de <b>${G.fmtN(e.silueta_propia, 3)}</b> y SSE de ${G.fmtC(e.sse_propio)} sobre los 12 mil proveedores recurrentes. ${k === 4 ? "Es el k elegido: la silueta máxima, y cada color es uno de los cuatro perfiles." : k === 5 ? "El codo del SSE sugería 5, pero la silueta cae." : "Cada grupo se nombra por el perfil de k = 4 al que más se parece."}` : "";
    }
    control(c, "número de grupos k", 2, 8, 1, 4, dibujar).disparar();
  },

  perfiles(el, o = {}) {
    const d = T("p2_perfiles");
    const [g, l] = partes(el, "", "");
    const filas = d.flatMap((r) => [{ cat: r.perfil + " · proveedores", val: r.pct_proveedores, s: 0, r }, { cat: r.perfil + " · monto", val: r.pct_monto, s: 1, r }]);
    G.barrasH(g, filas, { orden: "dato", izq: 290, paso: o.modo === "presentacion" ? 50 : 22, fmt: (v) => G.fmtN(v, 1) + " %",
      color: (x) => x.r.perfil.startsWith("cautivo") ? (x.s ? G.css("--s2") : "#E9A3AD") : (x.s ? G.css("--s1") : G.css("--neutro")),
      tip: (x) => `${x.r.perfil}: ${G.fmtN(x.r.proveedores)} proveedores, postor único ${G.fmtN(100 * x.r.pct_postor_unico)} %, sin concurso ${G.fmtN(100 * x.r.pct_sin_concurso)} %` });
    leyenda(l, [[G.css("--neutro"), "% de los proveedores"], [G.css("--s1"), "% del monto"], [G.css("--s2"), "perfil cautivo"]]);
  },

  dbscanVivo(el, o = {}) {
    const pts = T("p2_puntos");
    const X = pts.map((p) => [p.pc1, p.pc2, p.pc3, p.pc4, p.pc5, p.pc6]);
    let eps = 1.31, minPts = 12;
    const [c, info, g] = partes(el, "controles", "lectura", "");
    function dibujar() {
      const etq = G.dbscan(X, eps, minPts);
      const ruido = etq.filter((e) => e === -1).length, k = new Set(etq.filter((e) => e >= 0)).size;
      const p = pts.map((q, i) => ({ x: q.pc1, y: q.pc2, grupo: etq[i], etiqueta: privado(q.nombre) + (etq[i] < 0 ? "<br>ruido" : "") }));
      G.dispersion(g, p, { ancho: 760, alto: o.modo === "presentacion" ? 450 : 400, r: 2.4, ex: "componente principal 1", ey: "componente principal 2",
        color: (q) => q.grupo < 0 ? G.css("--s2") : G.css("--neutro"), op: .8 });
      info.innerHTML = `Con eps = <b>${G.fmtN(eps, 2)}</b> y min_pts = <b>${minPts}</b>, DBSCAN marca <b>${G.fmtN(100 * ruido / pts.length, 1)} %</b> de la muestra como ruido (en rojo) y deja ${k} región${k === 1 ? "" : "es"} densa${k === 1 ? "" : "s"}. El ruido no es error: es el proveedor que no se parece a ningún vecindario, y de ahí sale la cola de anomalías.`;
    }
    control(c, "eps", 0.8, 2.2, 0.01, eps, (v) => { eps = v; dibujar(); }, (v) => G.fmtN(v, 2));
    control(c, "min_pts", 4, 30, 1, minPts, (v) => { minPts = v; dibujar(); });
    c.querySelectorAll("input").forEach((i) => i.dispatchEvent(new Event("input")));
  },

  anomalias(el) {
    const s = T("p2_sensibilidad_anomalias");
    const factores = [...new Set(s.map((r) => r.factor_eps))], cuantiles = [...new Set(s.map((r) => r.cuantil))];
    let f = 1, q = 0.95;
    const [c1, c2, info, g] = partes(el, "controles", "controles", "lectura", "");
    c1.insertAdjacentHTML("beforeend", "<span class='control'>eps relativo al elegido</span>");
    chips(c1, factores.map((v) => ({ t: "× " + G.fmtN(v, 1), v })), f, (v) => { f = v; dibujar(); });
    c2.insertAdjacentHTML("beforeend", "<span class='control'>cuantil de distancia al centroide</span>");
    chips(c2, cuantiles.map((v) => ({ t: G.fmtN(v, 3), v })), q, (v) => { q = v; dibujar(); });
    const tipo = Object.fromEntries(T("p2_anomalias_tipo").map((r) => [r.tipo_anomalia, r]));
    function dibujar() {
      const r = s.find((x) => x.factor_eps === f && x.cuantil === q);
      G.barrasH(g, [{ cat: "anomalías en total", val: r.anomalias }, { cat: "por competencia o dependencia", val: r.competencia }, { cat: "de las 77 adoptadas que siguen", val: r.adoptadas_que_siguen }],
        { orden: "dato", izq: 250, dur: 300, max: 480, color: (x, i) => i === 1 ? G.css("--s2") : G.css("--neutro") });
      info.innerHTML = `La cola útil para control es la de <b>competencia o dependencia</b>: con los parámetros elegidos son ${tipo["competencia o dependencia"]?.proveedores} proveedores, ganan sin otro postor el ${G.fmtN(100 * tipo["competencia o dependencia"]?.postor_unico)} % de las veces y suman ${G.fmtC(tipo["competencia o dependencia"]?.monto)} soles. Mover los parámetros cambia el largo de la cola, entre ${d3.min(s, (x) => x.competencia)} y ${d3.max(s, (x) => x.competencia)}: es una decisión de capacidad de revisión, no del algoritmo.`;
    }
    dibujar();
  },

  // ------------------------------------------------ Parte III
  recomendacion(el, o = {}) {
    const r = T("p3_resultados");
    const curva = T("p3_curva_k");
    const [g, c, info, g2] = partes(el, "", "controles", "lectura", "");
    G.barrasH(g, r.map((x) => ({ cat: x.metodo, val: x.ndcg, x })), { izq: 260, fmt: (v) => G.fmtN(v, 3),
      color: (x) => x.cat.startsWith("híbrido") ? G.css("--s1") : G.css("--neutro"),
      tip: (x) => `${x.cat}<br>precisión@10 ${G.fmtN(x.x.precision, 3)} · recall@10 ${G.fmtN(x.x.recall, 3)}` });
    function dibujar(k) {
      const filas = curva.filter((x) => x.k === k).map((x) => ({ cat: x.metodo, val: 100 * x.recall }));
      G.barrasH(g2, filas, { izq: 260, dur: 300, fmt: (v) => G.fmtN(v, 1) + " %", max: 100 * d3.max(curva, (x) => x.recall) * 1.05,
        color: (x) => x.cat.startsWith("híbrido") ? G.css("--s1") : G.css("--neutro") });
      const h = curva.find((x) => x.k === k && x.metodo.startsWith("híbrido"));
      info.innerHTML = `Con listas de <b>${k}</b> proveedores, el híbrido recupera el <b>${G.fmtN(100 * h.recall, 1)} %</b> de las relaciones nuevas de 2025 de cada entidad. Arriba, el NDCG en 10 de cada método; abajo, el recall según el largo de la lista.`;
    }
    control(c, "largo de la lista", 1, 10, 1, 10, (v) => dibujar([1, 3, 5, 10].reduce((a, b) => Math.abs(b - v) < Math.abs(a - v) ? b : a))).disparar();
  },

  sorpresa(el, o = {}) {
    const s = T("p3_sorpresa"), p = Object.fromEntries(T("p3_prueba_sorpresa").map((r) => [r.variable, r]));
    const [g, info] = partes(el, "", "lectura");
    G.barrasH(g, s.map((r) => ({ cat: "percentil " + r.tramo, val: r.pct_postor_unico, r })), { orden: "dato", izq: 200, ancho: o.compacto ? 600 : 760, paso: o.compacto ? 30 : 26, fmt: (v) => G.fmtN(v, 1) + " %",
      color: (x, i) => i === 0 ? G.css("--s2") : G.css("--neutro"), tip: (x) => `${G.fmtN(x.r.relaciones)} relaciones; sin concurso ${G.fmtN(x.r.pct_sin_concurso, 1)} %` });
    if (o.compacto) { info.remove(); return; }
    info.innerHTML = `Porcentaje con postor único según qué tan esperable era la relación para el modelo. Las improbables (en rojo) tienen ${G.fmtN(p.postor_unico?.improbables_pct, 1)} % frente a ${G.fmtN(p.postor_unico?.esperadas_pct, 1)} % de las esperadas, una diferencia que no es significativa (p = ${G.fmtN(p.postor_unico?.p_valor, 2)}). <b>Resultado negativo, y se reporta así</b>: lo inesperado no es por sí solo menos competitivo.`;
  },

  // ------------------------------------------------ Parte IV
  pagerankVivo(el, o = {}) {
    const nodos = T("p4_subgrafo_nodos"), aristas = T("p4_subgrafo_aristas"), sens = T("p4_sensibilidad_beta");
    const n = nodos.length, E = aristas.map((a) => ({ s: a.i, d: a.j, w: a.peso }));
    const pres = o.modo === "presentacion";
    const [c, cuerpo] = partes(el, "controles", "");
    cuerpo.style.cssText = "display:grid;grid-template-columns:1.25fr .9fr;gap:22px;align-items:start";
    const [gEl, lado] = partes(cuerpo, "", "");
    const W = 640, H = pres ? 450 : 460;
    const color = (p) => p?.startsWith("gran") ? G.css("--s1") : p?.startsWith("cautivo") ? G.css("--s2") :
      p?.startsWith("competitivo") ? G.css("--s3") : p?.startsWith("contratista") ? G.css("--s4") : G.css("--neutro");
    const sim = nodos.map((d) => ({ ...d }));
    const links = aristas.filter((a) => a.i !== a.j).map((a) => ({ source: a.i, target: a.j, w: a.peso }));
    d3.forceSimulation(sim).force("link", d3.forceLink(links).distance(70).strength(0.02))
      .force("charge", d3.forceManyBody().strength(-38)).force("x", d3.forceX(W / 2).strength(.06))
      .force("y", d3.forceY(H / 2).strength(.08)).force("col", d3.forceCollide(7)).stop().tick(320);
    const { g } = G.lienzo(gEl, W, H, { t: 6, r: 6, b: 6, l: 6 });
    const ext = [d3.extent(sim, (d) => d.x), d3.extent(sim, (d) => d.y)];
    const sx = d3.scaleLinear(ext[0], [12, W - 24]), sy = d3.scaleLinear(ext[1], [12, H - 24]);
    g.append("g").selectAll("line").data(links).join("line").attr("x1", (l) => sx(l.source.x)).attr("y1", (l) => sy(l.source.y))
      .attr("x2", (l) => sx(l.target.x)).attr("y2", (l) => sy(l.target.y)).attr("stroke", G.css("--linea")).attr("stroke-opacity", .55);
    const t = G.tooltip();
    const nodosG = g.append("g").selectAll("circle").data(sim).join("circle").attr("cx", (d) => sx(d.x)).attr("cy", (d) => sy(d.y))
      .attr("fill", (d) => color(d.perfil)).attr("stroke", G.css("--fondo")).attr("stroke-width", 1).attr("r", 3);
    leyenda(lado.appendChild(document.createElement("div")), [[G.css("--s1"), "gran recurrente"], [G.css("--s3"), "competitivo"],
      [G.css("--s4"), "contratista de obra"], [G.css("--s2"), "cautivo"], [G.css("--neutro"), "sin perfil"]]);
    const lista = lado.appendChild(document.createElement("div"));
    const info = lado.appendChild(document.createElement("p")); info.className = "lectura";
    let base = null;
    function dibujar(beta) {
      const { r, it } = G.pagerank(n, E, beta);
      const orden = d3.range(n).sort((a, b) => r[b] - r[a]);
      if (!base) base = orden.slice(0, 10);
      const rmax = d3.max(r);
      nodosG.on("mousemove", (ev, d) => t.show(ev, `<b>${privado(d.nombre, d.tipo)}</b><br>${d.perfil}<br>${G.fmtN(d.victorias_disputadas)} victorias en procesos disputados<br>puesto ${orden.indexOf(d.i) + 1} de ${n} con beta ${beta.toFixed(2)}`))
        .on("mouseleave", () => t.hide())
        .transition().duration(450).attr("r", (d) => 3 + 22 * Math.sqrt(r[d.i] / rmax));
      lista.innerHTML = `<table class="datos" style="margin-top:10px"><tr><th>#</th><th>proveedor</th><th class="num">rango ×N</th></tr>` +
        orden.slice(0, pres ? 7 : 8).map((k, q) => `<tr><td>${q + 1}${base.includes(k) ? "" : " <b style='color:var(--s2)'>nuevo</b>"}</td><td>${G.corto(privado(nodos[k].nombre, nodos[k].tipo), pres ? 30 : 34)}</td><td class="num">${G.fmtN(r[k] * n, 1)}</td></tr>`).join("") + "</table>";
      const cerca = sens.reduce((a, b) => Math.abs(b.beta - beta) < Math.abs(a.beta - beta) ? b : a);
      info.innerHTML = `Con beta = <b>${G.fmtN(beta, 2)}</b> la caminata sigue una arista con esa probabilidad y salta al azar con ${G.fmtN(1 - beta, 2)}. Converge en <b>${it}</b> iteraciones. En el grafo completo de ${G.fmtN(DATOS.p2.p4_resumen?.[0]?.nodos_g3)} proveedores, beta ${G.fmtN(cerca.beta, 2)} conserva el <b>${G.fmtN(cerca.top100_comun_pct)} %</b> del top 100 de beta 0,85.`;
    }
    control(c, "factor de amortiguamiento beta", 0.5, 0.99, 0.01, 0.85, dibujar, (v) => G.fmtN(v, 2)).disparar();
  },

  pagerankVsVictorias(el, o = {}) {
    const d = T("p4_pagerank_top").filter((r) => r.puesto_victorias > 0);
    const [g, l] = partes(el, "", "");
    const { g: gg, w, h } = G.lienzo(g, 760, o.modo === "presentacion" ? 560 : 400, { t: 10, r: 16, b: 44, l: 60 });
    const x = d3.scaleLog([d3.max(d, (r) => r.puesto_victorias) * 1.1, 1], [0, w]), y = d3.scaleLog([300, 1], [h, 0]);
    gg.append("g").attr("class", "eje").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(6, "~s"));
    gg.append("g").attr("class", "eje").call(d3.axisLeft(y).ticks(5, "~s"));
    gg.append("text").attr("class", "tenue").attr("x", w).attr("y", h + 38).attr("text-anchor", "end").text("puesto por victorias en procesos disputados →  mejor");
    gg.append("text").attr("class", "tenue").attr("x", 0).attr("y", -2).text("puesto por PageRank");
    gg.append("line").attr("x1", x(100)).attr("x2", x(100)).attr("y1", 0).attr("y2", h).attr("stroke", G.css("--linea")).attr("stroke-dasharray", "4 4");
    const t = G.tooltip();
    gg.selectAll("circle").data(d).join("circle").attr("cx", (r) => x(r.puesto_victorias)).attr("cy", (r) => y(r.puesto_pagerank))
      .attr("r", 0).attr("fill", (r) => r.puesto_victorias > 100 && r.puesto_pagerank <= 100 ? G.css("--s2") : G.css("--s1")).attr("fill-opacity", .75)
      .on("mousemove", (ev, r) => t.show(ev, `<b>${privado(r.nombre, r.tipo)}</b><br>puesto ${r.puesto_pagerank} por PageRank, ${r.puesto_victorias} por victorias<br>${G.fmtN(r.victorias_disputadas)} victorias disputadas, ${G.fmtN(r.rivales_vencidos)} rivales vencidos`))
      .on("mouseleave", () => t.hide()).transition().duration(600).delay((_, i) => i * 2).attr("r", 4);
    leyenda(l, [[G.css("--s2"), "top 100 por PageRank, fuera del top 100 por victorias"], [G.css("--s1"), "resto de los 300 primeros"]]);
  },

  perfilPagerank(el, o = {}) {
    const d = T("p4_pagerank_perfil");
    G.barrasH(el, d.map((r) => ({ cat: r.perfil, val: r.percentil_mediano, r })), { izq: 270, ancho: o.compacto ? 640 : 760, corte: o.compacto ? 30 : 36, fmt: (v) => "percentil " + G.fmtN(v),
      max: 100, color: (x) => x.cat.startsWith("cautivo") ? G.css("--s2") : G.css("--s1"),
      tip: (x) => `${G.fmtN(x.r.proveedores)} proveedores en procesos disputados; ${G.fmtN(x.r.en_top_1pct, 1)} % en el 1 % superior` });
  },

  hits(el, o = {}) {
    const hubs = T("p4_hits_hubs").slice(0, 8), aut = T("p4_hits_authorities").slice(0, 8);
    const [a, b] = partes(el, "", "");
    el.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:24px";
    a.insertAdjacentHTML("beforeend", "<p class='lectura'><b>Hubs</b>: entidades que contratan a proveedores de referencia</p>");
    b.insertAdjacentHTML("beforeend", "<p class='lectura'><b>Authorities</b>: proveedores contratados por buenos hubs</p>");
    const ga = a.appendChild(document.createElement("div")), gb = b.appendChild(document.createElement("div"));
    G.barrasH(ga, hubs.map((r) => ({ cat: r.comprador_nombre, val: r.hub, r })), { izq: 250, corte: 30, ancho: 560, fmt: (v) => G.fmtN(v, 2),
      tip: (x) => `${x.r.comprador_nombre}<br>${x.r.departamento}, ${G.fmtN(x.r.n_proveedores)} proveedores` });
    G.barrasH(gb, aut.map((r) => ({ cat: privado(r.nombre, r.tipo), val: r.authority, r })), { izq: 250, corte: 30, ancho: 560, fmt: (v) => G.fmtN(v, 2),
      color: G.css("--s3"), tip: (x) => `${privado(x.r.nombre, x.r.tipo)}<br>${G.fmtN(x.r.clientes)} entidades clientes, ${G.fmtC(x.r.monto)} soles` });
  },

  mercados(el, o = {}) {
    const m = T("p4_mercados_svd");
    const [c, cuerpo] = partes(el, "controles", "");
    cuerpo.style.cssText = "display:grid;grid-template-columns:1fr 1.1fr;gap:24px;align-items:start";
    const [gEl, ficha] = partes(cuerpo, "", "");
    let sel = 1;
    function dibujar() {
      G.barrasH(gEl, m.map((r) => ({ cat: `vector ${r.vector}`, val: r.valor_singular, r })), { orden: "dato", izq: 90, ancho: 480, dur: 300, paso: o.modo === "presentacion" ? 38 : 26,
        fmt: (v) => G.fmtN(v, 1), color: (x) => x.r.vector === sel ? G.css("--s1") : G.css("--neutro") });
      const r = m.find((x) => x.vector === sel);
      ficha.innerHTML = `<div class="cifras"><div class="cifra"><div class="n">${r.pct_familia} %</div><div class="t">de sus 30 proveedores principales en la familia ${r.familia}</div></div>
        <div class="cifra"><div class="n">${r.pct_departamento} %</div><div class="t">en ${r.departamento.toLowerCase()}</div></div></div>
        <p class="lectura"><b>Ítem típico:</b> ${r.item_tipico.toLowerCase()}</p>
        <p class="lectura"><b>Proveedores con más peso:</b> ${r.proveedores.split(" | ").map((n) => privado(n)).join(" | ")}</p>
        <p class="lectura"><b>Entidades con más peso:</b> ${r.entidades}</p>`;
    }
    chips(c, m.map((r) => ({ t: `v${r.vector}: ${G.corto(r.item_tipico.toLowerCase(), 18)}`, v: r.vector })), sel, (v) => { sel = v; dibujar(); });
    dibujar();
  },

  pares(el, o = {}) {
    const p = T("p4_patrones_pares"), top = T("p4_pares_alternan_top");
    const [g, tabla] = partes(el, "", "tabla-scroll");
    const claves = ["pierden juntos", "siempre gana el mismo", "alternan"];
    G.apiladas(g, [{ nombre: "pares afines", partes: Object.fromEntries(p.map((r) => [r.patron, r.afines])) },
                   { nombre: "control", partes: Object.fromEntries(p.map((r) => [r.patron, r.control])) }], claves,
      { colores: [G.css("--neutro"), G.css("--s1"), G.css("--s2")], primeroClaro: true, alto: o.modo === "presentacion" ? 160 : 180 });
    tabla.innerHTML = `<table class="datos"><tr><th>proveedor A</th><th>proveedor B</th><th class="num">procesos juntos</th><th class="num">gana A</th><th class="num">gana B</th></tr>` +
      top.slice(0, o.modo === "presentacion" ? 5 : 8).map((r) => `<tr><td>${G.corto(privado(r.proveedor_a), 38)}</td><td>${G.corto(privado(r.proveedor_b), 38)}</td><td class="num">${G.fmtN(r.compartidos)}</td><td class="num">${r.gana_a}</td><td class="num">${r.gana_b}</td></tr>`).join("") + "</table>";
  },

  // ------------------------------------------------ Parte V
  girvanNewman(el, o = {}) {
    const nodos = T("p5_gn_nodos"), aristas = T("p5_gn_aristas"), curva = T("p5_gn_curva");
    const res = T("p5_resumen")[0] || {};
    const niveles = Object.keys(nodos[0] || {}).filter((k) => /^k\d+$/.test(k)).map((k) => +k.slice(1)).sort((a, b) => a - b);
    const pres = o.modo === "presentacion";
    const [c, cuerpo] = partes(el, "controles", "");
    cuerpo.style.cssText = "display:grid;grid-template-columns:1.3fr 1fr;gap:20px;align-items:start";
    const [gEl, lado] = partes(cuerpo, "", "");
    const W = 600, H = pres ? 470 : 430;
    const sim = nodos.map((d, i) => ({ ...d, i }));
    const links = aristas.map((a) => ({ source: a.i, target: a.j, w: a.peso }));
    d3.forceSimulation(sim).force("link", d3.forceLink(links).distance(30).strength((l) => Math.min(1, l.w * 2)))
      .force("charge", d3.forceManyBody().strength(-30)).force("x", d3.forceX(W / 2).strength(.07))
      .force("y", d3.forceY(H / 2).strength(.09)).stop().tick(300);
    const { g } = G.lienzo(gEl, W, H, { t: 6, r: 6, b: 6, l: 6 });
    const sx = d3.scaleLinear(d3.extent(sim, (d) => d.x), [10, W - 22]), sy = d3.scaleLinear(d3.extent(sim, (d) => d.y), [10, H - 22]);
    const lineas = g.append("g").selectAll("line").data(links).join("line").attr("x1", (l) => sx(l.source.x)).attr("y1", (l) => sy(l.source.y))
      .attr("x2", (l) => sx(l.target.x)).attr("y2", (l) => sy(l.target.y)).attr("stroke-width", .6);
    const t = G.tooltip();
    const pal = [G.css("--s1"), G.css("--s2"), G.css("--s3"), G.css("--s4"), G.css("--s5"), "#5FA8D3", "#A0522D", "#2F4858", "#C47AC0", "#7A9E3B"];
    const circ = g.append("g").selectAll("circle").data(sim).join("circle").attr("cx", (d) => sx(d.x)).attr("cy", (d) => sy(d.y))
      .attr("r", 5.5).attr("stroke", G.css("--fondo")).attr("stroke-width", 1);
    const graf = lado.appendChild(document.createElement("div"));
    const info = lado.appendChild(document.createElement("p")); info.className = "lectura";
    function dibujar(v) {
      const k = niveles.reduce((a, b) => Math.abs(b - v) < Math.abs(a - v) ? b : a);
      const etq = sim.map((d) => d["k" + k]);
      const tam = d3.rollup(etq, (x) => x.length, (x) => x);
      const grandes = [...tam].sort((a, b) => b[1] - a[1]).slice(0, 10).map((x) => x[0]);
      const col = (e) => grandes.includes(e) ? pal[grandes.indexOf(e)] : G.css("--neutro");
      circ.on("mousemove", (ev, d) => t.show(ev, `<b>${privado(d.nombre, d.tipo)}</b><br>${d.tipo}<br>${(d.item_tipico || "").toLowerCase()}<br>comunidad de ${tam.get(d["k" + k])} proveedores`))
        .on("mouseleave", () => t.hide()).transition().duration(400).attr("fill", (d) => col(d["k" + k]));
      lineas.transition().duration(400).attr("stroke", (l) => l.source["k" + k] === l.target["k" + k] ? G.css("--tinta3") : G.css("--linea"))
        .attr("stroke-opacity", (l) => l.source["k" + k] === l.target["k" + k] ? .35 : .5);
      const q = curva.find((r) => r.k === k);
      const r = G.lineas(graf, [{ nombre: "Q", puntos: curva.filter((r) => r.k <= 30).map((r) => ({ x: r.k, y: r.Q })), color: G.css("--s1"), marcas: false }],
        { ancho: 460, alto: pres ? 190 : 230, der: 30, ex: "comunidades", ey: "modularidad Q", dy: [0, .45] });
      r.g.append("circle").attr("cx", r.x(k)).attr("cy", r.y(q.Q)).attr("r", 6).attr("fill", G.css("--s2"));
      info.innerHTML = `Con <b>${k}</b> comunidades, Q = <b>${G.fmtN(q.Q, 3)}</b>, tras cortar ${G.fmtN(q.cortes)} aristas puente. ${k === res.k_girvan_newman ? "Es el codo de la curva: la partición adoptada." : ""} Las aristas oscuras quedan dentro de una comunidad y las claras cruzan entre comunidades.`;
    }
    if (pres) MODULOS.tablaMetodosV(lado.appendChild(document.createElement("div")), { compacto: true });
    control(c, "número de comunidades", niveles[0], niveles[niveles.length - 1], 1, res.k_girvan_newman || 5, dibujar).disparar();
  },

  // Los métodos de comunidades lado a lado: grafo, comunidades, Q y tiempo medido.
  tablaMetodosV(el, o = {}) {
    const r = T("p5_resumen")[0] || {}, e = T("p5_escalabilidad");
    const seg = (m) => { const x = e.find((z) => z.metodo === m); return x ? G.fmtN(x.segundos, x.segundos < 1 ? 2 : 0) + " s" : ""; };
    const filas = [["Girvan-Newman", "núcleo, 143", r.k_girvan_newman, r.q_girvan_newman, "4 min"],
      ["espectral", "Ayacucho, " + G.fmtN(r.proveedores_ayacucho), r.k_espectral, r.q_espectral, seg("espectral")],
      ["Louvain", "Ayacucho, " + G.fmtN(r.proveedores_ayacucho), r.k_louvain, r.q_louvain, seg("Louvain")],
      ["propagación, Spark", "nacional, 70.383", r.comunidades_lpa, r.q_lpa, seg("propagación de etiquetas, Spark")],
      ["Louvain", "nacional, 70.383", r.comunidades_louvain_nacional, r.q_louvain_nacional, seg("Louvain nacional, local")]];
    el.innerHTML = `<p class="mini" style="margin-top:14px">Cada método en su escala</p><table class="datos"><tr><th>método</th><th>grafo</th><th class="num">comunidades</th><th class="num">Q</th><th class="num">tiempo</th></tr>` +
      filas.map((f) => `<tr><td>${f[0]}</td><td>${f[1]}</td><td class="num">${G.fmtN(f[2])}</td><td class="num">${G.fmtN(f[3], 2)}</td><td class="num">${f[4]}</td></tr>`).join("") + "</table>";
  },

  escalabilidad(el, o = {}) {
    const e = T("p5_escalabilidad"), res = T("p5_resumen")[0] || {};
    const [g0, ley] = partes(el, "", "");
    const { svg, g, w, h } = G.lienzo(g0, 760, o.modo === "presentacion" ? 480 : 360, { t: 14, r: 20, b: 44, l: 96 });
    const x = d3.scaleLog([30, 1e5], [0, w]), y = d3.scaleLog([0.01, 1e14], [h, 0]);
    const marcas = { 0.01: "0,01 s", 1: "1 s", 60: "1 minuto", 3600: "1 hora", 86400: "1 día", 3.15e7: "1 año", 3.15e10: "mil años", 3.15e13: "un millón de años" };
    g.append("g").attr("class", "rejilla").call(d3.axisLeft(y).tickValues(Object.keys(marcas).map(Number)).tickSize(-w).tickFormat(""));
    g.append("g").attr("class", "eje").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(5, "~s"));
    g.append("g").attr("class", "eje").call(d3.axisLeft(y).tickValues(Object.keys(marcas).map(Number)).tickFormat((v) => marcas[v]));
    g.append("text").attr("class", "tenue").attr("x", w).attr("y", h + 38).attr("text-anchor", "end").text("proveedores en el grafo");
    const id = "recorte" + Math.random().toString(36).slice(2);
    svg.append("clipPath").attr("id", id).append("rect").attr("x", 0).attr("y", 0).attr("width", w).attr("height", h);
    const gn = e.filter((r) => r.metodo === "Girvan-Newman");
    // Misma recta que el notebook: mínimos cuadrados de log(segundos) contra log(nodos).
    const lx = gn.map((r) => Math.log(r.nodos)), ly = gn.map((r) => Math.log(r.segundos));
    const mx = d3.mean(lx), my = d3.mean(ly);
    const b = d3.sum(lx, (v, i) => (v - mx) * (ly[i] - my)) / d3.sum(lx, (v) => (v - mx) ** 2), a0 = my - b * mx;
    const en = (n) => Math.exp(a0 + b * Math.log(n));
    const ext = d3.range(30, 1e5, 150).map((n) => ({ n, s: en(n) }));
    g.append("path").datum(ext).attr("clip-path", `url(#${id})`).attr("fill", "none").attr("stroke", G.css("--s2")).attr("stroke-width", 2)
      .attr("stroke-dasharray", "6 5").attr("d", d3.line().x((p) => x(p.n)).y((p) => y(p.s)));
    g.selectAll("circle.gn").data(gn).join("circle").attr("class", "gn").attr("cx", (r) => x(r.nodos)).attr("cy", (r) => y(r.segundos)).attr("r", 5).attr("fill", G.css("--s2"));
    const nac = e.find((r) => r.metodo.startsWith("propagación"));
    if (nac) {
      const anios = en(nac.nodos) / 3.15e7;
      g.append("circle").attr("cx", x(nac.nodos)).attr("cy", y(en(nac.nodos))).attr("r", 6).attr("fill", "none").attr("stroke", G.css("--s2")).attr("stroke-width", 2);
      g.append("text").attr("x", x(nac.nodos) - 10).attr("y", y(en(nac.nodos)) + 4).attr("text-anchor", "end").style("fill", G.css("--s2")).style("font-weight", 700)
        .text(`Girvan-Newman nacional: unos ${anios >= 1e6 ? G.fmtN(anios / 1e6, 1) + " millones de" : G.fmtN(anios / 1000) + " mil"} años`);
    }
    const otros = e.filter((r) => r.metodo !== "Girvan-Newman");
    const cols = [G.css("--s1"), G.css("--s3"), G.css("--s4"), G.css("--s5"), "#1D4A7C"];
    otros.forEach((r, i) => g.append("rect").attr("x", x(r.nodos) - 6 + i * 3).attr("y", y(Math.max(r.segundos, 0.012)) - 6).attr("width", 12).attr("height", 12).attr("fill", cols[i % 5]));
    leyenda(ley, [[G.css("--s2"), `Girvan-Newman medido y extrapolado (n elevado a ${G.fmtN(b, 1)})`]].concat(
      otros.map((r, i) => [cols[i % 5], `${r.metodo}: ${G.fmtN(r.segundos, r.segundos < 1 ? 2 : 0)} s`])));
  },

  acuerdo(el, o = {}) {
    const clave = ["Girvan-Newman frente a espectral, núcleo", "Girvan-Newman frente a Louvain, núcleo", "Louvain frente a familia CUBSO",
      "Louvain frente a perfil de la Parte II", "Louvain nacional frente a familia CUBSO", "Louvain nacional frente a departamento", "propagación frente a Louvain, nacional"];
    const d = o.compacto ? clave.map((c) => T("p5_acuerdo").find((r) => r.comparacion === c)).filter(Boolean) : T("p5_acuerdo");
    const color = (v) => d3.interpolateRgb(G.css("--panel"), G.css("--s1"))(Math.max(0, Math.min(1, v)));
    el.innerHTML = `<div class="tabla-scroll"><table class="datos"><tr><th>comparación</th><th class="num">ARI</th><th class="num">NMI</th></tr>` +
      d.map((r) => `<tr><td>${r.comparacion}</td>` + ["ARI", "NMI"].map((m) => `<td class="num" style="background:${color(r[m])};color:${r[m] > .55 ? "#fff" : "inherit"};font-weight:600">${G.fmtN(r[m], 2)}</td>`).join("") + "</tr>").join("") + "</table></div>";
  },

  comunidadesNacionales(el) {
    const d = T("p5_comunidades_nacionales");
    G.barrasH(el, d.map((r, i) => ({ cat: G.corto(r.item_tipico.toLowerCase(), 40), val: r.proveedores, r })), { orden: "dato", izq: 300, corte: 40,
      color: (x) => x.r.pct_departamento >= 50 ? G.css("--s4") : G.css("--s1"),
      tip: (x) => `${G.fmtN(x.r.proveedores)} proveedores; ${x.r.pct_familia} % en su familia principal; ${x.r.pct_departamento} % en ${x.r.departamento}; ganaron ${G.fmtC(x.r.monto_ganado)} soles` });
  },

  comunidadesAyacucho(el, o = {}) {
    const d = T("p5_comunidades_ayacucho"), res = T("p5_resumen")[0] || {};
    const [cif, g] = partes(el, "cifras", "");
    cif.innerHTML = `<div class="cifra"><div class="n">${G.fmtN(res.pct_afines_misma_comunidad)} %</div><div class="t">de los pares afines de Ayacucho cae dentro de una misma comunidad</div></div>
      <div class="cifra"><div class="n">${G.fmtN(res.pct_esperado)} %</div><div class="t">es lo que se esperaría si fueran dos proveedores al azar</div></div>
      <div class="cifra"><div class="n">${G.fmtN(res.pct_puente)} %</div><div class="t">de los proveedores compite en dos o más mercados (BigCLAM)</div></div>`;
    G.barrasH(g, d.map((r, i) => ({ cat: `${i + 1}. ${G.corto(r.item_tipico.toLowerCase(), 30)} · ${r.proveedores} prov.`, val: r.pares_afines, r })), { orden: "dato", izq: 360, corte: 50, paso: o.modo === "presentacion" ? 38 : 26,
      color: (x) => x.r.pares_que_alternan > 0 ? G.css("--s2") : G.css("--s1"), fmt: (v) => G.fmtN(v) + " pares",
      tip: (x) => `${x.r.proveedores} proveedores, ganaron ${G.fmtC(x.r.monto_ganado)} soles<br>${x.r.pares_afines} pares afines, ${x.r.pares_que_alternan} alternan victorias` });
  },

  bigclam(el, o = {}) {
    const d = T("p5_bigclam_solapamiento");
    const claves = ["ninguna", "una", "dos", "tres o más"].filter((k) => d[0] && k in d[0]);
    G.apiladas(el, d.map((r) => ({ nombre: r.tipo, partes: Object.fromEntries(claves.map((k) => [k, r[k]])) })), claves,
      { izq: 140, colores: [G.css("--neutro"), "#9DC6E0", G.css("--s1"), G.css("--s2")], primeroClaro: true });
  },

  // ------------------------------------------------ Parte VI
  tsneVivo(el, o = {}) {
    const d = T("p6_tsne");
    const claves = Object.keys(d[0] || {}).filter((k) => k.endsWith("_x")).map((k) => k.slice(0, -2));
    const nombre = (k) => k === "svd" ? "SVD" : k.startsWith("gnn") ? k.replace("gnn_", "") : "Node2Vec p " + k.split("_")[1] + ", q " + k.split("_")[2];
    let emb = claves.includes("n2v_1_0.5") ? "n2v_1_0.5" : claves[0], colorPor = "rubro";
    const [c1, c2, info, g] = partes(el, "controles", "controles", "lectura", "");
    if (o.lateral) { o.lateral.prepend(c1, c2, info); info.style.fontSize = "18px"; }
    const visibles = o.lateral ? claves.filter((k) => k === "svd" || k === "n2v_1_0.5" || k.startsWith("gnn")) : claves;
    c1.insertAdjacentHTML("beforeend", "<span class='control'>embedding</span>");
    chips(c1, visibles.map((k) => ({ t: nombre(k), v: k })), emb, (v) => { emb = v; dibujar(); });
    c2.insertAdjacentHTML("beforeend", "<span class='control'>colorear por</span>");
    chips(c2, [{ t: "rubro", v: "rubro" }, { t: "perfil de la Parte II", v: "perfil" }, { t: "departamento", v: "region" }], colorPor, (v) => { colorPor = v; dibujar(); });
    function dibujar() {
      const cats = [...d3.rollup(d, (x) => x.length, (r) => r[colorPor])].sort((a, b) => b[1] - a[1]).map((x) => x[0]);
      const top = cats.filter((x) => x !== "otros" && x !== "sin perfil").slice(0, 6);
      const pal = G.SERIES().concat(["#5FA8D3"]);
      const col = (r) => top.includes(r[colorPor]) ? pal[top.indexOf(r[colorPor])] : G.css("--neutro");
      const p = d.map((r) => ({ x: r[emb + "_x"], y: r[emb + "_y"], r, etiqueta: `<b>${privado(r.nombre)}</b><br>${r.rubro || ""}<br>${r.perfil}<br>${r.region}` }));
      G.dispersion(g, p, { ancho: 760, alto: o.lateral ? 590 : o.modo === "presentacion" ? 470 : 430, r: o.lateral ? 2.8 : 2.3, ejes: false, color: (q) => col(q.r), op: .8 });
      info.innerHTML = top.map((t, i) => `<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px"><i style="width:10px;height:10px;border-radius:50%;background:${pal[i]};display:inline-block"></i>${G.corto(String(t).toLowerCase(), 30)}</span>`).join("") +
        `<span style="color:var(--tinta3)">gris: el resto</span>`;
    }
    dibujar();
  },

  enlaces(el, o = {}) {
    const d = T("p6_prediccion_enlaces");
    const tieneSin = d.some((r) => r.AUC_sin_rivales_comunes != null);
    let vista = "AUC";
    const [c, g, info] = partes(el, "controles", "", "lectura");
    if (tieneSin) chips(c, [{ t: "todos los pares", v: "AUC" }, { t: "pares sin rivales en común", v: "AUC_sin_rivales_comunes" }], vista, (v) => { vista = v; dibujar(); });
    function dibujar() {
      const filas = d.filter((r) => r[vista] != null).map((r) => ({ cat: r.metodo, val: r[vista], r }));
      G.barrasH(g, filas, { izq: 260, dur: 300, max: 1, fmt: (v) => G.fmtN(v, 3), paso: o.modo === "presentacion" ? 34 : 26,
        color: (x) => x.r.tipo === "heurística" ? G.css("--neutro") : x.r.tipo === "GNN" ? G.css("--s2") : G.css("--s1") });
      info.innerHTML = vista === "AUC" ? "Gris: heurísticas que cuentan rivales en común. Celeste: embeddings clásicos. Rojo: redes neuronales sobre grafos con los rasgos de cada proveedor. 0,5 es azar." :
        "Entre pares que todavía no comparten ningún rival, las heurísticas valen 0,5 por construcción: no tienen nada que contar. Aquí se ve qué aporta cada embedding.";
    }
    dibujar();
  },

  convergencia(el, o = {}) {
    const d = T("p6_convergencia");
    let metrica = "NMI", k = 30;
    const [c, tabla] = partes(el, "controles", "tabla-scroll");
    chips(c, [{ t: "NMI", v: "NMI" }, { t: "ARI", v: "ARI" }], metrica, (v) => { metrica = v; dibujar(); });
    if (!o.compacto) chips(c, [{ t: "k = 4", v: 4 }, { t: "k = 30", v: 30 }], k, (v) => { k = v; dibujar(); });
    function dibujar() {
      const f = d.filter((r) => r.k === k);
      const embs = [...new Set(f.map((r) => r.embedding))], ets = [...new Set(f.map((r) => r.etiqueta))];
      const max = d3.max(f, (r) => r[metrica]);
      const color = (v) => d3.interpolateRgb(G.css("--panel"), G.css("--s1"))(Math.max(0, v) / max);
      const corta = (e) => o.compacto ? e.replace("de la Parte II", "II").replace("comunidad de la Parte V", "comunidad V").replace("familia CUBSO", "rubro").replace("departamento", "depto.") : e;
      tabla.innerHTML = `<table class="datos"><tr><th>grupos de</th>${ets.map((e) => `<th class="num">${corta(e)}</th>`).join("")}</tr>` +
        embs.map((e) => `<tr><td>${e}</td>${ets.map((t) => { const v = f.find((r) => r.embedding === e && r.etiqueta === t)[metrica];
          return `<td class="num" style="background:${color(v)};color:${v > .6 * max ? "#fff" : "inherit"};font-weight:600">${G.fmtN(v, 2)}</td>`; }).join("")}</tr>`).join("") + "</table>";
    }
    dibujar();
  },
};

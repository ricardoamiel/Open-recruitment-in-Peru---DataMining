// Componentes de gráficos compartidos por el reporte y la presentación.
// Cada función recibe un contenedor y datos ya calculados por los notebooks;
// lo único que se recalcula en el navegador es lo barato: PageRank sobre un
// subgrafo de 120 nodos, KMeans y DBSCAN sobre una muestra de 3.000 puntos.
const G = (() => {
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const SERIES = () => [css("--s1"), css("--s2"), css("--s3"), css("--s4"), css("--s5")];
  // Punto para miles y coma para decimales, como en la prosa (de-DE agrupa también los números de 4 cifras).
  const fmtN = (x, d = 0) => (x == null || isNaN(x)) ? "s/d" :
    Number(x).toLocaleString("de-DE", { maximumFractionDigits: d, minimumFractionDigits: d });
  const fmtC = (x) => {
    const a = Math.abs(x);
    if (a >= 1e6) return fmtN(x / 1e6, a >= 1e8 ? 0 : 1) + " millones";
    if (a >= 1e4) return fmtN(x / 1e3, 0) + " mil";
    return fmtN(x, a < 10 && a % 1 ? 2 : 0);
  };
  const corto = (s, n = 34) => (s || "").length > n ? s.slice(0, n - 1) + "…" : (s || "");

  let tip;
  function tooltip() {
    if (!tip) tip = d3.select("body").append("div").attr("class", "tooltip");
    return {
      show(ev, html) { tip.html(html).style("opacity", 1); this.move(ev); },
      move(ev) {
        const w = tip.node().offsetWidth, x = ev.clientX + 14 + w > innerWidth ? ev.clientX - w - 14 : ev.clientX + 14;
        tip.style("left", x + "px").style("top", (ev.clientY + 14) + "px");
      },
      hide() { tip.style("opacity", 0); },
    };
  }

  function lienzo(el, ancho, alto, m) {
    const sel = d3.select(el);
    sel.selectAll("*").remove();
    sel.classed("grafico", true);
    const svg = sel.append("svg").attr("viewBox", `0 0 ${ancho} ${alto}`).attr("role", "img");
    const g = svg.append("g").attr("transform", `translate(${m.l},${m.t})`);
    return { svg, g, w: ancho - m.l - m.r, h: alto - m.t - m.b };
  }

  // Barras horizontales ordenadas, con valor rotulado al final de cada barra.
  function barrasH(el, datos, o = {}) {
    const cat = o.cat || "cat", val = o.val || "val", fmt = o.fmt || fmtC;
    const d = [...datos].sort((a, b) => o.orden === "dato" ? 0 : b[val] - a[val]);
    const alto = o.alto || (34 + d.length * (o.paso || 26));
    const { g, w, h } = lienzo(el, o.ancho || 760, alto, { t: 8, r: 70, b: 24, l: o.izq || 230 });
    const y = d3.scaleBand(d.map((r) => r[cat]), [0, h]).padding(.28);
    const x = d3.scaleLinear([o.min || 0, o.max || d3.max(d, (r) => r[val]) * 1.02], [0, w]);
    g.append("g").attr("class", "eje").call(d3.axisLeft(y).tickSize(0).tickFormat((t) => corto(t, o.corte || 36)))
      .call((a) => a.select("path").remove()).selectAll("text").attr("dx", -6);
    const t = tooltip();
    g.selectAll("rect").data(d).join("rect").attr("y", (r) => y(r[cat])).attr("height", y.bandwidth())
      .attr("rx", 3).attr("fill", (r, i) => typeof o.color === "function" ? o.color(r, i) : (o.color || css("--s1")))
      .attr("width", 0)
      .on("mousemove", (ev, r) => o.tip ? t.show(ev, o.tip(r)) : null).on("mouseleave", () => t.hide())
      .transition().duration(o.dur ?? 700).delay((_, i) => i * 40).attr("width", (r) => Math.max(0, x(r[val])));
    g.selectAll("text.v").data(d).join("text").attr("class", "v rotulo").attr("y", (r) => y(r[cat]) + y.bandwidth() / 2)
      .attr("dy", ".35em").attr("x", (r) => Math.max(0, x(r[val])) + 6).text((r) => fmt(r[val])).style("opacity", 0)
      .transition().delay(o.dur ?? 700).style("opacity", 1);
    return { g, x, y };
  }

  // Líneas sobre un eje x numérico. series: [{nombre, puntos:[{x,y}], color, punteada}]
  function lineas(el, series, o = {}) {
    const { g, w, h } = lienzo(el, o.ancho || 760, o.alto || 340, { t: 14, r: o.der || 120, b: 42, l: 58 });
    const todos = series.flatMap((s) => s.puntos);
    const x = (o.logx ? d3.scaleLog() : d3.scaleLinear()).domain(o.dx || d3.extent(todos, (p) => p.x)).range([0, w]);
    const y = (o.logy ? d3.scaleLog() : d3.scaleLinear()).domain(o.dy || [0, d3.max(todos, (p) => p.y) * 1.05]).nice().range([h, 0]);
    g.append("g").attr("class", "rejilla").call(d3.axisLeft(y).ticks(5).tickSize(-w).tickFormat(""));
    g.append("g").attr("class", "eje").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(o.tx || 6, o.fx));
    g.append("g").attr("class", "eje").call(d3.axisLeft(y).ticks(5, o.fy));
    if (o.ex) g.append("text").attr("class", "tenue").attr("x", w).attr("y", h + 36).attr("text-anchor", "end").text(o.ex);
    if (o.ey) g.append("text").attr("class", "tenue").attr("x", -6).attr("y", -4).attr("text-anchor", "start").text(o.ey);
    const linea = d3.line().x((p) => x(p.x)).y((p) => y(p.y));
    series.forEach((s, i) => {
      const c = s.color || SERIES()[i % 5];
      const p = g.append("path").datum(s.puntos).attr("fill", "none").attr("stroke", c).attr("stroke-width", s.grosor || 2.4)
        .attr("stroke-dasharray", s.punteada ? "5 4" : null).attr("d", linea);
      if (!s.punteada) {
        const L = p.node().getTotalLength();
        p.attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L).transition().duration(900).attr("stroke-dashoffset", 0);
      }
      if (s.marcas !== false) g.selectAll(null).data(s.puntos).join("circle").attr("cx", (p) => x(p.x)).attr("cy", (p) => y(p.y))
        .attr("r", 3.4).attr("fill", c);
      const u = s.puntos[s.puntos.length - 1];
      g.append("text").attr("x", x(u.x) + 8).attr("y", y(u.y)).attr("dy", ".35em").attr("fill", c)
        .style("font-weight", 600).text(s.nombre);
    });
    return { g, x, y, w, h };
  }

  // Dispersión con color por grupo. puntos: [{x, y, grupo, etiqueta}]
  function dispersion(el, puntos, o = {}) {
    const { g, w, h } = lienzo(el, o.ancho || 760, o.alto || 420, { t: 12, r: 16, b: 42, l: 54 });
    const x = d3.scaleLinear(o.dx || d3.extent(puntos, (p) => p.x), [0, w]).nice();
    const y = d3.scaleLinear(o.dy || d3.extent(puntos, (p) => p.y), [h, 0]).nice();
    if (o.ejes !== false) {
      g.append("g").attr("class", "eje").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(6));
      g.append("g").attr("class", "eje").call(d3.axisLeft(y).ticks(6));
    }
    if (o.ex) g.append("text").attr("class", "tenue").attr("x", w).attr("y", h + 36).attr("text-anchor", "end").text(o.ex);
    if (o.ey) g.append("text").attr("class", "tenue").attr("x", 0).attr("y", -2).text(o.ey);
    const t = tooltip();
    const col = o.color || ((p) => SERIES()[(p.grupo ?? 0) % 5]);
    const c = g.selectAll("circle").data(puntos).join("circle").attr("cx", (p) => x(p.x)).attr("cy", (p) => y(p.y))
      .attr("r", o.r || 2.6).attr("fill", col).attr("fill-opacity", o.op || .7)
      .on("mousemove", (ev, p) => p.etiqueta && t.show(ev, p.etiqueta)).on("mouseleave", () => t.hide());
    return { g, x, y, c, w, h, col };
  }

  // Barras apiladas al 100 % por fila. filas: [{nombre, partes:{clave:valor}}]
  function apiladas(el, filas, claves, o = {}) {
    const { g, w, h } = lienzo(el, o.ancho || 760, o.alto || (60 + filas.length * 54), { t: 34, r: 12, b: 10, l: o.izq || 120 });
    const y = d3.scaleBand(filas.map((f) => f.nombre), [0, h]).padding(.3);
    const x = d3.scaleLinear([0, 100], [0, w]);
    const colores = o.colores || SERIES();
    g.append("g").attr("class", "eje").call(d3.axisLeft(y).tickSize(0)).call((a) => a.select("path").remove());
    filas.forEach((f) => {
      let acc = 0;
      claves.forEach((k, i) => {
        const v = f.partes[k] || 0;
        g.append("rect").attr("y", y(f.nombre)).attr("height", y.bandwidth()).attr("x", x(acc)).attr("width", 0)
          .attr("fill", colores[i]).transition().duration(700).delay(i * 220).attr("width", x(v));
        if (v > 7) g.append("text").attr("x", x(acc + v / 2)).attr("y", y(f.nombre) + y.bandwidth() / 2).attr("dy", ".35em")
          .attr("text-anchor", "middle").style("fill", i === 0 && o.primeroClaro ? css("--tinta") : "#fff").style("font-weight", 700)
          .text(fmtN(v) + " %").style("opacity", 0).transition().delay(700 + i * 220).style("opacity", 1);
        acc += v;
      });
    });
    const ley = g.append("g").attr("transform", "translate(0,-24)");
    let lx = 0;
    claves.forEach((k, i) => {
      const it = ley.append("g").attr("transform", `translate(${lx},0)`);
      it.append("rect").attr("width", 12).attr("height", 12).attr("rx", 2).attr("fill", colores[i]);
      const tx = it.append("text").attr("x", 17).attr("y", 10).text(k);
      lx += 30 + tx.node().getComputedTextLength();
    });
  }

  // ------------------------------------------------------------ algoritmos
  function pagerank(n, aristas, beta, tol = 1e-12, maxIter = 1000) {
    const salida = new Float64Array(n);
    aristas.forEach((a) => (salida[a.s] += a.w));
    let r = new Float64Array(n).fill(1 / n), it = 0;
    for (; it < maxIter; it++) {
      const nuevo = new Float64Array(n);
      let fuga = 0;
      for (let i = 0; i < n; i++) if (salida[i] === 0) fuga += r[i];
      aristas.forEach((a) => (nuevo[a.d] += beta * r[a.s] * a.w / salida[a.s]));
      const base = (beta * fuga + 1 - beta) / n;
      let delta = 0;
      for (let i = 0; i < n; i++) { nuevo[i] += base; delta += Math.abs(nuevo[i] - r[i]); }
      r = nuevo;
      if (delta < tol) break;
    }
    return { r, it: it + 1 };
  }

  function semillaAleatoria(s) { return () => ((s = Math.imul(s ^ (s >>> 15), 2246822507) ^ (s + 0x6D2B79F5)) >>> 0) / 4294967296; }
  function d2(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += (a[i] - b[i]) ** 2; return s; }

  function kmeans(X, k, semilla = 7, maxIter = 60) {
    const rnd = semillaAleatoria(semilla), n = X.length;
    const C = [X[Math.floor(rnd() * n)]];
    const dist = X.map((x) => d2(x, C[0]));
    while (C.length < k) {                       // KMeans++: muestreo proporcional a D^2
      let s = dist.reduce((a, b) => a + b, 0) * rnd(), i = 0;
      while ((s -= dist[i]) > 0 && i < n - 1) i++;
      C.push(X[i]);
      X.forEach((x, j) => (dist[j] = Math.min(dist[j], d2(x, X[i]))));
    }
    let etq = new Array(n).fill(0), sse = 0;
    for (let it = 0; it < maxIter; it++) {
      let cambio = false; sse = 0;
      X.forEach((x, j) => {
        let mejor = 0, md = Infinity;
        C.forEach((c, q) => { const v = d2(x, c); if (v < md) { md = v; mejor = q; } });
        if (etq[j] !== mejor) { etq[j] = mejor; cambio = true; }
        sse += md;
      });
      const suma = C.map(() => new Array(X[0].length).fill(0)), cnt = new Array(k).fill(0);
      X.forEach((x, j) => { cnt[etq[j]]++; x.forEach((v, q) => (suma[etq[j]][q] += v)); });
      for (let q = 0; q < k; q++) if (cnt[q]) C[q] = suma[q].map((v) => v / cnt[q]);
      if (!cambio && it > 0) break;
    }
    return { etq, C, sse };
  }

  function dbscan(X, eps, minPts) {
    const n = X.length, e2 = eps * eps, etq = new Array(n).fill(-2);
    const vecinos = (i) => { const v = []; for (let j = 0; j < n; j++) if (d2(X[i], X[j]) <= e2) v.push(j); return v; };
    let c = -1;
    for (let i = 0; i < n; i++) {
      if (etq[i] !== -2) continue;
      const v = vecinos(i);
      if (v.length < minPts) { etq[i] = -1; continue; }
      etq[i] = ++c;
      const cola = [...v];
      while (cola.length) {
        const q = cola.pop();
        if (etq[q] === -1) etq[q] = c;
        if (etq[q] !== -2) continue;
        etq[q] = c;
        const vq = vecinos(q);
        if (vq.length >= minPts) cola.push(...vq);
      }
    }
    return etq;
  }

  return { css, SERIES, fmtN, fmtC, corto, tooltip, lienzo, barrasH, lineas, dispersion, apiladas,
           pagerank, kmeans, dbscan };
})();

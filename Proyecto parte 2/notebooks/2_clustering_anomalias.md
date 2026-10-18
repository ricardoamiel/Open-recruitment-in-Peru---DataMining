# Notebook 2. Clustering y detección de anomalías

Guía de estudio del notebook [2_clustering_anomalias.ipynb](2_clustering_anomalias.ipynb). Recorre el notebook sección por sección, explica por dentro cada técnica, interpreta cada figura, dice qué se descartó y por qué, y cierra con las preguntas previsibles de la sustentación.

**Integrantes:** Ricardo Acuña, Juan Aquino y Camilo Soto.

## 1. Qué responde esta parte

**Pregunta 1 del proyecto:** ¿qué tipos de proveedor existen en la contratación pública peruana, y cuáles combinan dependencia de un solo cliente con poca competencia?

No se clasifica por tamaño, que ya sabemos que es muy desigual, sino por **comportamiento**: a cuántos clientes vende, con cuánta competencia gana, en cuántos mercados opera.

**Por qué le importa a un gerente de supervisión.** Nadie puede revisar 63 mil proveedores. Una tipología convierte esa masa en cuatro perfiles con una política distinta para cada uno, y las anomalías dan una cola de revisión corta en la que cada proveedor llega con la razón por la que es raro.

**Los dos hallazgos, en una frase cada uno:**

1. **Existe un perfil de proveedor cautivo**: 1.285 proveedores que viven de una sola entidad y ganan sin otro postor el 91 por ciento de las veces, por S/ 1.645 millones.
2. **Las anomalías útiles no son las más grandes**: de 289 anomalías, 202 son grandes proveedores nacionales y 87 son raras por competencia, con postor único en el 73 por ciento de lo que ganan.

**Dónde corre.** Spark para leer la base, ensamblar, estandarizar, aplicar PCA y para el KMeans de MLlib. Local para el KMeans++ propio, el jerárquico y la densidad. La sección 4 mide los dos caminos.

## 2. El vocabulario mínimo

1. **Clustering.** Agrupar puntos sin etiquetas de modo que los de un mismo grupo se parezcan entre sí y no a los de otros grupos.
2. **Centroide.** El promedio de los puntos de un cluster. Puede no ser un punto real.
3. **SSE.** Suma de las distancias al cuadrado de cada punto a su centroide. Siempre baja al subir k.
4. **Silueta.** Para cada punto, (b menos a) dividido entre el mayor de los dos, donde a es su distancia media a los de su cluster y b la menor distancia media a otro cluster. Va de menos 1 a 1; cerca de 1 es un punto bien asignado.
5. **ARI, índice de Rand ajustado.** Mide cuánto coinciden dos particiones, corrigiendo por azar. 1 es acuerdo perfecto y 0 es lo que daría el azar.
6. **Ruido en DBSCAN.** Un punto que no es núcleo ni está al alcance de ningún núcleo.

## 3. Recorrido sección por sección

### Sección 1. Población, características y estandarización

**Población: solo proveedores con tres o más adjudicaciones, 12.235 de 63.204.** No es por comodidad. Las tasas que definen el comportamiento, como la cuota del mayor cliente o la tasa de postor único, valen exactamente 0 o 1 cuando se ganó una sola vez. Con esos proveedores dentro, el algoritmo encontraría esquinas del cubo y no perfiles.

**Las doce características y su transformación:**

| Grupo | Variables | Transformación |
| --- | --- | --- |
| Escala | n_ganados, monto_total, monto_mediano | logaritmo de uno más el valor |
| Alcance | n_entidades, n_departamentos, n_familias | logaritmo de uno más el valor |
| Dependencia y continuidad | cuota_cliente_top, meses_activos | ninguna |
| Competencia y rubro | tasa_victoria, pct_postor_unico, pct_sin_concurso, pct_obras | ninguna |

**Por qué logaritmo.** El monto va de miles a cientos de millones. Sin logaritmo, tres o cuatro proveedores gigantes definirían toda la geometría.

**Por qué se dejan fuera dos variables.** n_participaciones es casi n_ganados dividido entre la tasa de victoria, y pct_servicios es casi el complemento de bienes más obras. Una variable redundante cuenta dos veces en la distancia euclidiana.

**Estandarización.** Media cero y desviación uno con el StandardScaler de Spark. Sin ella, el monto en logaritmo, que va de 7 a 20, dominaría a una tasa que va de 0 a 1.

**Reducción de dimensión con PCA.** El PCA de Spark rota el espacio a ejes no correlacionados ordenados por varianza. Se conservan las componentes que explican el 90 por ciento. Dos razones: las variables de escala están correlacionadas y sin PCA el tamaño contaría tres veces; y DBSCAN funciona mejor en pocas dimensiones.

**Figura f09.** Varianza explicada por componente y acumulada. La primera componente explica solo el 40 por ciento, y hacen falta 6 de 12 para llegar al 90. La primera la forman sobre todo n_entidades, n_ganados y meses_activos, es decir **escala y alcance**; la segunda, pct_postor_unico, pct_sin_concurso y monto_mediano con signo opuesto, es decir **competencia**. **Lectura para un gerente:** el comportamiento de un proveedor tiene al menos dos ejes independientes, cuánto vende y cómo gana, y un ranking de monto solo ve el primero.

**Detalle técnico que conviene saber.** El signo de una componente es arbitrario. Se orienta cada una para que su carga más grande sea positiva, de modo que PC1 crece con la escala. Cambiar el signo no altera ninguna distancia.

### Sección 2. KMeans++ y la elección de k

**Cómo funciona KMeans, el algoritmo de Lloyd de la lecture.** Se eligen k centroides iniciales; cada punto se asigna al centroide más cercano; cada centroide se recalcula como el promedio de sus puntos; se repite hasta que ningún punto cambie de cluster. La función objetivo, el SSE, baja en cada paso, así que siempre termina, pero en un mínimo local que depende del inicio.

**Cómo funciona k-means++.** Resuelve el problema del mal inicio. El primer centroide es un punto al azar. Cada siguiente se elige con probabilidad proporcional a D(x) al cuadrado, la distancia al centroide ya elegido más cercano: los puntos lejanos tienen más chance, y los centroides iniciales quedan bien separados. La implementación propia en algoritmos.py sigue el pseudocódigo de la lecture, incluida la selección por probabilidad acumulada.

**Cómo se elige k.** Se prueban k de 2 a 12 y se miran dos criterios a la vez:

1. **El codo del SSE.** Se normalizan los ejes y se busca el k más lejano de la cuerda que une el primer y el último punto.
2. **La silueta.** Su máximo indica la partición con grupos más separados.

**Figura f10.** SSE y silueta por k, propios y de MLlib. El codo está en k = 5 y la silueta más alta en k = 4, con 0,383. Se adopta **k = 4** porque en k = 5 la silueta cae a 0,267, más de 0,05 por debajo. La silueta de MLlib da valores más altos porque usa la distancia euclidiana al cuadrado, pero su máximo también está en k = 4. En 5 de los 11 valores de k, el SSE de MLlib queda más de un 1 por ciento por encima del propio: su inicialización cayó en un mínimo local peor, que es justo el riesgo que k-means++ reduce.

**Qué dice una silueta de 0,38.** Que los grupos existen pero no son islas: el comportamiento de los proveedores es un continuo con regiones más densas. Es lo esperable en un mercado y es la razón para complementar con un método de densidad.

### Sección 3. Qué perfil representa cada cluster

Se lee el promedio de cada cluster en las variables estandarizadas: un valor de más 1 es una desviación estándar por encima del proveedor recurrente típico.

| Cluster | Perfil | Proveedores | Monto | Rasgo distintivo |
| --- | --- | --- | --- | --- |
| 0 | competitivo típico | 7.728, 63 % | 18 % | gana compitiendo, con actividad esporádica |
| 1 | gran proveedor recurrente | 2.160, 18 % | 49 % | mediana de 15 adjudicaciones y 9 entidades |
| 2 | contratista de obra | 1.062, 9 % | 31 % | obras y contratos grandes |
| 3 | cautivo sin competencia | 1.285, 10 % | 3 % | un solo cliente, gana sin postor y sin concurso |

**Figura f11.** Mapa de calor de los perfiles con escala divergente: rojo por encima del típico, azul por debajo. El cluster 3 es la respuesta directa a la pregunta 1: en mediana obtiene el 100 por ciento de su monto de un solo cliente, su tasa de victoria es 1,0, gana sin otro postor el 91 por ciento de las veces y sin concurso el 96 por ciento.

**Cómo leer la tasa de victoria de 1,0.** No significa que gane todo lo que disputa, sino que solo aparece como participante cuando gana: es lo que ocurre en la contratación directa y el régimen especial, donde no hay competidores registrados.

**El nombre de cada cluster no se escribe a mano.** Se asigna por regla: el cautivo es el que maximiza la suma de cuota, postor único y sin concurso; el contratista de obra, el de mayor pct_obras entre los restantes; el gran proveedor, el de mayor n_ganados; el resto es el competitivo típico. Así el nombre sigue al dato si el dato cambia.

**Hallazgo y acción.** 1.285 proveedores cautivos suman S/ 1.645 millones. No es una irregularidad en sí: puede ser el único proveedor de un rubro en una provincia, un servicio con exclusividad o una compra de emergencia. Pero es la combinación que vuelve vulnerable a una entidad frente a su proveedor. **Acción:** usar el cluster como lista de vigilancia, revisar si la falta de competencia se explica por el rubro o la geografía y exigir un estudio de mercado ampliado en las próximas convocatorias; la Parte III aporta los sustitutos de mercado con los que ampliar la invitación.

### Sección 4. MLlib frente al propio, y si Spark conviene aquí

| Implementación | SSE en k = 4 | Segundos |
| --- | --- | --- |
| KMeans++ propio, numpy | 59.216,7 | 0,08 |
| KMeans de MLlib, k-means paralelo | 59.216,7 | 4,2 |

ARI entre las dos particiones: 1,0. Encuentran exactamente la misma estructura partiendo de inicializaciones distintas, lo que es evidencia de que los clusters no son un accidente de la semilla.

**Por qué Spark no conviene aquí y numpy sí.** Con 12 mil puntos en 6 dimensiones, una iteración de Lloyd es un producto de matrices que numpy hace en milisegundos, mientras Spark paga la planificación de cada iteración como un trabajo distribuido. Es unas 50 veces más lento. Si la población fueran millones de proveedores o cientos de dimensiones, el orden se invertiría y MLlib sería la herramienta, sin cambiar nada más del notebook.

**Qué es k-means paralelo.** La variante distribuida de k-means++ que usa MLlib: en lugar de elegir un centroide por pasada, muestrea varios candidatos por pasada con la misma probabilidad proporcional a D al cuadrado y luego los reduce a k.

### Sección 5. Jerárquico aglomerativo sobre una muestra

**Cómo funciona, la versión de la lecture.** Cada punto empieza como su propio cluster; en cada paso se fusionan los dos más cercanos; se repite hasta tener uno solo. El resultado es un dendrograma.

**Por qué sobre una muestra.** Necesita la matriz completa de distancias: memoria de orden n al cuadrado y tiempo de orden n al cubo en la versión directa. Con 12 mil puntos son 150 millones de distancias por paso.

**Verificación.** La implementación propia con enlace por centroide se compara contra el linkage de scipy sobre 200 puntos, y las alturas de fusión son idénticas.

**Por qué Ward para el dendrograma.** Ward fusiona en cada paso el par cuya unión menos aumenta la varianza interna. Es el análogo jerárquico de KMeans, porque minimiza el mismo SSE, y por eso es el que se puede comparar con él.

**Figura f12.** Dendrograma de Ward sobre 2.000 proveedores, truncado en las últimas 40 fusiones, con el corte en 4 grupos. Cortado ahí coincide con KMeans con un ARI de 0,67. Las fusiones altas unen grupos muy distintos; por debajo del corte las fusiones son bajas y parejas, sin un salto que pida un corte más fino. **Lectura:** pocos perfiles bien separados y mucha variación individual dentro de cada uno.

### Sección 6. Densidad: DBSCAN y HDBSCAN

**Cómo funciona DBSCAN.** Un punto es **núcleo** si tiene al menos min_pts vecinos a distancia eps, contándose a sí mismo. Los clusters crecen de núcleo en núcleo por alcanzabilidad: un vecino de un núcleo se une al cluster, y si también es núcleo, expande. Un punto frontera se une pero no expande. Lo que no es alcanzable desde ningún núcleo es ruido.

**Por qué importa para anomalías.** KMeans asigna todo punto a algún cluster, incluso el más extraño. DBSCAN no.

**Cómo se eligen los parámetros.** min_pts = 12, el doble de la dimensión, que es la regla habitual. eps sale del gráfico de distancia al vecino número 12.

**Figura f13.** Distancia al vecino número 12, ordenada. La curva es plana dentro de las regiones densas y se dispara en los puntos aislados. El codo está en 1,28, que se adopta como eps. El 7,6 por ciento de los proveedores tiene a su vecino 12 más lejos que eso.

**Resultados:**

| Método | Clusters | Ruido |
| --- | --- | --- |
| DBSCAN propio | 2 | 3,4 % |
| DBSCAN de scikit-learn | 2 | 3,4 % |
| HDBSCAN | 6 | 38,1 % |

El DBSCAN propio y el de scikit-learn coinciden con ARI 1,0 y el mismo ruido. El propio usa un KD-tree de scipy para consultar vecindarios sin calcular las n al cuadrado distancias.

**Por qué DBSCAN da solo dos clusters.** Con un solo eps no puede separar perfiles de densidades muy distintas y a la vez marcar el ruido. Por eso no compite con KMeans como tipología: lo complementa como detector de anomalías.

**Qué hace HDBSCAN distinto.** Recorre todos los eps a la vez, construye la jerarquía de clusters por densidad y conserva los que persisten en un rango amplio de eps. Separa regiones de densidad distinta, por eso encuentra 6 grupos, pero exige al menos 50 miembros por grupo y deja como ruido el 38 por ciento.

**Figura f14.** Los recurrentes en las dos primeras componentes, coloreados por KMeans a la izquierda y con el ruido de DBSCAN en rojo a la derecha. KMeans corta el continuo en cuatro regiones contiguas. El ruido, 416 proveedores, está en la periferia y sobre todo a la derecha: su mediana de adjudicaciones es 3 veces la del núcleo. Algunos puntos rojos parecen rodeados de grises porque son raros en dimensiones que esta proyección de dos ejes no muestra.

### Sección 7. Anomalías: quiénes son y qué tienen de raro

**Definición.** Un proveedor es anomalía si DBSCAN lo marca como ruido **y además** está en el 5 por ciento más lejano del centroide de su cluster de KMeans. Pedir las dos señales reduce los falsos positivos de cada una: el ruido de DBSCAN puede ser un punto en una zona poco poblada pero normal, y la distancia al centroide puede ser alta en un cluster muy extendido. Resultado: 289 proveedores, el 2,4 por ciento de los recurrentes.

**El rasgo extremo.** Para cada anomalía se listan las dos variables estandarizadas con mayor valor absoluto. Es la razón por la que es rara.

**Dos tipos de rareza.** Si alguno de sus dos rasgos extremos es de competencia o dependencia, es decir cuota del cliente, tasa de victoria, postor único o sin concurso, la anomalía es de competencia; si no, es de escala.

| Tipo | Proveedores | Monto | Postor único medio | Sin concurso medio |
| --- | --- | --- | --- | --- |
| Escala | 202 | S/ 21.311 millones | 27 % | 30 % |
| Competencia o dependencia | 87 | S/ 1.629 millones | 73 % | 94 % |

**Figura f15.** Frecuencia de cada rasgo entre los dos más extremos de las anomalías. La mayoría son raras por escala: los grandes proveedores nacionales de maquinaria, seguros o insumos médicos que le venden a más de cien entidades. Esa rareza es esperable.

**La cola útil.** Las 87 de competencia. Entre las de mayor monto aparecen la Fábrica de Armas y Municiones del Ejército, consorcios de laboratorios farmacéuticos, estudios de abogados internacionales y un centro de diálisis. **Cómo defender esa lista en la sustentación:** casi todas tienen una explicación legítima posible, como fabricante estatal, patente, arbitraje internacional o el único prestador de una zona. Por eso es una cola de revisión y no una lista de sospechosos: el método dice dónde mirar primero y qué preguntar, no qué se encontrará.

**Acción.** Entregar al área de control solo la cola de competencia, ordenada por monto, con el rasgo extremo como primera pregunta, y recalcularla cada trimestre con los mismos parámetros para ver quién entra y quién sale.

### Sección 8. Exportación

1. data/processed/clusters_proveedores, con cluster, etiqueta de DBSCAN y HDBSCAN, distancia al centroide y marca de anomalía por proveedor, para comparar en las Partes IV a VI con comunidades y embeddings.
2. artifacts/p2_puntos y p2_centroides, una muestra en coordenadas de PCA y los centroides para k de 2 a 10. Con eso el reporte web puede reasignar puntos al mover k sin recalcular nada pesado.

## 4. Técnicas consideradas y descartadas

1. **Incluir a los proveedores de una o dos adjudicaciones.** Sus tasas valen 0 o 1 y generan clusters artificiales.
2. **Clustering sin PCA.** El tamaño contaría tres veces y DBSCAN sufriría en 12 dimensiones.
3. **K-medoids.** Su paso de actualización prueba cada punto del cluster como candidato a medoide, de orden n al cuadrado por cluster; aquí hay un promedio natural, así que el centroide tiene sentido y KMeans basta.
4. **BFR.** Escala KMeans resumiendo los puntos en N, SUM y SUMSQ cuando no caben en memoria. Aquí caben de sobra, y BFR supone clusters con forma de elipse alineada a los ejes.
5. **Jerárquico sobre toda la población.** Inviable en memoria y tiempo; se usa sobre una muestra.
6. **DBSCAN como tipología.** Con un solo eps no separa perfiles; se usa como detector de ruido.
7. **Anomalía por una sola señal.** Ni el ruido de DBSCAN ni la distancia al centroide bastan por separado.

## 5. Preguntas previsibles y su respuesta

**¿Por qué k = 4 si el codo dice 5?** Porque en k = 5 la silueta cae de 0,383 a 0,267. La regla del notebook prefiere el codo solo si su silueta queda a menos de 0,05 de la mejor. Y el k elegido lo confirman la silueta de MLlib y el jerárquico.

**¿Por qué la silueta propia no coincide con la de MLlib?** Porque MLlib usa distancia euclidiana al cuadrado y la propia, la de la lecture, usa la euclidiana. Los valores cambian, el máximo no.

**¿Qué significa un ARI de 1,0 entre el propio y MLlib?** Que las dos implementaciones, con inicializaciones distintas, asignan cada proveedor al mismo cluster. La estructura es estable.

**¿Un proveedor cautivo es corrupto?** No. Es una combinación de dependencia y falta de competencia que puede tener explicaciones legítimas. El análisis prioriza la revisión; no la sustituye.

**¿Por qué las anomalías de escala no interesan?** Sí interesan para entender el mercado, pero no para supervisión: que una empresa grande sea grande no es una señal. Separarlas evita que la lista de anomalías sea, sin más, la de las empresas más grandes.

**¿Por qué HDBSCAN deja tanto ruido?** Porque exige que un grupo tenga al menos 50 miembros y persista en un rango amplio de densidades. Es más estricto que DBSCAN con un solo eps.

**¿Por qué no usar Spark para todo?** Se midió: KMeans en numpy tarda 0,08 segundos y en MLlib 4,2. Spark se justifica para leer y transformar la base con el mismo código de un clúster, no para iterar sobre 12 mil puntos.

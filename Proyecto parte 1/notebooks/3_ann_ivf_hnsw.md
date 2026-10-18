# Notebook 3. Búsqueda aproximada de vecinos: IVF y HNSW

Guía de estudio del notebook [3_ann_ivf_hnsw.ipynb](3_ann_ivf_hnsw.ipynb). El porqué de cada elección está en [docs/JUSTIFICACION.md](../docs/JUSTIFICACION.md), sección Parte III.

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

Qué significa cada campo, cada código CUBSO y cada etiqueta del dato está en [docs/GLOSARIO.md](../docs/GLOSARIO.md).

## 1. Qué responde esta parte

Dado un proceso de contratación, cuáles son los diez más parecidos de todo el conjunto, y cuánto cuesta responder eso de forma exacta frente a aproximada.

Es la misma pregunta de parecido de la Parte II, pero con otra representación y otra estructura. Allí el documento era un conjunto de shingles y la métrica Jaccard; aquí es un vector denso y la métrica el coseno. No es una cadena: son dos caminos distintos para la misma pregunta.

**Spark no se usa aquí, y hay que argumentarlo.** FAISS es una biblioteca de un solo nodo, el subconjunto cabe holgadamente en memoria, y toda la consulta es búsqueda en un índice y no agregación distribuida. Distribuir agregaría barajado y serialización sin ganar nada. Reconocer dónde Spark no aporta es parte de lo que evalúa la Parte VI.

## 2. Entradas y salidas

**Entrada.** El Parquet de la Parte I, filtrado a procesos con objeto de más de 60 caracteres y muestreado a 80.000. Ese tamaño está elegido para que la fuerza bruta duela y el índice tenga sentido, y para que el notebook corra en minutos.

**Salida.** Cinco artefactos y cinco figuras, de la f22 a la f26.

## 3. Recorrido sección por sección

### Sección 1. Dos representaciones vectoriales

Se construyen dos a propósito, para poder separar el efecto de la representación del efecto del índice.

1. **TF-IDF de palabras**, 22.037 términos. Es la de referencia.
2. **TF-IDF de 4-gramas de caracteres** con el analizador char_wb, 54.286 n-gramas. Es robusta frente a errores de digitación, que abundan porque el objeto lo escribe a mano cada entidad.

Las dos pasan por el mismo tratamiento: TF-IDF disperso, reducción a 128 dimensiones con **SVD truncada**, y normalización a norma uno.

**Por qué SVD.** FAISS trabaja sobre vectores densos y de dimensión fija. Un TF-IDF con 22.000 columnas sería inviable. La SVD truncada, que aplicada a TF-IDF se conoce como **Latent Semantic Analysis**, proyecta a un espacio de 128 dimensiones conservando la mayor parte de la varianza y, de paso, hace que términos que coocurren queden cerca.

**Por qué normalizar.** Con los vectores de norma uno, el **producto interno es exactamente el coseno**. Así se puede usar el índice de producto interno de FAISS y leer el resultado como similitud coseno sin convertir nada.

**Qué es sublinear_tf.** En lugar de la frecuencia bruta del término usa uno más su logaritmo, de modo que un término repetido diez veces no pesa diez veces más que uno que aparece una vez.

### Sección 2. Cómo se mide la latencia, y por qué el detalle decide la conclusión

Esta sección es la más importante del notebook y conviene saber contarla, porque corrige un error que cometimos nosotros.

**El problema.** FAISS cambia de implementación según el tamaño del lote de consultas. Con un lote grande, el índice plano resuelve la búsqueda como un producto de matrices con BLAS y aprovecha los ocho núcleos. Con una sola consulta no tiene nada que amortizar.

**Los dos regímenes corresponden a usos reales distintos.**

1. **Por lote.** Un trabajo fuera de línea, por ejemplo deduplicar todo el catálogo de una vez.
2. **Consulta única.** Un servicio en línea que responde a una petición a la vez.

Se miden los dos y toda comparación usa el mismo régimen en ambos lados. Mezclarlos produce diferencias de un orden de magnitud que no son del índice sino del método de medición. La primera versión del notebook medía la fuerza bruta con lotes de mil consultas y el escalado con lotes de trescientas, lo que daba un falso multiplicador de 28.

**Por qué la consulta única se mide con un solo hilo de OpenMP.** Por dos razones. La primera es de realismo: un servicio en línea atiende cada petición en su hilo y no reparte una sola consulta entre los ocho núcleos. La segunda es de estabilidad: con ocho hilos el arranque del grupo de hilos domina el tiempo de una consulta individual, y la medición se vuelve sensible a la carga de la máquina hasta producir curvas no monótonas que no dicen nada del índice.

Además hay calentamiento: se descartan las veinte primeras consultas y se toma la **mediana** de doscientas, no la media, porque la mediana no se mueve por una pausa del recolector de basura.

**La verdad de referencia** son los diez vecinos que devuelve el índice plano exacto, y la métrica de calidad es **recall en 10**: de los diez vecinos verdaderos, cuántos devuelve el índice aproximado.

### Sección 3. IVF, listas invertidas

**Cómo funciona.** Un k-medias previo parte el espacio en nlist celdas de Voronoi y guarda cada vector en la lista de su centroide más cercano. Eso es el entrenamiento. En consulta, se calcula la distancia a los nlist centroides, se eligen las nprobe celdas más cercanas y se recorren solo esos vectores. El trabajo baja en proporción a nprobe sobre nlist.

**El parámetro de calidad es nprobe.** Visitar más celdas acerca al resultado exacto y cuesta más tiempo. El valor de nlist se fija con la regla habitual, la raíz del número de vectores, que aquí da 282.

**El error que comete.** Un vecino verdadero puede estar en una celda que no se visitó, porque la frontera de Voronoi no respeta la vecindad: dos puntos cercanos pueden caer en celdas distintas si están junto a la frontera.

La **figura f22** muestra que el recall sube muy rápido y luego se aplana. Con nprobe igual a 1 se visita el 0,35 por ciento de las celdas y ya se recupera el 75 por ciento de los vecinos verdaderos; con 16 se llega al 99 por ciento en 0,122 milisegundos por consulta; con 64 se sube al 100 por ciento cuadruplicando el trabajo. La curva dice dónde dejar de pagar: más allá de la rodilla cada punto de recall cuesta desproporcionadamente.

### Sección 4. HNSW, grafo navegable en capas

**Qué significa el nombre.** Hierarchical Navigable Small World. Es un grafo de vecindad con varias capas.

**Cómo funciona.** Cada vector se conecta con hasta M vecinos cercanos. Las capas superiores son dispersas, con pocos nodos y aristas largas, y sirven para acercarse rápido a la región correcta; las inferiores son densas y afinan. La consulta entra por la capa superior, avanza con una búsqueda voraz hacia el vecino que más reduce la distancia, y al no poder mejorar baja una capa y repite. En la capa cero hace una búsqueda en haz con una lista de candidatos de tamaño efSearch.

**Los parámetros.** M es el número de aristas por nodo, aquí 32. efConstruction controla la calidad del grafo al construirlo, aquí 200. efSearch es el parámetro de calidad en consulta.

La **figura f23** muestra que HNSW llega muy alto con exploración mínima: con efSearch igual a 10 ya alcanza el 99 por ciento de recall en 0,028 milisegundos, y con 256 llega al 100 por ciento.

**La contrapartida está fuera de la figura y hay que decirla.** Construir el grafo tomó 7,1 segundos frente a 0,4 de IVF, y el grafo guarda hasta 32 aristas por nodo además de los vectores: 61,4 MB frente a 41,1 de IVF y 41,0 de la fuerza bruta.

### Sección 5. Los dos juntos, frente a la fuerza bruta

La comparación honesta no es recall contra parámetro sino **recall contra latencia**, cada índice en su mejor configuración para cada presupuesto de tiempo.

La **figura f24** tiene dos paneles y cuentan historias opuestas, que es por lo que hacen falta los dos.

1. **En lote**, la fuerza bruta tarda 0,0777 milisegundos por consulta y el mejor HNSW sobre el 95 por ciento de recall tarda 0,0088. El índice aproximado aporta poco, porque el índice plano resuelve el lote como un producto de matrices con BLAS sobre ocho núcleos y eso es extremadamente eficiente.
2. **Consulta a consulta** se invierte: la fuerza bruta tarda 1,924 milisegundos, HNSW 0,028, es decir 69 veces más rápido, e IVF 0,078.

La moraleja: la pregunta de si un índice aproximado vale la pena no tiene respuesta sin decir antes si el uso es por lotes o en línea.

**El escalado, figura f26.** Una sola medición no responde a partir de qué tamaño compensa, así que se mide sobre subconjuntos crecientes, en régimen de consulta única y con el mismo número de consultas en todos los puntos.

| Vectores | Fuerza bruta | HNSW | Factor |
| --- | --- | --- | --- |
| 5.000 | 0,064 ms | 0,024 ms | 2,7 |
| 10.000 | 0,110 ms | 0,027 ms | 4,1 |
| 20.000 | 0,257 ms | 0,033 ms | 7,9 |
| 40.000 | 0,799 ms | 0,041 ms | 19,7 |
| 80.000 | 1,940 ms | 0,053 ms | 36,7 |

Las dos rectas tienen pendientes distintas y esa diferencia es todo el argumento. Multiplicar la base por 16 multiplica el tiempo de la fuerza bruta por 30, que es crecimiento lineal, y el de HNSW por 2,2, que es el crecimiento logarítmico que promete la estructura.

**La conclusión incómoda que preferimos decir.** A nuestro volumen y en uso por lotes el índice aproximado no era necesario. Lo que lo justifica es el uso en línea y el escenario de volumen diez o cien veces mayor que plantea la Parte VI, y eso está medido aquí en lugar de supuesto.

**El efecto de la representación, figura f25.** Con el índice fijo y exacto en los dos casos, las dos representaciones comparten solo el 44 por ciento de los diez vecinos. Es un recordatorio incómodo: una parte grande de lo que se llama error de un índice aproximado es en realidad una decisión de representación tomada mucho antes. Los n-gramas de caracteres agrupan por forma de escritura; las palabras agrupan por vocabulario compartido. Ninguna es la correcta en abstracto.

### Sección 6. Cuándo conviene cada uno

| Índice | Construcción | Memoria | Latencia al 95 por ciento de recall |
| --- | --- | --- | --- |
| Fuerza bruta | 0,0 s | 41,0 MB | 1,924 ms |
| IVF con 282 celdas | 0,4 s | 41,1 MB | 0,078 ms |
| HNSW con M igual a 32 | 7,1 s | 61,4 MB | 0,028 ms |

1. **IVF** cuando la memoria es el límite y el conjunto cambia seguido. Se construye rápido, ocupa poco por encima de los vectores y admite insertar sin reconstruir. Degrada de forma predecible.
2. **HNSW** cuando la latencia es el límite y el conjunto es estable. Da más recall por milisegundo, pero el grafo cuesta construirlo y ocupa más memoria, y borrar elementos es incómodo.
3. **Fuerza bruta** cuando el conjunto es pequeño o la consulta es rara. No tiene ningún parámetro que calibrar mal y es la verdad de referencia.

## 4. Alternativas para cada decisión, explicadas

### Para indexar vecinos

1. **Fuerza bruta, índice plano.** Exacta y sin parámetros. Se conserva siempre, porque es la verdad de referencia sin la cual el recall no se puede medir. Su costo crece de forma lineal con la base.
2. **Árboles k-dimensionales y árboles de bolas.** Parten el espacio con hiperplanos o esferas y podan ramas por desigualdad triangular. Funcionan muy bien hasta unas diez o veinte dimensiones y luego degradan hasta el recorrido completo, porque en dimensión alta casi todos los puntos acaban a distancias parecidas y la poda deja de podar. Es la maldición de la dimensionalidad, y con 128 dimensiones ya no aportan.
3. **IVF, listas invertidas.** Lo que se usó. k-medias y recorrido de las celdas más cercanas.
4. **HNSW, grafo navegable en capas.** Lo que se usó. Más recall por milisegundo, más memoria y más tiempo de construcción.
5. **IVFPQ, listas invertidas con cuantización por producto.** Parte el vector en subvectores y sustituye cada uno por el índice de su centroide en un pequeño libro de códigos, con lo que un vector de 128 flotantes pasa a ocupar unos pocos bytes. Es lo que se usa cuando los vectores no caben en memoria. No se usa aquí por dos razones: 41 MB caben de sobra, y añadiría una **segunda fuente de error**, la de la compresión, que se confundiría con el error del índice, que es justo lo que esta parte quiere medir por separado.
6. **Árboles de proyección aleatoria, al estilo Annoy.** Construye un bosque de árboles que parten el espacio con hiperplanos aleatorios. Más simple que HNSW y en general peor en recall por milisegundo a este tamaño, pero con la ventaja de poder cargarse en memoria compartida desde disco.
7. **LSH para coseno.** Es exactamente SimHash, que ya está implementado en la Parte II. Para vectores densos y este rango de tamaños, IVF y HNSW lo dominan en recall por milisegundo; LSH brilla cuando se necesita una garantía probabilística explícita o un esquema distribuible, no cuando se quiere la menor latencia en un nodo.
8. **Fuerza bruta en tarjeta gráfica.** FAISS la soporta y a este volumen sería competitiva con cualquier índice. No se usa porque el entorno del proyecto es solo de procesador, y porque la pregunta del curso es sobre estructuras de índice y no sobre acelerar la fuerza bruta.

### Para la representación vectorial

1. **TF-IDF disperso directo.** No sirve: FAISS necesita vectores densos de dimensión fija.
2. **TF-IDF más SVD truncada.** Lo que se usó. Aplicada a TF-IDF esto se llama análisis semántico latente, y además de reducir la dimensión acerca términos que coocurren.
3. **Análisis de componentes principales.** Es casi lo mismo, pero centra los datos, cosa que sobre una matriz dispersa la vuelve densa y no cabría en memoria. La SVD truncada funciona sin centrar.
4. **Proyección aleatoria.** Más barata y con la garantía de Johnson y Lindenstrauss de que las distancias se conservan aproximadamente. Es una alternativa razonable y se descarta porque la SVD conserva mejor la estructura con la misma dimensión de llegada, y el costo de calcularla una vez es asumible.
5. **Incrustaciones de un modelo de lenguaje.** Darían similitud semántica de verdad y no de vocabulario. Se descartan a propósito: introducirían un componente que no se puede explicar línea por línea en una sustentación, y el curso trata de estructuras de índice y no de representaciones aprendidas.
6. **Normalizar a norma uno.** No es una alternativa sino un requisito del diseño: con norma uno el producto interno **es** el coseno, lo que permite usar el índice de producto interno y leer el resultado directamente.

### Para medir

1. **Un solo régimen.** Es lo que se hace casi siempre y es lo que nos dio un falso multiplicador de 28. La conclusión cambia según el régimen, de modo que presentar uno solo sería engañoso.
2. **Media en lugar de mediana.** La media se mueve con una pausa del recolector de basura o con cualquier otro proceso de la máquina. Se usa la mediana de doscientas consultas, tras descartar veinte de calentamiento.
3. **Todos los hilos en la consulta única.** Se descarta porque el arranque del grupo de hilos domina el tiempo de una consulta individual y vuelve la medición sensible a la carga de la máquina, hasta producir curvas no monótonas.

### Para distribuir

1. **Spark.** Descartado con argumento, no por comodidad: un nodo, 41 MB en memoria, y la operación es búsqueda en índice y no agregación. Distribuirlo añadiría barajado y serialización sin ganar nada. Si la base creciera cien veces, lo que se haría es **fragmentar** el índice por nodo y consultar todos los fragmentos en paralelo, combinando los diez mejores de cada uno, que es un patrón de dispersar y reunir y no un barajado.

## 5. Preguntas probables y qué responder

**¿Cuál de los dos números de latencia es el correcto?** Los dos, para preguntas distintas. El error está en comparar un lado medido en lote contra el otro medido consulta a consulta, que es lo que nos dio un falso multiplicador de 28 la primera vez.

**¿Dónde conviene dejar de subir nprobe?** En la rodilla de la curva. De 16 a 64 el recall sube un punto y el trabajo se cuadruplica.

**¿Entonces HNSW es mejor que IVF?** En latencia de consulta sí, con este volumen. Pero compra esa latencia con memoria y con tiempo de construcción, y con un índice que admite peor las inserciones masivas. Si la base cambia todo el tiempo o la memoria es escasa, IVF sigue siendo la elección.

**¿Cuál representación es la correcta?** Ninguna en abstracto. Depende de si el parecido que se busca es ortográfico o de vocabulario.

**¿Para este proyecto el índice aproximado era necesario?** A nuestro volumen y en uso por lotes, no, y preferimos decirlo. Lo justifica el uso en línea y el escenario de más volumen, y eso está medido.

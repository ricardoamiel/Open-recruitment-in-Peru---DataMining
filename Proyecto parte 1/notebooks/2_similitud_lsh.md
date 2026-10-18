# Notebook 2. Similitud: shingling, Jaccard, MinHash, LSH y SimHash

Guía de estudio del notebook [2_similitud_lsh.ipynb](2_similitud_lsh.ipynb). El porqué de cada elección está en [docs/JUSTIFICACION.md](../docs/JUSTIFICACION.md), sección Parte II.

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

Qué significa cada campo, cada código CUBSO y cada etiqueta del dato está en [docs/GLOSARIO.md](../docs/GLOSARIO.md).

## 1. Qué responde esta parte

La Parte I dejó dos cosas abiertas. Primero, hay procesos cuyo objeto contractual es prácticamente el mismo texto repetido entre entidades. Segundo, hay proveedores que aparecen como distintos siendo la misma empresa escrita de otra forma.

Ninguna de las dos se detecta comparando todos los pares: con 177.398 procesos son más de quince mil millones de comparaciones. El problema es cuadrático y la parte entera trata de convertirlo en uno aproximadamente lineal sin perder lo que importa.

Spark es obligatorio aquí. Las firmas y el agrupamiento por bandas corren sobre RDD, que es donde el estilo imperativo gana al declarativo.

## 2. El esquema completo, en una frase

Texto del objeto, pasado a **conjunto de k-shingles**, resumido en una **firma MinHash** de 128 enteros, partida en **bandas** que generan candidatos, y los candidatos pasan por una **verificación exacta** de Jaccard. En paralelo, el mismo texto pasado a **TF-IDF** y resumido con **SimHash**, para comparar los dos esquemas de hashing sensible a la localidad.

## 3. Recorrido sección por sección

### Sección 1. Dos representaciones como conjunto

El dataset ofrece dos formas de ver un proceso como conjunto, y compararlas es en sí mismo un resultado.

| Representación | Elementos por proceso | Universo | Procesos vacíos |
| --- | --- | --- | --- |
| Shingles del objeto con k igual a 9 | 186,9 | 137.412 | 0 |
| Conjunto de códigos CUBSO | 0,94 | 654 | 270 de 2.000 |

La tabla decide. El conjunto CUBSO tiene menos de un elemento por proceso en promedio y 270 procesos vacíos, así que no sostiene una similitud discriminante: la Jaccard entre dos conjuntos de un elemento solo puede ser cero o uno. Los shingles del objeto sí la sostienen. El CUBSO se reserva para la Parte V, donde la canasta se redefine por entidad y mes.

**Qué es un k-shingle.** Es cada subcadena contigua de k caracteres del texto. El documento se representa por el **conjunto** de sus shingles, no por la lista: se pierde el orden global pero se conserva el orden local, porque cada shingle es un fragmento contiguo. Dos textos con las mismas palabras en distinto orden comparten pocos shingles si las fronteras caen distinto, que es lo que se quiere.

**Por qué shingles de caracteres y no de palabras.** Porque el objeto lo escribe a mano cada entidad y abundan los errores de digitación, las abreviaturas y los plurales. Los shingles de caracteres toleran eso; los de palabras no.

**La calibración de k.** Esta es la figura que más conviene saber defender porque documenta un resultado negativo.

| k | Shingles por documento | Fondo, mediana de pares no relacionados | Señal, percentil 99 |
| --- | --- | --- | --- |
| 3 | 153,7 | 0,1384 | 0,3010 |
| 5 | 179,4 | 0,0549 | 0,2023 |
| 7 | 186,0 | 0,0247 | 0,1490 |
| 9 | 187,1 | 0,0114 | 0,1152 |
| 11 | 186,5 | 0,0047 | 0,0911 |
| 13 | 185,3 | 0,0000 | 0,0733 |

Buscábamos un k óptimo y no existe: las dos curvas bajan juntas, así que ninguna métrica sobre pares aleatorios tiene un máximo interior, y construir una métrica que lo tuviera sería fabricar el resultado. Lo que se hace es **fijar un criterio explícito**: k debe ser lo bastante grande para que dos objetos no relacionados no compartan casi nada, en concreto que el fondo quede por debajo de 0,02. El primer k que lo cumple es 9.

Con k igual a 3 el fondo está en 0,138, es decir que dos textos cualesquiera ya se parecen un 14 por ciento solo por ser español administrativo. Y la elección no es crítica: el barrido de LSH da resultados muy parecidos con 7 y con 11. Esta es la **figura f16**.

### Sección 2. Jaccard exacta, la verdad de referencia

Sobre una muestra de 2.000 procesos se calculan los 1.999.000 pares. Esa muestra existe para una sola cosa: tener una verdad de referencia contra la que medir todo lo aproximado.

**Qué es Jaccard.** El tamaño de la intersección dividido entre el tamaño de la unión de los dos conjuntos. Va de 0, sin nada en común, a 1, idénticos.

**Cómo se calcula para dos millones de pares sin un bucle.** Con álgebra dispersa. Se arma una matriz binaria M de documentos por shingles, donde la celda vale uno si el documento contiene ese shingle. Entonces el producto M por M traspuesta da, en cada celda, el **tamaño de la intersección** de ese par. La unión sale de la identidad de inclusión y exclusión: tamaño de A más tamaño de B menos la intersección. Es una sola multiplicación de matrices en lugar de dos millones de operaciones de conjunto en Python.

La **figura f17** muestra la distribución, con el eje vertical en logaritmo porque la primera barra es tres órdenes de magnitud mayor que las demás y en escala lineal aplastaría la cola, que es la única parte interesante. Solo 42 pares de 1.999.000 superan 0,5, el 0,002 por ciento. Esa es la figura que justifica que LSH exista: comparar todos los pares para encontrar esa fracción es desperdicio.

### Sección 3. MinHash

**La propiedad que lo sostiene.** Para una permutación aleatoria del universo de shingles, la probabilidad de que dos conjuntos tengan el mismo elemento mínimo es exactamente su similitud de Jaccard. La intuición: mirando solo los elementos que están en la unión de los dos conjuntos, el mínimo es uniformemente alguno de ellos, y coincide si y solo si cae en la intersección, lo que ocurre con probabilidad igual a intersección sobre unión.

**Cómo se implementa sin permutar de verdad.** Permutar un universo de 137.412 shingles sería absurdo. En su lugar se usan funciones hash lineales de la forma a por x más b, módulo P, con P igual a 2 elevado a 31 menos 1, un primo de Mersenne. Cada par de coeficientes a y b sorteados define una permutación aproximada. La firma del conjunto es, para cada una de las n funciones, el mínimo de los valores hash de sus elementos.

Dos detalles de implementación que conviene saber explicar.

1. **El hash base es blake2b y no el de Python.** La función hash incorporada de Python viene aleatorizado por proceso, lo que haría irreproducibles las firmas y los buckets entre ejecuciones y, peor, entre el driver y los workers de Spark.
2. **P es un primo de Mersenne de 31 bits** para que el producto a por x quepa en un entero de 64 bits sin desbordar, lo que permite vectorizar con numpy: una sola matriz de n por tamaño del conjunto y un mínimo por fila, en vez de iterar en Python.

**Cuánto error tiene.** La firma estima Jaccard como la fracción de posiciones en que las dos firmas coinciden. El error es del orden de uno sobre la raíz de n.

| Funciones hash | Error medio observado | Cota uno sobre raíz de n | Bytes por documento |
| --- | --- | --- | --- |
| 32 | 0,0142 | 0,1768 | 256 |
| 64 | 0,0109 | 0,1250 | 512 |
| 128 | 0,0072 | 0,0884 | 1.024 |
| 256 | 0,0052 | 0,0625 | 2.048 |

La **figura f18** muestra las dos curvas en escala logarítmica doble y tienen la misma pendiente, lo que confirma la ley. La consecuencia práctica es dura: cuadruplicar las funciones hash solo divide el error entre dos. Se eligen **128** porque su error, 0,0072, es un orden de magnitud menor que el ancho de la banda de decisión de LSH, así que afinar más la estimación por debajo de la resolución con la que luego se decide no compra nada.

### Sección 4. LSH por bandas, en Spark

**Cómo funciona.** La firma de 128 enteros se parte en b bandas de r filas. Cada banda se resume en un hash, y dos documentos son candidatos si coinciden en el hash de **al menos una** banda. Solo los candidatos se verifican con Jaccard exacta.

La probabilidad de que un par con similitud real s sea candidato es uno menos, uno menos s elevado a r, elevado a b. Esa es la **curva S**.

1. La probabilidad de coincidir en una banda concreta es s elevado a r, porque la banda tiene r posiciones y todas deben coincidir.
2. La probabilidad de no coincidir en ninguna de las b bandas es, uno menos s elevado a r, elevado a b.
3. El complemento es la fórmula.

**El umbral.** La aproximación estándar del punto de inflexión es uno sobre b, elevado a uno sobre r. Aquí hay un error frecuente que conviene no cometer: en ese umbral la probabilidad **no vale un medio**. Vale uno menos, uno menos uno sobre b, elevado a b, que tiende a uno menos uno sobre e, alrededor de **0,63**. El umbral marca dónde la curva cambia de concavidad, no dónde vale la mitad. Lo verificamos numéricamente antes de escribirlo.

**Detalle de implementación.** Con r igual a 3 salen 42 bandas y sobran dos posiciones de las 128, porque 3 no divide a 128. La firma se recorta a b por r antes de partirla, y cada banda lleva su propia semilla de hash para que bandas distintas con el mismo contenido no colisionen entre sí.

**Por qué RDD y no DataFrame.** El agrupamiento por bandas es un flatMap que emite un par por banda, seguido de un groupByKey y de las combinaciones dentro de cada bucket. Expresar eso en SQL sería forzado. Además se filtran los buckets con más de 400 elementos: un bucket enorme no informa, solo produce combinaciones cuadráticas de basura.

**LSH es un generador de candidatos, no un clasificador.** Esta frase decide cómo se mide todo lo que sigue. Su salida pasa después por una verificación exacta que elimina **todos** los falsos positivos, de modo que la precisión antes de verificar no es una medida de calidad sino de cuánto trabajo queda. Las dos cifras que importan son el recall, porque un par perdido aquí se pierde para siempre, y el número de candidatos, porque es el costo de la verificación.

El barrido, con umbral buscado de 0,3 y 263 pares verdaderos:

| Configuración | Candidatos | Falsos positivos | Falsos negativos | Recall | Pares a verificar |
| --- | --- | --- | --- | --- | --- |
| b=128, r=1 | 993.962 | 993.699 | 0 | 1,0000 | 49,72 % |
| b=64, r=2 | 171.259 | 170.997 | 1 | 0,9962 | 8,57 % |
| b=42, r=3 | 32.337 | 32.106 | 32 | 0,8783 | 1,62 % |
| b=32, r=4 | 1.177 | 1.051 | 137 | 0,4791 | 0,06 % |
| b=25, r=5 | 139 | 64 | 188 | 0,2852 | 0,007 % |
| b=21, r=6 | 59 | 18 | 222 | 0,1559 | 0,003 % |
| b=16, r=8 | 24 | 0 | 239 | 0,0913 | 0,001 % |

Las dos figuras que salen de aquí son la **f19**, la curva S de cada configuración, y la **f20**, recall contra costo de verificación.

**Por qué no se usa F1.** Lo intentamos primero con F1 y seleccionaba una configuración con recall por debajo de la mitad, que para un generador de candidatos es inservible. F1 trata los dos errores como equivalentes y aquí no lo son: un falso positivo lo elimina la verificación posterior, así que es trabajo; un falso negativo se pierde para siempre. La configuración elegida es **b igual a 64 y r igual a 2**, que recupera el 99,6 por ciento de los pares verdaderos verificando solo el 8,6 por ciento de los pares.

### Sección 5. SimHash frente a MinHash

**Qué es SimHash.** Otro esquema de hashing sensible a la localidad, pero para similitud **coseno** en lugar de Jaccard. Se sortean tantos hiperplanos aleatorios como bits quiera tener la firma. Cada bit dice de qué lado del hiperplano cae el vector del documento. La probabilidad de que dos documentos coincidan en un bit es uno menos el ángulo entre ellos dividido entre pi, de modo que la distancia de Hamming entre las dos firmas estima el ángulo y, con él, el coseno.

En la implementación, en lugar de sortear hiperplanos explícitos se usa el hash de cada término: cada bit del hash indica el signo con que ese término contribuye a esa coordenada, y se acumula sumando el peso del término con ese signo. Al final cada coordenada se reduce a un bit según su signo.

**Por qué los dos y no uno.** No son intercambiables. MinHash trata un conjunto **sin pesos**; SimHash respeta el peso de cada término. En este dataset la palabra adquisición aparece en casi todos los objetos y el nombre de un equipo médico en muy pocos. MinHash las trata igual; TF-IDF con SimHash no.

**TF-IDF.** Term Frequency por Inverse Document Frequency. Pesa cada término por lo frecuente que es en el documento y lo castiga por lo frecuente que es en la colección, de modo que lo que aparece en todas partes pesa poco.

El resultado, en la **figura f21** sobre 2.091 pares: SimHash correlaciona **0,734** con el coseno de TF-IDF y **0,694** con Jaccard. Cada esquema estima la métrica para la que fue diseñado.

Dos cosas que conviene anticipar.

1. **Los pares están estratificados por similitud real, no elegidos al azar.** Con pares aleatorios casi todos tienen similitud cero y la correlación medida sería ruido, no una propiedad de SimHash.
2. **Ninguna correlación llega a uno, y el motivo es la resolución.** Con 64 bits la similitud estimada solo puede tomar 65 valores distintos, lo que produce las bandas horizontales visibles en los dos paneles. Subir a 128 bits afinaría la escala a costa del doble de memoria por firma.

### Sección 6. Contraste con Spark MLlib

Hay una **diferencia de contrato** que invalida la comparación ingenua. El método approxSimilarityJoin de MLlib no devuelve candidatos: genera los candidatos internamente y ya les aplica la verificación exacta, de modo que su salida son pares verificados. Comparar sus pares verificados contra los candidatos crudos de la implementación propia daría una ventaja aparente enorme a MLlib que es solo de contabilidad.

Para que la comparación sea válida, a los candidatos propios se les aplica la misma verificación exacta.

| Configuración | Candidatos crudos | Pares verificados | Recall |
| --- | --- | --- | --- |
| propia, b=64 y r=2, verificada | 171.259 | 262 | 0,9962 |
| MLlib con 8 tablas hash | no expuesto | 252 | 0,9582 |
| MLlib con 16 tablas hash | no expuesto | 261 | 0,9924 |
| MLlib con 32 tablas hash | no expuesto | 261 | 0,9924 |

Con el mismo contrato las dos producen pares verificados correctos, y lo que queda es una diferencia de configuración y no de corrección. MLlib usa tablas hash independientes, que equivale a bandas de una sola fila, y eso le da un umbral efectivo muy bajo: atrapa casi todo a costa de generar muchos más candidatos internos, que no expone. La implementación propia permite elegir explícitamente ese punto con b y r, que es lo que el enunciado pide analizar.

**La verificación que importa.** Ningún par declarado por la implementación propia resulta falso tras la comprobación exacta: los 262 superan el umbral. Si el agrupamiento por bandas tuviera un error conceptual aparecerían pares que no lo superan, y no aparece ninguno. Y el recall queda al nivel de MLlib, 262 de 263 pares verdaderos frente a 261.

### Sección 7. Un caso concreto

Los cinco pares de mayor similitud. Los de la misma entidad son reconvocatorias del mismo objeto. El interesante es la Municipalidad Distrital de Tambo de Mora contra la Municipalidad Distrital de San Bartolo, dos municipalidades distintas con el mismo pliego del programa Vaso de Leche, una de 2024 y otra de 2023.

**Qué autoriza a concluir esto y qué no.** Un par con similitud alta dice que dos procesos describen casi lo mismo. Eso puede reflejar una plantilla compartida entre entidades, una necesidad genuinamente idéntica o un proceso fraccionado. Es una hipótesis que señala dónde mirar, no una conclusión sobre la conducta de nadie.

### Sección 8. A escala completa

Todo lo anterior corre sobre 2.000 procesos porque ahí se puede calcular la verdad de referencia. El método, en cambio, se aplica al conjunto entero en Spark: 166.439 procesos con objeto suficientemente largo, 13.850.887.141 pares posibles, 28.161.739 candidatos. Una reducción de **492 a 1**.

## 4. Alternativas para cada decisión, explicadas

### Para encontrar pares parecidos sin compararlos todos

1. **Fuerza bruta.** Quince mil millones de comparaciones. Es la cota contra la que se mide todo, y es lo que la figura f17 demuestra que sería desperdicio: solo el 0,002 por ciento de los pares supera 0,5.
2. **Bloqueo, o vecindario ordenado.** Se ordenan los documentos por una clave, por ejemplo las primeras letras del objeto, y solo se comparan los que caen en la misma ventana. Es barato y es lo que se hacía antes de LSH. El problema es que es frágil: un error de digitación en la primera letra manda el documento a otro bloque y se pierde para siempre, y no hay forma de calcular la probabilidad de que eso pase. LSH tiene la misma idea pero con una **curva de probabilidad calculable**, que es lo que permite elegir el punto de operación a conciencia.
3. **Filtrado por prefijo, al estilo PPJoin.** Ordena los elementos del conjunto por frecuencia global y usa el hecho de que dos conjuntos con Jaccard alta deben compartir algo de su prefijo. Da resultados exactos sin falsos negativos y es más eficiente que la fuerza bruta, pero su costo depende mucho de la distribución y no se paraleliza tan limpiamente como el agrupamiento por bandas.
4. **Índice invertido con filtro de longitud.** Exacto y bueno cuando los conjuntos son pequeños. Aquí cada documento tiene 187 shingles y el universo es de 137.412, de modo que las listas de posteo serían enormes.
5. **Lo que se hizo.** LSH por bandas sobre firmas MinHash, porque es lo único de la lista que ofrece una curva S con parámetros explícitos y se expresa de forma natural como flatMap más groupByKey en Spark.

### Para resumir un conjunto en una firma

1. **Permutaciones reales del universo.** Es la definición del algoritmo y es inviable: permutar 137.412 shingles por cada una de las 128 funciones.
2. **MinHash con hashes lineales.** Lo que se usó: a por x más b, módulo un primo de Mersenne. Cada par de coeficientes es una permutación aproximada.
3. **Hashing de una sola permutación con densificación.** Una sola función hash y el universo partido en n franjas, tomando el mínimo de cada franja. Cuesta una pasada en lugar de n, pero hay que tratar las franjas vacías con un esquema de densificación que complica la explicación. Con 128 hashes vectorizados en numpy no hacía falta.
4. **Bocetos de los k mínimos, o bottom-k.** Se queda con los k valores hash más pequeños del conjunto entero, en vez de el mínimo de k funciones. Estima mejor para el mismo tamaño de firma, pero no se parte en bandas de forma natural, que es justo lo que LSH necesita.
5. **Minwise hashing de b bits.** Guarda solo los b bits bajos de cada mínimo, de modo que la firma ocupa mucho menos a cambio de más colisiones. Es la optimización evidente si la memoria apretara; con 1 KiB por documento no aprieta.

### Para la representación del documento

1. **Shingles de palabras.** Más interpretables y más baratos, pero frágiles ante errores de digitación, abreviaturas y plurales, que abundan porque el objeto lo escribe cada entidad a mano.
2. **Shingles de caracteres.** Lo que se usó, con k igual a 9 fijado por criterio.
3. **El conjunto de códigos CUBSO.** Medido y descartado: 0,94 elementos por proceso y 270 procesos vacíos de 2.000.
4. **TF-IDF.** Sí se usa, pero para SimHash y para la Parte III, porque es una representación **con pesos** y Jaccard no los admite.

### Para la métrica de similitud

1. **Jaccard.** Para conjuntos sin peso. Es la que estima MinHash.
2. **Coseno.** Para vectores con peso. Es la que estima SimHash, y la de la Parte III.
3. **Distancia de edición, o Levenshtein.** Es la métrica natural para errores de digitación, y se descarta por dos motivos: es cuadrática en la longitud de los textos, y no se conoce una familia de funciones sensibles a la localidad para ella, de modo que no admite el truco de LSH. Los shingles de caracteres son la forma práctica de capturar parte de esa tolerancia dentro de una métrica que sí la admite.
4. **Distancia de Hamming.** Es la que se usa **entre firmas SimHash**, no entre documentos.

### Para elegir bandas y filas

1. **F1 sobre los candidatos crudos.** Fue el primer intento y seleccionaba una configuración con recall por debajo de la mitad. Trata los dos errores como equivalentes y aquí no lo son.
2. **Precisión.** Peor todavía: premia a la configuración que menos propone.
3. **Fijar el umbral teórico y despejar.** Se puede, y de hecho la fórmula está implementada, pero el umbral teórico es una aproximación y conviene comprobar con el barrido lo que realmente ocurre.
4. **Lo que se hizo.** Recall contra porcentaje de pares a verificar, eligiendo la configuración de menor costo entre las que superan el 95 por ciento de recall.

### Para el contraste con una biblioteca

1. **Comparar los candidatos propios contra la salida de MLlib.** Inválido: son contratos distintos, porque MLlib ya verifica internamente.
2. **Lo que se hizo.** Aplicar a los candidatos propios la misma verificación exacta, y entonces comparar recall contra recall.

## 5. Preguntas probables y qué responder

**¿Cuál es el criterio para k y qué pasa si se elige otro?** El criterio es que el fondo de pares no relacionados quede por debajo de 0,02, y el primer k que lo cumple es 9. No es crítico: con 7 y con 11 el barrido de LSH da resultados muy parecidos.

**¿El umbral de LSH es donde la probabilidad vale un medio?** No. La fórmula marca el punto de inflexión, donde la probabilidad vale uno menos uno sobre e, unos 0,63.

**¿Por qué 128 funciones hash y no más?** Porque el error con 128 ya es un orden de magnitud menor que el ancho de la banda de decisión de LSH; gastar más afina una estimación por debajo de la resolución con la que se decide.

**¿Por qué ninguna correlación de SimHash llega a uno?** Por resolución: con 64 bits solo hay 65 valores posibles de similitud estimada.

**¿Cómo saben que la implementación propia es correcta?** Porque todos sus pares verificados superan el umbral y porque coinciden con los de MLlib bajo el mismo contrato. Las dos comprobaciones hacen falta: la primera descarta falsos, la segunda descarta omisiones.

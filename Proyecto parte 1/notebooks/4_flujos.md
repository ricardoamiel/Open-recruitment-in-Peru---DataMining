# Notebook 4. Minería de flujos: muestreo, Bloom Filter, Count-Min Sketch y DGIM

Guía de estudio del notebook [4_flujos.ipynb](4_flujos.ipynb). El porqué de cada elección está en [docs/JUSTIFICACION.md](../docs/JUSTIFICACION.md), sección Parte IV.

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

Qué significa cada campo, cada código CUBSO y cada etiqueta del dato está en [docs/GLOSARIO.md](../docs/GLOSARIO.md).

## 1. La restricción que da sentido a todo

Los 177.398 procesos se recorren en orden de convocatoria, uno a uno, y cada uno se ve **una sola vez**. No se puede volver atrás ni guardar el flujo completo. Esa es la diferencia entre un flujo y una tabla, y es lo que obliga a usar estructuras de resumen.

El flujo es simulado a partir del Parquet, ordenado por fecha, y va del 4 de enero de 2023 al 30 de diciembre de 2025. Hay que ser honesto en esto: no hay una fuente en tiempo real, se simula el régimen de una sola pasada para poder medir lo que el enunciado pide.

**Spark es opcional aquí y no se usa.** El recorrido es inherentemente secuencial y con estado: cada elemento modifica una estructura que el siguiente consulta. Distribuirlo exigiría combinar resúmenes parciales, lo que se puede hacer con Bloom y Count-Min porque son aditivos, pero no con DGIM sin reescribirlo. Spark se usa solo para ordenar y materializar el flujo.

**Qué hereda de la Parte I.** La pregunta abierta del suelo de procesos sin competencia. Sobre un flujo esa pregunta se convierte en si el suelo está subiendo o bajando ahora mismo, y eso es un conteo sobre una ventana reciente, que es exactamente para lo que existe DGIM. Y el filtro de Bloom consulta el identificador del proveedor, que es la recurrencia que la figura f10 de la Parte I puso sobre la mesa.

## 2. Recorrido sección por sección

### Sección 1. Tres formas de muestrear

Tres técnicas que suelen confundirse. La diferencia no es de eficiencia sino de **qué preguntas sobreviven a la muestra**.

| Técnica                                | Eventos | Proveedores | Proveedores completos |
| --------------------------------------- | ------- | ----------- | --------------------- |
| Por evento, 10 por ciento               | 17.849  | 11.065      | 46,9 %                |
| Por clave, 10 por ciento de proveedores | 45.781  | 6.814       | 100 %                 |
| Reservoir de 17.739 elementos           | 17.739  | 10.914      | 47,5 %                |

1. **Muestreo por evento.** Cada evento entra con probabilidad fija e independiente. Conserva proporciones globales y destroza la integridad por entidad.
2. **Muestreo por clave.** Se sortea la **entidad**, no el evento, hasheando la clave y comparando contra el umbral. Si la entidad entra, entran todos sus eventos. Conserva integridad por entidad y pierde uniformidad sobre eventos.
3. **Reservoir sampling.** Mantiene una muestra uniforme de tamaño fijo k sin saber cuánto durará el flujo. Los primeros k elementos entran; el elemento número i, con i mayor que k, entra con probabilidad k sobre i y desaloja a uno al azar.

**Por qué el reservoir es uniforme, demostrado.** Esta es la parte bonita del algoritmo y conviene saber contarla, porque el enunciado del algoritmo parece magia hasta que se ve la inducción.

La afirmación es que, tras procesar i elementos, cada uno de los i está en la muestra con probabilidad k sobre i.

1. **Caso base.** Con i igual a k, los k primeros entraron todos, de modo que cada uno está con probabilidad k sobre k, que es uno.
2. **Paso inductivo.** Supongamos que vale tras i menos uno elementos, y llega el elemento i. Entra con probabilidad k sobre i, que es lo que queríamos para él. Para un elemento viejo x, que estaba con probabilidad k sobre i menos uno, hay que calcular la probabilidad de que sobreviva. Si el elemento i se rechaza, cosa que ocurre con probabilidad uno menos k sobre i, x sobrevive seguro. Si el elemento i se acepta, con probabilidad k sobre i, desaloja a una de las k posiciones elegida al azar, de modo que x sobrevive con probabilidad k menos uno, sobre k.
3. **La cuenta.** La probabilidad de que x siga dentro es k sobre i menos uno, multiplicado por la suma de los dos casos, que es uno menos k sobre i, más k sobre i por k menos uno sobre k. Esa suma vale uno menos k sobre i más k menos uno sobre i, es decir uno menos uno sobre i, que es i menos uno sobre i. Y entonces k sobre i menos uno, por i menos uno sobre i, es **k sobre i**, que es lo que había que probar.

La consecuencia práctica es que el reservoir no necesita conocer el largo del flujo de antemano, que es exactamente lo que un muestreo del diez por ciento sí necesitaría para producir una muestra de tamaño acotado. Con un flujo sin final declarado, el muestreo por evento tiene memoria no acotada; el reservoir tiene memoria exactamente k.

**Por qué importa que una entidad quede completa.** Porque cambia qué preguntas admite la muestra. Sobre muestreo por evento, la pregunta cuántas adjudicaciones acumuló este proveedor da una respuesta **falsa**, no imprecisa: le faltan filas, y el conteo es sistemáticamente bajo. Con muestreo por clave la respuesta es exacta dentro de las entidades elegidas. Es la **figura f27**.

El reservoir se comporta como el muestreo por evento en integridad, lo cual es esperado: su garantía es de uniformidad sobre eventos, no de integridad por entidad.

**La figura f28 verifica el reservoir.** El invariante es que, tras ver i elementos, cada uno está en la muestra con probabilidad k sobre i, y eso implica que la composición de la muestra debe reproducir la del flujo. La desviación máxima observada entre las dos distribuciones de métodos es de 0,06 puntos porcentuales.

Si preguntan para qué verificar algo ya demostrado: para distinguir un error de teoría de un error de implementación. La demostración garantiza el algoritmo, no nuestro código. Esta figura es la que detecta si el índice aleatorio está mal calculado, que es el fallo típico al escribir reservoir.

### Sección 2. Bloom Filter

**La pregunta.** Ha aparecido antes este proveedor, sin mantener el conjunto de todos los vistos.

**Cómo funciona.** Un arreglo de m bits, todos en cero, y k funciones hash. Insertar un elemento pone en uno las k posiciones que le corresponden. Consultar devuelve sí solo si las k posiciones están en uno.

**Por qué los falsos negativos son imposibles.** Por construcción, no por suerte: insertar solo enciende bits y nunca los apaga, así que si un elemento se insertó, sus k posiciones siguen encendidas. Esa asimetría es lo que lo hace útil como primer filtro: **un no es definitivo**.

**Por qué puede haber falsos positivos.** Porque las k posiciones de un elemento ausente pueden haber sido encendidas por otros elementos.

**El dimensionamiento.** Para n elementos y tasa objetivo p, el tamaño óptimo es m igual a menos n por el logaritmo de p dividido entre el logaritmo de 2 al cuadrado, y el número óptimo de funciones hash es k igual a m sobre n por el logaritmo de 2. La tasa teórica es uno menos e elevado a menos k n sobre m, todo elevado a k.

**Un detalle de implementación que conviene saber.** No se calculan k hashes independientes, sino **doble hash de Kirsch y Mitzenmacher**: dos hashes h1 y h2, y la posición i es h1 más i por h2, módulo m. Se demuestra que tiene el mismo comportamiento asintótico que k funciones independientes y cuesta dos hashes en lugar de k.

| Tasa objetivo | Bits    | Funciones hash | Memoria   | Tasa observada | Falsos negativos |
| ------------- | ------- | -------------- | --------- | -------------- | ---------------- |
| 0,200         | 226.148 | 2              | 27,6 KiB  | 0,0785         | 0                |
| 0,100         | 323.544 | 3              | 39,5 KiB  | 0,0306         | 0                |
| 0,050         | 420.940 | 4              | 51,4 KiB  | 0,0126         | 0                |
| 0,010         | 647.088 | 7              | 79,0 KiB  | 0,0017         | 0                |
| 0,001         | 970.631 | 10             | 118,5 KiB | 0,0001         | 0                |

La **figura f29** muestra que la curva observada sigue a la teórica, lo que valida la implementación. Lo que decide es la comparación con la alternativa exacta: guardar los 67.510 identificadores en un conjunto de Python costaría del orden de 1.582 KiB, y el filtro con 1 por ciento de error ocupa 79,0, unas 20 veces menos.

La tasa observada es menor que la teórica porque la teórica se evalúa con el filtro ya lleno, mientras que las consultas ocurren mientras se va llenando.

### Sección 3. Count-Min Sketch

**La pregunta.** Cuántas veces apareció cada código CUBSO, sin guardar un diccionario.

**Cómo funciona.** Una tabla de d filas por w columnas, inicialmente en cero, y d funciones hash, una por fila. Al llegar una clave se incrementa una celda en cada fila. Para estimar se toma el **mínimo** de las d celdas.

**Por qué el mínimo y por qué nunca subestima.** Cada celda acumula la clave más todas las que colisionan con ella, de modo que cada celda es una cota superior del conteo real. El mínimo de cotas superiores sigue siendo una cota superior, y es la más ajustada de las d.

**La garantía.** El error está acotado por epsilon por el total de eventos con probabilidad uno menos delta, donde w es e sobre epsilon y d es el logaritmo de uno sobre delta. El **ancho controla el error** y la **profundidad controla la probabilidad** de excederlo.

| Epsilon | Ancho  | Profundidad | Memoria     | Error medio | Error máximo | Cota teórica | Subestimaciones |
| ------- | ------ | ----------- | ----------- | ----------- | ------------- | ------------- | --------------- |
| 0,0100  | 272    | 7           | 14,9 KiB    | 97,24       | 480           | 1.320         | 0               |
| 0,0050  | 544    | 7           | 29,8 KiB    | 30,70       | 319           | 660           | 0               |
| 0,0010  | 2.719  | 7           | 148,7 KiB   | 0,57        | 19            | 132           | 0               |
| 0,0005  | 5.437  | 7           | 297,3 KiB   | 0,04        | 8             | 66            | 0               |
| 0,0001  | 27.183 | 7           | 1.486,6 KiB | 0,00        | 2             | 13            | 0               |

La **figura f30** muestra que el error observado queda siempre por debajo de la cota y que nunca hay subestimaciones, que es exactamente lo que garantiza tomar el mínimo.

**Aquí hay un resultado incómodo que se reporta igual.** El diccionario exacto de 4.664 códigos ocupa del orden de 273 KiB, y para bajar el error a dos apariciones el sketch necesita 1.487. A este volumen el Count-Min **no compensa**. Compensa cuando el universo de claves es mucho mayor que la memoria disponible, y nuestro universo de códigos CUBSO no lo es. Se incluye porque el curso lo pide y porque medir cuándo una estructura no conviene también es resultado.

### Sección 4. Por qué hacen falta los dos, y no uno de los dos

Es la pregunta natural: una frecuencia mayor que cero es una respuesta de pertenencia, entonces para qué un Bloom.

La respuesta se mide en lugar de afirmarse. El Count-Min se dimensiona resolviendo **su propia fórmula de colisión**, no eligiendo parámetros a ojo: un elemento ausente se declara presente solo si las d filas tienen su celda ocupada, y con n claves en w columnas una celda está ocupada con probabilidad uno menos e elevado a menos n sobre w, así que hay que resolver esa expresión elevada a d igual a la tasa objetivo, y elegir la combinación de menor memoria.

| Estructura       | Responde    | Memoria     | Tasa de falsos positivos |
| ---------------- | ----------- | ----------- | ------------------------ |
| Bloom Filter     | pertenencia | 79,0 KiB    | 0,00172                  |
| Count-Min Sketch | frecuencia  | 5.059,6 KiB | 0,00167                  |

A igual tasa de error el Count-Min necesita **64 veces más memoria**, y la razón es estructural: guarda un contador de ocho bytes donde al Bloom le basta un bit. Es la **figura f31**.

Conviene contar que la primera versión de esta figura daba lo contrario, porque habíamos dimensionado el Count-Min a ojo, y encontrarlo fue lo que nos obligó a derivar la fórmula.

### Sección 5. DGIM

**La pregunta.** Cuántos de los últimos N procesos tuvieron un solo postor. El flujo de bits es exactamente el indicador de postor único que la Parte I dejó abierto.

**Cómo funciona.** Se mantienen **cubos**, cada uno con una marca de tiempo y un tamaño que es potencia de dos, y a lo más r cubos de cada tamaño, con r igual a 2. Cuando llega un uno se crea un cubo de tamaño uno; si hay más de r cubos del mismo tamaño, los dos más antiguos se fusionan en uno del doble de tamaño, que hereda la marca de tiempo del más reciente de los dos. Los cubos que salen de la ventana se descartan.

**Cómo estima.** Suma el tamaño de todos los cubos vivos **menos el más antiguo, del que cuenta solo la mitad**, porque de ese cubo no se sabe qué parte cae todavía dentro de la ventana.

**Por qué la memoria es logarítmica.** Hay a lo más r cubos de cada tamaño y los tamaños son potencias de dos hasta N, de modo que hay del orden del logaritmo de N cubos, cada uno con una marca de tiempo de del orden del logaritmo de N bits. De ahí el logaritmo al cuadrado.

**La cota de error.** El único cubo del que se duda es el más antiguo, y su tamaño es a lo más la mitad del conteo, de modo que el error relativo está acotado por uno sobre r. Con r igual a 2 la cota es el 50 por ciento, y subiendo r baja a uno sobre r menos uno, a cambio de más memoria.

| Ventana | Exacto | DGIM   | Error  | Cubos | Memoria DGIM | Memoria exacta | Días cubiertos |
| ------- | ------ | ------ | ------ | ----- | ------------ | -------------- | --------------- |
| 500     | 200    | 193    | 3,5 %  | 10    | 160 B        | 62 B           | 25              |
| 5.000   | 879    | 793    | 9,8 %  | 14    | 224 B        | 625 B          | 61              |
| 20.000  | 2.498  | 2.841  | 13,7 % | 16    | 256 B        | 2.500 B        | 138             |
| 50.000  | 5.959  | 7.449  | 25,0 % | 18    | 288 B        | 6.250 B        | 304             |
| 150.000 | 18.043 | 17.689 | 2,0 %  | 20    | 320 B        | 18.750 B       | 902             |

La **figura f32** muestra que el peor error relativo observado es del 25 por ciento, muy por debajo de la cota teórica del 50. La **figura f33** muestra las dos curvas de memoria divergiendo: multiplicar la ventana por 300 multiplica la memoria exacta por lo mismo y los cubos pasan solo de 10 a 20.

**Un matiz que conviene decir.** Con ventanas pequeñas DGIM **pierde**: con N igual a 500 usa 160 bytes frente a 62 del conteo exacto, porque cada cubo guarda una marca de tiempo y eso cuesta más que unos pocos bits. El cruce aparece alrededor de los primeros miles de elementos. Afirmar que una estructura sublineal siempre gana es el error que esta figura evita.

### Sección 6. DGIM frente a reservoir

Se confunden porque ambos son resúmenes de un flujo con memoria acotada, pero responden a preguntas ortogonales. El reservoir da una muestra uniforme de **todo** el flujo, sin noción de recencia. DGIM responde solo sobre los últimos N elementos y olvida el resto por construcción.

| Método            | Estimación | Memoria  | Responde la pregunta de ventana | Error  |
| ------------------ | ----------- | -------- | ------------------------------- | ------ |
| Conteo exacto      | 2.498       | 2.500 B  | sí                             | 0 %    |
| DGIM               | 2.841       | 256 B    | sí                             | 13,7 % |
| Reservoir filtrado | 2.820       | 32.000 B | no                              | 12,9 % |

El reservoir puede aproximar la pregunta de ventana solo descartando casi toda su muestra, y lo hace con más memoria y más error. A la inversa, DGIM no puede responder qué proporción de todo el histórico tuvo un solo postor, porque ya lo olvidó. Por eso se implementan los dos.

### Sección 7. Cuánto cuesta cada estructura en tiempo

El enunciado pide analizar precisión, memoria y tiempo. Las dos primeras ya están medidas; esta sección añade la tercera, que el discurso habitual sobre estas estructuras suele omitir.

| Estructura                            | Elementos | Microsegundos por elemento |
| ------------------------------------- | --------- | -------------------------- |
| Conjunto exacto de Python, referencia | 146.025   | 0,08                       |
| DGIM con ventana de 20.000            | 177.398   | 0,51                       |
| Muestreo por clave                    | 177.398   | 0,93                       |
| Reservoir sampling                    | 177.398   | 1,10                       |
| Bloom Filter                          | 146.025   | 7,35                       |
| Count-Min Sketch                      | 132.091   | 7,74                       |

El filtro de Bloom cuesta unas 92 veces más tiempo por elemento que el conjunto exacto de Python, porque calcula varias funciones hash donde el conjunto nativo calcula una y está implementado en C.

**La conclusión honesta, que es la que hay que decir:** estas estructuras **no ahorran tiempo**. Cambian memoria por tiempo y por un error acotado, y se eligen cuando la memoria es el recurso escaso. Presentarlas como una mejora en todos los ejes sería falso. Es la **figura f38**.

### Sección 8. Las cinco estructuras, lado a lado

La tabla es el entregable de la parte: no cuál es mejor, sino qué pregunta responde cada una y qué cuesta.

| Estructura         | Qué pregunta responde                  | Memoria                               | Error                                                      | Por qué se usa                                |
| ------------------ | --------------------------------------- | ------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------- |
| Muestreo por clave | métricas por entidad sobre una muestra | proporcional a la fracción de claves | ninguno dentro de las claves elegidas                      | la única que conserva entidades completas     |
| Reservoir sampling | proporciones sobre todo el flujo        | k elementos, fija y conocida          | 0,06 puntos de desviación                                 | no necesita conocer el largo del flujo         |
| Bloom Filter       | apareció antes este proveedor          | 79,0 KiB para 67.510 claves           | 0,17 por ciento de falsos positivos, cero falsos negativos | un bit por posición, imbatible en pertenencia |
| Count-Min Sketch   | cuántas veces apareció cada ítem     | 149 KiB                               | nunca subestima, máximo 19 apariciones                    | única que da frecuencias sin diccionario      |
| DGIM               | cuántos en los últimos N elementos    | 20 cubos para N igual a 150.000       | 25 por ciento observado, cota teórica 50                  | única con noción de recencia                 |

## 3. Por qué cada estructura y no la otra

Las preguntas del tipo si usan DGIM, por qué también reservoir, o por qué no solo uno de los dos, son las más probables. La respuesta corta es que cada una responde una pregunta que la otra no puede responder. La respuesta larga, pareja por pareja:

**DGIM frente a reservoir.** DGIM responde cuántos unos hay en los últimos N elementos. El reservoir responde qué proporción tiene el flujo entero. El reservoir no tiene noción de recencia: un evento de 2023 tiene la misma probabilidad de estar en la muestra que uno de 2025. Si se le fuerza la pregunta de ventana filtrando su muestra por posición, quedan 234 elementos de 2.000 y el resultado cuesta 32.000 bytes con 12,9 por ciento de error, frente a 256 bytes y 13,7 por ciento de DGIM. En sentido contrario, DGIM no puede responder qué proporción de todo el histórico tuvo un solo postor, porque el histórico ya lo olvidó. La tabla de la sección 6 del recorrido es esa medición.

**DGIM frente al muestreo por clave.** Ni siquiera compiten. El muestreo por clave decide qué entidades entran y conserva todos sus eventos, de modo que su eje es la entidad; el de DGIM es el tiempo. Si lo que se quiere es cuántos procesos sin competencia hubo en los últimos tres meses, el muestreo por clave da una respuesta sesgada por construcción, porque la respuesta depende de qué entidades salieron sorteadas y no del período.

**Reservoir frente al muestreo por clave.** Esta es la pareja que de verdad se confunde, porque las dos producen una muestra. La diferencia está medida en la figura f27: con muestreo por evento o reservoir, solo el 47 por ciento de los proveedores de la muestra conserva todos sus eventos, y con muestreo por clave el 100 por ciento. Entonces la pregunta cuántas adjudicaciones acumuló este proveedor da una respuesta falsa sobre el reservoir, no imprecisa, porque le faltan filas. Y a la inversa, el muestreo por clave no es uniforme sobre eventos: una entidad enorme entra entera o no entra, de modo que la varianza de cualquier proporción estimada es mucho mayor. Hacen falta los dos.

**Bloom frente a Count-Min.** Una frecuencia mayor que cero es una respuesta de pertenencia, así que la pregunta de por qué los dos es legítima. La sección 4 del recorrido la responde con una medición, no con una opinión: a igual tasa de error, el Count-Min necesita 64 veces más memoria para responder pertenencia, por una diferencia estructural de ocho bytes por celda contra un bit.

**Cualquiera de ellas frente al conteo exacto.** Es la comparación que falta en casi toda exposición de este tema y que aquí se hace siempre. El Bloom gana claramente, 79 KiB contra 1.582. DGIM gana a partir de algunos miles de elementos y pierde por debajo. El Count-Min **pierde** a este volumen, 1.487 KiB contra 273, y se reporta así.

## 4. Técnicas del temario que no se implementaron, y por qué

Conviene saber que existen y poder decir en una frase qué hacen y por qué no hacían falta.

1. **HyperLogLog.** Responde cuántos elementos distintos hay en el flujo, con memoria del orden del logaritmo del logaritmo de la cardinalidad. Es la cuarta pregunta clásica sobre un flujo, junto a pertenencia, frecuencia y recencia. Sí se usa en el perfilado de la Parte I, con approx_count_distinct, pero no aquí: la cardinalidad exacta de proveedores, 67.510, cabe de sobra en memoria y no habría nada que ahorrar. Su antecesor es Flajolet y Martin, que estima la cardinalidad a partir del máximo número de ceros iniciales en los hashes; HyperLogLog lo mejora promediando muchos registros con media armónica y corrigiendo el sesgo.
2. **Misra y Gries, y Space-Saving.** Encuentran los elementos pesados, es decir los que superan una fracción del flujo, con memoria proporcional a uno sobre esa fracción. Son la alternativa al Count-Min cuando la pregunta no es cuántas veces apareció una clave cualquiera sino cuáles son las más frecuentes. No se usan porque nuestra pregunta es la primera: el conteo de una clave concreta, consultable después.
3. **Lossy Counting y Sticky Sampling, de Manku y Motwani.** Conteo aproximado de elementos frecuentes sobre flujos con garantía de error epsilon y sin falsos negativos. Mismo motivo que el anterior.
4. **Histogramas exponenciales, de Datar y otros.** Son la generalización de DGIM para sumar **valores** en una ventana y no solo contar unos. Es la extensión natural si en lugar de cuántos procesos sin competencia quisiéramos cuántos soles movieron esos procesos en los últimos N. No se implementó porque nuestra pregunta es un conteo sobre un indicador binario, que es exactamente el caso que DGIM cubre.
5. **Filtro de Bloom con contadores, y filtro cuckoo.** Variantes que permiten borrar elementos, cosa que el Bloom clásico no puede porque apagar bits introduciría falsos negativos. El cuckoo además ocupa menos a tasas de error bajas. No hacen falta: nuestro conjunto de proveedores vistos solo crece.
6. **Filtro de Bloom escalable.** Encadena filtros de tamaño creciente cuando no se conoce de antemano cuántos elementos habrá. Aquí sí se conoce, porque la cardinalidad se mide antes.
7. **Boceto de Alon, Matias y Szegedy.** Estima momentos de frecuencia, por ejemplo la suma de los cuadrados, que mide lo desigual que es la distribución. Sería otra forma de medir concentración, pero la Parte I ya la mide de forma exacta con Gini porque la tabla cabe.
8. **Ventana deslizante exacta con una cola.** Es la alternativa exacta contra la que se compara DGIM. Para N igual a 150.000 cuesta 18.750 bytes frente a 320.
9. **Subir r en DGIM.** La cota de error es uno sobre r menos uno, de modo que con tres cubos por tamaño bajaría del 50 al 33 por ciento. No se hace porque el error observado ya está muy por debajo de la cota, pero es la palanca disponible y conviene saberlo.
10. **Spark.** Descartado con argumento: el recorrido es secuencial y con estado. Bloom y Count-Min sí son aditivos, de modo que esos dos se podrían distribuir combinando resúmenes parciales con un or lógico y una suma respectivamente; DGIM no, sin reescribirlo. Decir esa diferencia es parte de entender las estructuras.

## 5. Preguntas probables y qué responder

**¿Por qué no hay falsos negativos en el Bloom?** Por construcción: insertar solo enciende bits y nunca los apaga.

**¿En este caso el sketch realmente ahorró memoria?** No, y lo reportamos así. El diccionario exacto ocupa 273 KiB y el sketch necesita 1.487 para bajar el error a dos apariciones.

**¿De dónde sale el factor 64 entre Bloom y Count-Min?** De una diferencia estructural: ocho bytes por celda frente a un bit. No se sustituyen, responden preguntas distintas.

**¿Un error del 25 por ciento en DGIM no es demasiado?** Depende de la pregunta. Para decidir si una entidad entró en una racha inusual, un conteo con error acotado llega antes y basta. Para una cifra que se publica, no sirve. Y la cota se ajusta subiendo r.

**¿Entonces estas estructuras no sirven?** Sirven cuando la memoria es el recurso escaso, que es la situación de un flujo que no cabe. No ahorran tiempo: cambian memoria por tiempo y por error acotado.

**¿Por qué el flujo es simulado?** Porque no hay una fuente en tiempo real del OCDS peruano. Se ordena la tabla por fecha de convocatoria y se recorre una sola vez, que es el régimen que importa para medir estas estructuras.

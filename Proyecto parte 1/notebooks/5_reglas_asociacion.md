# Notebook 5. Conjuntos frecuentes y reglas de asociación

Guía de estudio del notebook [5_reglas_asociacion.ipynb](5_reglas_asociacion.ipynb). El porqué de cada elección está en [docs/JUSTIFICACION.md](../docs/JUSTIFICACION.md), sección Parte V.

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

## 1. Qué responde esta parte

La Parte I dejó un suelo de procesos sin competencia efectiva que atraviesa todos los tramos de monto. Falta saber si se reparte al azar o se concentra en combinaciones específicas de rubro, método y nivel de gobierno. Eso es, exactamente, una pregunta de patrones frecuentes.

**Y la decisión que determina todo el resultado es qué se considera una transacción.** El enunciado pide justificarla; aquí se justifica con una medición y no con una intuición, porque la definición obvia resultó no servir.

## 2. Qué es una entidad y por qué una contratación tiene canastas

**Entidad.** Es el comprador estatal, lo que en la tabla es el campo comprador_id. No es una empresa: en contratación pública el Estado es el que compra y la empresa está al otro lado del mostrador, como postor o como proveedor. Entidad es una municipalidad distrital, un gobierno regional, un hospital, una UGEL, un ministerio o un programa social. Hay 2.968 compradores distintos en los tres años.

Esto importa porque **el sujeto de nuestras reglas es la entidad compradora y no el proveedor**. Agrupar por proveedor y mes era posible, y respondería qué le compran juntos a un mismo proveedor, pero la pregunta que hereda esta parte es sobre el comportamiento del comprador.

**La correspondencia con el supermercado**, que es la analogía con la que se enseña el tema:

| En el supermercado | En las contrataciones del Estado peruano |
| --- | --- |
| El cliente | La entidad pública compradora |
| El ticket de compra | Todo lo que esa entidad contrató en un mes |
| El producto del ticket | El código CUBSO del objeto contratado |

El ítem no es un producto de abarrotes: es un código del **CUBSO**, el Catálogo Único de Bienes, Servicios y Obras, así que el universo incluye insumos, servicios y obras. Por eso entre los ítems aparecen cosas como servicio de alquiler de excavadora hidráulica o servicio de seguridad y vigilancia. La estructura del código, dígito por dígito, está en [docs/GLOSARIO.md](../docs/GLOSARIO.md).

**Por qué las reglas que salen tienen sentido.** No son el ejemplo del libro, son el resultado medido, y cada grupo tiene una causa institucional identificable.

1. Conserva de sardina o anchoveta, aceite vegetal comestible, arroz pilado superior, leche evaporada, hojuela de avena con quinua y kiwicha. Es la canasta de los **programas sociales de alimentación**: Vaso de Leche, comedores populares y Qali Warma. La municipalidad que compra aceite en un mes compra también conserva y arroz porque está armando la misma ración.
2. Alquiler de camión volquete, cemento Portland, alquiler de excavadora hidráulica. Es la canasta de **obra pública**: maquinaria y material de la misma obra.
3. Servicio de limpieza de áreas administrativas junto con servicio de seguridad y vigilancia, con lift 8,8. Este es el mejor ejemplo para defender el método, porque demuestra que no está encontrando comida sino **paquetes de abastecimiento institucional**: la entidad renueva los dos contratos en el mismo mes.

La frase corta, si preguntan qué hace una canasta de supermercado en un dataset de contrataciones: **la entidad es el cliente, el mes es el ticket y el código CUBSO es el producto.**

## 3. El vocabulario mínimo

1. **Transacción o canasta.** El conjunto de ítems que ocurren juntos. En el supermercado, lo que lleva un cliente en un ticket.
2. **Conjunto frecuente.** Un conjunto de ítems cuyo soporte supera un umbral.
3. **Soporte.** La fracción de transacciones que contienen el conjunto. Es una probabilidad conjunta.
4. **Confianza** de la regla A implica B. El soporte del conjunto unión dividido entre el soporte de A. Es la probabilidad condicional de B dado A.
5. **Lift.** La confianza dividida entre el soporte de B. Mide cuántas veces más aparece B junto a A de lo que cabría esperar si fueran independientes. Lift igual a uno es independencia.
6. **Antimonotonía.** Si un conjunto no es frecuente, ningún superconjunto suyo puede serlo. Es la propiedad que hace viable toda la minería de patrones.

## 4. Recorrido sección por sección

### Sección 1. Qué es una transacción aquí

La definición natural es que cada proceso es una canasta de códigos CUBSO. Se mide antes de usarla, junto con dos alternativas que agrupan por entidad y período.

| Definición | Canastas | Tamaño medio | Tamaño mediano | Con dos o más ítems |
| --- | --- | --- | --- | --- |
| Un proceso | 177.398 | 0,74 | 1 | 2,1 % |
| Una entidad en un mes | 37.114 | 2,78 | 2 | 53,6 % |
| Una entidad en un trimestre | 21.098 | 4,49 | 2 | 68,0 % |

Esta es la **figura f34** y decide la parte entera. La definición natural **no sirve**: solo el 2,1 por ciento de los procesos tiene dos o más ítems, con tamaño medio de canasta por debajo de uno. Un conjunto de un solo elemento no contiene coocurrencia, de modo que A-Priori y FP-Growth sobre esa definición devolverían únicamente conjuntos de tamaño uno, es decir un ranking de frecuencias disfrazado de minería de patrones.

**El motivo, que hay que saber explicar.** El catálogo CUBSO identifica el objeto del proceso, y la mayoría de los procesos peruanos tienen un objeto único. La analogía del supermercado no se sostiene a nivel de acto administrativo: el acto administrativo no es el ticket, es el producto.

**Por qué mes y no trimestre.** El trimestre da más coocurrencia, 68 por ciento, pero se adopta el mes por dos razones. Conserva más transacciones, y un mismo umbral de soporte relativo es más exigente cuando hay más transacciones. Y es interpretable: la regla dice que la entidad que compra A compra también B dentro del mismo mes, lo que describe un patrón de abastecimiento. A escala trimestral la coocurrencia empieza a capturar simplemente que la entidad compra mucho.

Si preguntan si cambiar la definición hasta que salga algo no es hacer trampa: sería trampa si la definición nueva no tuviera sentido, y lo tiene. Además la figura documenta **las tres** definiciones, incluida la que no funcionó, en lugar de presentar solo la que salió bien.

Las canastas unitarias se descartan después del agrupamiento porque no aportan coocurrencia.

### Sección 2. A-Priori, implementación propia

**Cómo funciona, por niveles.**

1. Cuenta el soporte de cada ítem individual y se queda con los frecuentes.
2. Genera candidatos de tamaño dos uniendo pares de frecuentes de tamaño uno, cuenta su soporte con una pasada completa por las transacciones y se queda con los frecuentes.
3. Repite subiendo de nivel hasta que no quedan candidatos.

**Dónde entra la antimonotonía.** En la generación de candidatos. Un candidato de tamaño k solo se considera si **todos** sus subconjuntos de tamaño k menos uno son frecuentes. Esa poda es lo que evita el crecimiento combinatorio completo.

**Cuál es su costo.** Una pasada completa por las transacciones en cada nivel, y el conteo de todos los candidatos contra cada transacción. Cuando el umbral baja, el número de candidatos explota.

Se corre sobre una muestra de 8.000 transacciones, porque A-Priori no escala al conjunto completo, y eso también es un resultado que se reporta.

### Sección 3. FP-Growth con Spark MLlib

**Cómo funciona.** Dos pasadas por el dato y ningún candidato.

1. Primera pasada: cuenta la frecuencia de cada ítem y descarta los no frecuentes.
2. Segunda pasada: inserta cada transacción, con sus ítems ordenados por frecuencia descendente, en un **árbol de prefijos** llamado FP-tree. Las transacciones que comparten prefijo comparten camino, de modo que el árbol comprime el dataset.
3. Minería: para cada ítem, de menos a más frecuente, construye su **base de patrones condicional**, que son los caminos del árbol que terminan en ese ítem, y sobre ella construye un FP-tree condicional del que extrae recursivamente los conjuntos frecuentes.

**Por qué es más rápido.** No genera ni cuenta candidatos. El trabajo depende del tamaño del árbol comprimido y no del número de combinaciones posibles.

**La verificación.** Los dos algoritmos deben devolver exactamente los mismos conjuntos frecuentes sobre la misma muestra, y lo hacen: cero conjuntos exclusivos de uno u otro, y diferencia máxima de soporte nula. Esa comprobación es lo que permite confiar en FP-Growth para el conjunto completo y deja A-Priori como implementación de referencia.

**El costo según el umbral**, que es la **figura f35**:

| Soporte mínimo | Conjuntos frecuentes | A-Priori | FP-Growth |
| --- | --- | --- | --- |
| 0,0200 | 34 | 0,17 s | 0,45 s |
| 0,0100 | 80 | 0,67 s | 0,37 s |
| 0,0050 | 202 | 2,99 s | 0,42 s |
| 0,0025 | 554 | 19,27 s | 0,44 s |

Con soporte alto los dos cuestan parecido porque hay pocos conjuntos frecuentes y A-Priori poda casi todo en el primer nivel. Al bajar el umbral de 0,02 a 0,0025, A-Priori pasa de 0,17 a 19,27 segundos y FP-Growth se mantiene plano. La diferencia es estructural y es exactamente la razón por la que el segundo desplazó al primero.

Si preguntan por qué implementar A-Priori si FP-Growth gana: porque A-Priori es donde se ve la antimonotonía, y porque sin medir la explosión de candidatos decir que FP-Growth es mejor sería repetir lo que dice el libro.

### Sección 4. Reglas sobre el conjunto completo

Sobre las 37.114 canastas de entidad y mes, con soporte mínimo 0,002 y confianza mínima 0,3.

La **figura f36** es una nube de soporte contra lift, coloreada por confianza, con los dos ejes en logaritmo y la línea de lift igual a uno marcada. Muestra el compromiso central de la minería de reglas: las reglas de soporte alto tienen lift cercano a uno, porque describen ítems que coinciden por ser ambos frecuentes y no porque uno prediga al otro; las de lift alto viven en la zona de soporte bajo, donde el patrón es fuerte pero afecta a pocas transacciones. El máximo de lift es 139.

**Por qué el criterio de selección es el lift y no la confianza.** Porque la confianza no descuenta la frecuencia del consecuente. Una regla que concluye en un ítem presente en la mitad de las canastas tiene confianza alta por construcción y no informa nada. El lift sí lo descuenta, porque compara contra la independencia.

Las diez reglas seleccionadas exigen soporte de al menos 0,004 y lift de al menos 3:

| Si la entidad compra | También compra | Soporte | Confianza | Lift |
| --- | --- | --- | --- | --- |
| Conserva de sardina o anchoveta | Aceite vegetal comestible | 0,0042 | 0,386 | 50,9 |
| Aceite vegetal comestible | Conserva de sardina o anchoveta | 0,0042 | 0,550 | 50,9 |
| Aceite vegetal comestible | Arroz pilado superior | 0,0047 | 0,616 | 37,8 |
| Arroz pilado superior | Conserva de sardina o anchoveta | 0,0054 | 0,330 | 30,6 |
| Alquiler de camión volquete más cemento | Alquiler de excavadora hidráulica | 0,0043 | 0,705 | 18,1 |

**Cómo interpretarlas.** Las primeras son la canasta de los programas sociales de alimentación, sobre todo Vaso de Leche y los comedores: la entidad que compra aceite en un mes compra también conserva y arroz. Las últimas son la canasta de obra pública: maquinaria y materiales que se contratan juntos. Ninguna es sorprendente para quien conozca el sector, y eso es buena señal: el método recupera estructura real antes de buscar lo inesperado.

### Sección 5. Canasta enriquecida, donde se responde la pregunta de la Parte I

Hasta aquí la canasta tiene solo códigos de catálogo, de modo que las reglas solo pueden hablar de qué se compra junto. Pero la pregunta que dejó abierta la Parte I es otra, y **tener un solo postor no es un producto del catálogo, es un atributo del proceso**.

La técnica, que conviene saber nombrar, es **convertir atributos categóricos en ítems** para que el mismo algoritmo de patrones frecuentes descubra asociaciones entre atributos y no solo entre productos. A cada canasta se le agregan los atributos del proceso como ítems, con un prefijo que nombra el campo. Una canasta enriquecida se ve así:

**{ RUBRO=5013, METODO=Contratación Directa, NIVEL=Gobierno nacional, TRAMO=50 mil a 500 mil, POSTOR=unico }**

Cuatro detalles de implementación que hay que saber justificar.

1. **El prefijo no es decoración.** Sin él un valor de un campo podría colisionar con el de otro, y la regla dejaría de leerse sola. Con él, el antecedente se lee en castellano.
2. **Aquí la canasta vuelve a ser el proceso**, no la entidad y el mes, porque los atributos pertenecen al proceso. Y ahora sí funciona, porque por construcción cada canasta tiene cinco ítems o más, así que hay coocurrencia de sobra. Es el mismo algoritmo sobre una definición de transacción distinta, elegida por la pregunta.
3. **El tramo de monto es una discretización obligatoria.** Un algoritmo de patrones frecuentes solo entiende ítems, no puede recibir una variable continua, así que el monto se parte en cuatro categorías: menos de 50 mil, de 50 mil a 500 mil, de 500 mil a 5 millones y más de 5 millones.
4. **Se excluyen los procesos con número de postores imputado.** Si no, la asociación la podría producir nuestra propia regla de imputación de la Parte I, que sería circular.

Luego se filtran las reglas cuyo consecuente es exactamente la marca de postor único.

| Si el proceso es | Soporte | Confianza | Lift |
| --- | --- | --- | --- |
| Régimen Especial más Gobierno nacional más menos de 50 mil | 0,0176 | 1,000 | 8,06 |
| Régimen Especial más Gobierno nacional más rubro 8010 más menos de 50 mil | 0,0157 | 1,000 | 8,06 |
| Contratación Internacional más rubro 8210 | 0,0058 | 1,000 | 8,06 |
| Contratación Directa más rubro 8013 más de 50 mil a 500 mil | 0,0075 | 0,990 | 7,98 |

La última se lee así: cuando un proceso es Contratación Directa, del rubro 8013 y está en el tramo de 50 mil a 500 mil soles, tiene un solo postor el 99 por ciento de las veces, casi ocho veces más de lo que correspondería al azar.

**Qué son esos rubros**, resuelto con las descripciones del propio dato. Esto es lo que convierte la figura en un hallazgo explicable y no en una lista de números:

| Rubro | Qué agrupa | Lectura de la regla |
| --- | --- | --- |
| 8010 | Consultoría, seguimiento y monitoreo de proyectos de inversión pública | Contratación de un consultor concreto, donde el postor único es la norma del procedimiento |
| 8013 | Alquiler de inmuebles, locales y oficinas | El dueño de un local determinado es, por definición, el único que puede ofrecerlo |
| 8210 | Publicidad y difusión en medios de comunicación | Espacios de un medio concreto, que tampoco tiene sustituto |
| 5013 | Leche y derivados | El rubro del Vaso de Leche, que aparece en las reglas de productos |

La **figura f37** es la respuesta: el suelo de procesos sin competencia **no se reparte al azar**, se concentra en combinaciones identificables.

**Tres matices que hay que decir al presentarla.**

1. La tasa base de postor único es del 12,4 por ciento, de modo que el lift máximo posible es 8,06 y lo alcanza **toda** condición con confianza igual a uno. Hay varias combinaciones empatadas en ese máximo, así que el ranking por lift no distingue entre ellas y se desempata por soporte.
2. Que un régimen especial, una contratación internacional o el alquiler de un inmueble tengan un solo postor es **administrativamente esperable** y no indica nada irregular. Los rubros de la tabla anterior lo muestran: son objetos sin sustituto.
3. Por eso el valor de la figura es acotar dónde buscar, y lo informativo son las combinaciones donde el procedimiento sí preveía concurrencia.

## 5. Alternativas para cada decisión, explicadas

### Para definir la transacción

1. **Un proceso igual a una canasta.** La definición natural. Medida y descartada: 2,1 por ciento de coocurrencia, tamaño medio 0,74.
2. **Una entidad en un trimestre.** Más coocurrencia, 68 por ciento, pero menos transacciones y peor interpretabilidad.
3. **Una entidad en un año, o la entidad entera.** Llevado al extremo, la canasta acabaría siendo el catálogo completo de lo que compra una entidad, y las reglas solo dirían que las entidades grandes compran de todo.
4. **Un proveedor en un mes.** Otra agrupación posible, que respondería qué le compran juntos a un mismo proveedor. No se usa porque la pregunta heredada de la Parte I es sobre el comportamiento de la **entidad compradora**.
5. **Lo que se hizo.** Entidad y mes, con las tres definiciones medidas y publicadas en la figura f34, incluida la que no funcionó.

### Para el nivel de agregación del código

1. **El código CUBSO completo, 16 dígitos.** Casi único por ítem. El universo sería tan disperso que ningún conjunto alcanzaría el soporte mínimo.
2. **El prefijo de 8 dígitos.** Lo que se usó para las reglas de productos: 4.664 ítems distintos, que es un universo minable.
3. **El prefijo de 4 dígitos.** Lo que se usó en la canasta enriquecida, donde interesa el rubro grueso y no el producto exacto, para que las condiciones de la figura f37 sean legibles.

### Para hallar los conjuntos frecuentes

1. **Fuerza bruta sobre todos los subconjuntos.** Dos elevado al número de ítems. Impensable.
2. **A-Priori.** Lo que se implementó a mano. Por niveles, con poda por antimonotonía. Su costo es una pasada completa por las transacciones en cada nivel.
3. **PCY, de Park, Chen y Yu.** La mejora clásica de A-Priori para el paso de los pares, que es el que más memoria consume. Mientras cuenta los ítems en la primera pasada, además hashea cada par a un conjunto de contenedores y cuenta cuántos pares caen en cada uno. Un par solo puede ser frecuente si su contenedor lo es, de modo que en la segunda pasada el mapa de bits de contenedores frecuentes poda muchísimos pares antes de contarlos. No hace falta aquí: con 4.664 ítems los pares caben en memoria sin apretar.
4. **Multietapa y multihash.** Son refinamientos de PCY, con más pasadas y más funciones hash respectivamente, para apretar todavía más la poda. Mismo motivo para no usarlos.
5. **Algoritmo de Toivonen.** Corre A-Priori sobre una muestra con un umbral algo menor, y luego verifica los candidatos y su **frontera negativa**, es decir los conjuntos que no son frecuentes en la muestra pero cuyos subconjuntos sí lo son. Si ningún elemento de la frontera negativa resulta frecuente en el conjunto completo, el resultado es exacto; si alguno lo es, hay que repetir. Da una respuesta exacta con alta probabilidad en dos pasadas. No se usa porque el conjunto completo cabe en memoria: lo que escala mal aquí es A-Priori, no el dato.
6. **SON, de Savasere, Omiecinski y Navathe.** Es el algoritmo distribuido natural y conviene conocerlo justo porque esta parte usa Spark. Parte las transacciones en fragmentos, halla los conjuntos frecuentes locales de cada fragmento con cualquier algoritmo, y toma la unión como candidatos globales; después una segunda pasada cuenta esos candidatos sobre el conjunto completo. La propiedad que lo hace correcto es que un conjunto frecuente globalmente tiene que ser frecuente en al menos un fragmento, de modo que **no hay falsos negativos**. Encaja exactamente en un mapa y una reducción, y es la forma en que se distribuiría A-Priori si hiciera falta. No se usa porque FP-Growth de MLlib ya resuelve el conjunto completo en menos de medio segundo.
7. **Eclat.** Representa cada ítem por su lista de identificadores de transacción y obtiene el soporte de un conjunto intersecando listas, en lugar de recorrer las transacciones. Es rápido con datos densos y consume mucha memoria con universos grandes.
8. **FP-Growth.** Lo que se usa en producción. Árbol de prefijos y proyecciones condicionales, sin generar candidatos.

### Para elegir qué reglas presentar

1. **Confianza alta.** Descartada: no descuenta la frecuencia del consecuente, de modo que una regla que concluye en un ítem muy común tiene confianza alta por construcción.
2. **Lift.** Lo que se usó, junto a un mínimo de soporte para que la regla no sea una anécdota.
3. **Convicción.** Mide cuánto se equivocaría la regla si antecedente y consecuente fueran independientes. Es menos conocida y no añade nada aquí.
4. **Leverage, o diferencia respecto de la independencia.** Favorece reglas de soporte alto, que es lo contrario de lo que hace el lift. Serviría si la prioridad fuera el impacto absoluto y no la fuerza del patrón.
5. **Conjuntos maximales y cerrados.** Formas de comprimir la salida: los maximales son los frecuentes sin superconjunto frecuente, y los cerrados son aquellos cuyos superconjuntos tienen soporte estrictamente menor. Reducen mucho el número de resultados sin perder información de soporte en el caso cerrado. No hacían falta porque la salida ya es manejable.

### Para responder la pregunta de la Parte I

1. **Un modelo de clasificación de postor único.** Predeciría mejor, y no respondería la pregunta: el enunciado pide patrones frecuentes, y un modelo entrega un peso por variable en lugar de combinaciones concretas legibles.
2. **Tablas cruzadas de método por nivel por tramo.** Es lo que haría un análisis exploratorio, y se queda corto: el número de combinaciones crece y no hay criterio para ordenarlas.
3. **Lo que se hizo.** Convertir los atributos del proceso en ítems de la canasta, de modo que el mismo algoritmo de patrones frecuentes descubra asociaciones entre atributos, con soporte, confianza y lift como criterio de orden.

### Lo que no se hizo y sería la continuación natural

1. **Minería de secuencias, al estilo GSP o PrefixSpan.** Encuentra patrones **con orden**, por ejemplo que tras comprar A una entidad compra B el mes siguiente. Nuestra pregunta es de coocurrencia dentro de un mes, no de orden, pero es la extensión evidente si se quisiera estudiar ciclos de abastecimiento.
2. **Reglas con restricción temporal o por territorio.** Mismo algoritmo, particionando antes.

## 6. Preguntas probables y qué responder

**¿No es hacer trampa cambiar la definición de transacción hasta que salga algo?** Sería trampa si la nueva no tuviera sentido. Lo tiene, y la figura documenta las tres definiciones para que el lector juzgue el cambio.

**¿Por qué implementar A-Priori si FP-Growth gana?** Porque A-Priori es donde se ve la antimonotonía, y porque la figura es el argumento medido en lugar de la cita del libro.

**¿Por qué no filtrar simplemente por confianza alta?** Porque la confianza no descuenta la frecuencia del consecuente, y el lift sí.

**¿Eso es evidencia de direccionamiento?** No. Parte de lo que aparece arriba es administrativamente esperable. Lo que entrega el análisis es una lista priorizada de dónde mirar, no una conclusión sobre conducta.

**¿Cómo saben que su A-Priori es correcto?** Porque devuelve exactamente el mismo conjunto de itemsets frecuentes que FP-Growth de MLlib sobre las mismas transacciones, con diferencia de soporte nula.

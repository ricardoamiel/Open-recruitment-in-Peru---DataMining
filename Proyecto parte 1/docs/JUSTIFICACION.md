# Justificación de las decisiones del proyecto

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

Este documento contiene el razonamiento detrás de cada decisión técnica. Los notebooks llevan el resultado y una lectura corta de cada figura; el porqué, las alternativas descartadas y los límites de cada conclusión están aquí.

Orden de lectura sugerido: esta sección 0, luego el notebook de la parte que interese, y de vuelta aquí a la sección correspondiente cuando una decisión no se entienda.

## 0. Decisiones transversales

### 0.1 Por qué este dataset

El enunciado exige datos abiertos del Estado peruano que admitan de forma integrada las seis técnicas del curso. Las contrataciones públicas en estándar OCDS cumplen los cuatro requisitos mínimos sin forzar ninguna analogía.

| Requisito | Qué aporta |
| --- | --- |
| Volumen para justificar procesamiento distribuido | 2,77 GB de CSV en 21 tablas por año, 281.462 procesos, más de 11 millones de líneas |
| Registros como conjuntos o vectores comparables | El objeto contractual es texto libre; además cada proceso trae códigos CUBSO |
| Dimensión temporal para simular un flujo | Fecha de convocatoria con resolución de minuto |
| Estructura transaccional derivable | Los códigos CUBSO por entidad y período forman canastas |

Se descartó MEF por ser fuerte en volumen pero débil en texto libre, e INEI porque la dimensión de flujo y la canasta habría que forzarlas.

### 0.2 Por qué Spark en una sola máquina

Es un despliegue de un nodo y conviene ser honesto: no demuestra escalabilidad horizontal. Sí ejercita el mismo modelo de ejecución, el mismo planificador y las mismas primitivas de particionado y barajado que un clúster, y el código no cambia al mover la sesión; cambia la cadena del master. El enunciado admite justificar por qué Spark sigue siendo adecuado aun sin volumen extremo, y esa es la justificación.

### 0.3 Arquitectura del código

Tres módulos y nada más, en src_v2.

1. comun.py abre Spark, dibuja las figuras y exporta artefactos. La función figura exige una lectura de al menos cuarenta caracteres y falla si no la recibe, de modo que es imposible dejar un gráfico sin interpretar por descuido.
2. ingesta.py es el único que conoce la forma cruda del dataset. Cambiar de fuente cuesta reescribir este archivo.
3. algoritmos.py contiene las implementaciones propias de las semanas 3 a 6.

Se descartó la versión anterior, que tenía un perfil YAML declarativo y una capa genérica de roles de columna. Era flexible pero exigía leer tres archivos para entender una línea de limpieza. La prioridad aquí es que el código se pueda explicar en una sustentación oral.

### 0.4 Por qué implementaciones propias y además las de las bibliotecas

Cada algoritmo del curso está implementado a mano y, donde existe equivalente, contrastado contra Spark MLlib o FAISS. La implementación propia demuestra que se entiende el mecanismo; el contraste demuestra que no se entendió mal. Si la propia tuviera un error conceptual, el contraste lo revelaría de inmediato.

Todas las implementaciones propias se verifican antes de usarlas: MinHash contra la cota de uno sobre raíz de n, Bloom contra su tasa teórica de falsos positivos, Count-Min contra su cota de error, DGIM contra el conteo exacto, reservoir contra la uniformidad esperada, y A-Priori contra fuerza bruta sobre un ejemplo pequeño.

### 0.5 La paleta

La paleta del curso, azul 1F4E79, naranja C55A11 y verde 548235, no separa el verde del naranja bajo deuteranopia. Se reescalonaron las mismas familias a 2E6DB4, B3441F, 6FAE3C, 8B5BB5 y 00A0A0, que sí separan. Además toda figura lleva ejes rotulados y el dato exportado como tabla, de modo que ninguna lectura depende solo del color.

---

## 1. Parte I. KDD y EDA

### 1.1 Selección: 5 tablas de 21, 14 columnas de 37

Se leen main, awards, awards_suppliers, awards_items y parties. Las 16 restantes son documentos adjuntos, tipos de cambio y clasificaciones secundarias que ninguna de las seis técnicas necesita. Proyectar temprano reduce lo que Spark deserializa en cada tarea, y sobre CSV ese costo no se recupera después.

### 1.2 Por qué todo se lee como texto

Si se deja inferir el esquema, el código CUBSO de 16 dígitos se lee como número de coma flotante y vuelve en notación científica, perdiendo los últimos dígitos, que son justo los que identifican el ítem. La conversión de tipos se hace después, explícita y columna por columna.

### 1.3 Qué fecha es la fecha

El paquete trae dos. La fecha de publicación indica cuándo el registro entró al feed OCDS, que para procesos reprocesados es años posterior al hecho. La fecha de convocatoria indica cuándo la entidad publicó el proceso en el SEACE. Se usa la segunda: la primera describiría la actividad del publicador y no la del Estado comprador.

### 1.4 Las seis decisiones de limpieza

**Descartar montos no positivos.** Cerca de 23.000 procesos declaran valor referencial cero. Un proceso de contratación sin valor referencial no existe administrativamente; el cero es la marca de un campo no publicado o reservado por ley. La alternativa, imputar la mediana, inventaría gasto público que no existe. Se descarta y se reporta la pérdida.

**Recortar la ventana temporal a 2023 a 2025.** El paquete anual arrastra convocatorias de años anteriores que recién entonces se publicaron o corrigieron; en el paquete 2024 casi la mitad son de 2015 y 2016. Mezclarlas produce picos en la serie temporal que son del publicador y no del Estado. Cuesta alrededor del 30 por ciento de las filas y es el descarte más caro del proyecto. La alternativa, conservarlas y filtrar en cada consulta, se descartó porque garantiza que alguien olvide el filtro alguna vez.

**Imputar el número de postores con la mediana de su método.** La ausencia no es al azar: se concentra en ciertos métodos de contratación. La mediana global mezclaría una licitación pública con una adjudicación de menor cuantía. Se usa la mediana y no la media porque la variable tiene cola larga. Queda la columna n_postores_imputado para poder excluir estos casos, y de hecho el análisis de competencia los excluye.

**Marcar los extremos de monto, no eliminarlos.** Es la decisión contraria a la habitual y la más importante del preprocesamiento. El criterio del rango intercuartílico se aplica sobre el logaritmo, porque en escala lineal marcaría como extrema a una fracción enorme de la cola, que en este dominio es dato legítimo. Y lo detectado se marca y se conserva: los procesos marcados son el 0,3 por ciento de las filas y concentran alrededor del 38 por ciento del gasto. Eliminarlos habría dejado una tabla más ordenada y habría borrado un tercio del dinero público que se quiere estudiar.

**Winsorizar el número de postores al percentil 99,9.** Aquí el extremo sí es un error de carga del SEACE y no tiene lectura sustantiva. Se recorta en lugar de descartar la fila, porque la fila sigue aportando su monto, su objeto y su canasta.

**Reparar la codificación.** Parte de los textos se grabó en CP850 y el registro los leyó como Latin-1, de modo que cada letra acentuada quedó convertida siempre en el mismo carácter equivocado. Son once sustituciones reversibles. No es cosmética: el shingling de la Parte II sobre un texto corrompido genera fragmentos que no coinciden con los del mismo texto bien codificado, y produce falsos negativos justo entre los registros que más interesa emparejar. Se deja sin tocar lo ambiguo, sobre todo el signo de interrogación invertido, que unas veces sustituye una tilde y otras está puesto a propósito; repararlo por conjetura introduciría más ruido del que quita.

### 1.5 Una columna que resultó inservible

La duración de la convocatoria vale cero en todas las filas, porque la fuente publica el inicio y el fin del período de ofertas con el mismo valor. No se imputa, porque no hay nada que imputar, y no se usa en ningún análisis. Es el recordatorio de por qué el perfilado va antes que el análisis: una variable con nombre prometedor puede estar vacía de contenido sin tener un solo nulo.

### 1.6 El nivel de gobierno es derivado y heurístico

El estándar OCDS no publica el nivel de gobierno de la entidad compradora, así que se deriva por expresión regular sobre su nombre. Tiene dos límites que hay que declarar. El residual, es decir la categoría Otro, es la medida honesta de cuánto falla la derivación y se reporta en el notebook. Y algunos nombres son ambiguos por naturaleza: un fondo de inversiones municipal lleva la palabra fondo y ninguna referencia a su municipalidad, de modo que la regla lo asigna a gobierno nacional. Para un corte institucional grueso la variable cumple; para una clasificación presupuestal exacta, no.

### 1.7 Parquet particionado por año

Tres motivos, en orden de importancia. Es columnar, y el EDA lee dos o tres columnas de veinticinco. La partición por año permite descartar directorios enteros, que se verifica leyendo PartitionFilters en el plan. Y conserva los tipos, de modo que las partes siguientes arrancan de un estado idéntico.

Se descartó particionar por departamento: daría veinticinco directorios muy desiguales, con Lima concentrando casi todo, y esa asimetría se paga en cada barajado.

### 1.8 RDD frente a DataFrame

El EDA va en DataFrames sin discusión. Los RDD se reservan para lo que de verdad los necesita, que es mantener estado entre elementos: las firmas MinHash y el agrupamiento por bandas de la Parte II, y el recorrido de la Parte IV.

La medición se hace con calentamiento previo y mediana de tres corridas. Una sola corrida no es una medición, y omitir el dato tampoco es la respuesta: el enunciado lo pide y lo riguroso es repetir, no abstenerse.

---

## 2. Parte II. Similitud

### 2.1 Por qué shingles del objeto y no códigos CUBSO

El dataset ofrece las dos representaciones y se midieron ambas. El conjunto de códigos CUBSO tiene menos de un elemento por proceso en promedio y muchos procesos vacíos, así que no sostiene una similitud discriminante. Los shingles del objeto sí. El CUBSO se reserva para la Parte V, donde la canasta se redefine por entidad y mes y entonces sí tiene tamaño suficiente.

### 2.2 Cómo se elige k, y por qué no sale de los datos

Al subir k el fondo de pares no relacionados cae, pero la señal de los pares parecidos también. Las dos curvas bajan juntas, de modo que ninguna métrica sobre pares aleatorios tiene un máximo interior. Se probaron la resta entre percentil 99 y mediana, la razón entre ambos, y una relación señal a ruido: la primera elige siempre el k más pequeño y las otras dos el más grande. También se probó generar duplicados conocidos perturbando textos reales, y el óptimo resultó depender de la tasa de perturbación que uno asuma, que es un parámetro inventado.

La conclusión honesta es que k no se optimiza, se fija con un criterio, y el criterio del curso es que dos documentos no relacionados no compartan prácticamente nada. Se toma el k más pequeño que deja la mediana de los pares aleatorios por debajo de 0,02. Subir más solo recorta señal y gasta memoria. La elección no es crítica, y el barrido de LSH lo confirma.

### 2.3 Por qué 128 funciones hash

El error de estimación de MinHash baja como uno sobre la raíz de n, de modo que cuadruplicar las funciones solo divide el error entre dos. Con 128 el error queda muy por debajo del ancho de la zona de decisión de LSH, así que gastar más memoria por firma no compra nada útil.

### 2.4 Cómo se eligen las bandas y las filas, y con qué métrica

No hay una configuración correcta en abstracto: el par de bandas y filas es la definición operativa de qué se considera parecido.

Lo primero es acertar con la métrica, y aquí hubo que corregir el enfoque inicial. **LSH es un generador de candidatos, no un clasificador.** Su salida pasa después por una verificación con Jaccard exacta que elimina todos los falsos positivos. Por eso la precisión antes de verificar no mide calidad: mide cuánto trabajo queda por hacer. Las dos cifras que deciden son el recall, porque un par perdido en esta etapa se pierde para siempre, y el número de candidatos, porque es el costo de la verificación. La primera versión de esta parte usaba F1 sobre candidatos crudos y elegía una configuración de recall bajo, que es exactamente el error contrario al que conviene cometer.

El barrido se hace variando r de 1 a 8 con b igual a 128 dividido entre r, y se elige la configuración de menor costo entre las que superan 95 por ciento de recall.

Una confusión frecuente que conviene evitar: el umbral (1 sobre b) elevado a 1 sobre r marca dónde la curva S cambia de concavidad, no dónde la probabilidad vale un medio. En ese punto la probabilidad de ser candidato es 1 menos 1 sobre e, alrededor de 0,63.

### 2.5 Por qué la comparación con Spark MLlib necesita un ajuste

El método approxSimilarityJoin de MLlib no devuelve candidatos: genera los candidatos internamente y ya les aplica la verificación exacta, de modo que su salida son pares verificados. Comparar sus pares verificados contra los candidatos crudos de la implementación propia da una ventaja aparente enorme a MLlib que es solo de contabilidad, y así estaba en el primer intento.

Con el mismo contrato, es decir aplicando a los candidatos propios la misma verificación, las dos producen pares correctos y lo que queda es una diferencia de configuración. MLlib usa tablas hash independientes, que equivale a bandas de una sola fila, y eso le da un umbral efectivo muy bajo: atrapa casi todos los pares verdaderos a costa de generar muchos más candidatos internos, que no expone. La implementación propia permite elegir ese punto explícitamente, que es lo que el enunciado pide analizar.

La verificación que importa es que ningún par declarado por la implementación propia resulta falso tras la comprobación exacta. Si el agrupamiento por bandas tuviera un error conceptual, aparecerían pares que no superan el umbral.

### 2.6 MinHash y SimHash no compiten

Es la pregunta que el enunciado invita a responder y la respuesta no es elegir uno.

1. MinHash estima similitud de Jaccard entre conjuntos sin peso. Es lo correcto para un conjunto de shingles o de códigos de catálogo, donde todos los elementos valen igual.
2. SimHash proyecta un vector con pesos sobre hiperplanos aleatorios y estima similitud coseno. Es lo correcto para el objeto vectorizado con TF-IDF, donde la palabra adquisición aparece en casi todos los procesos y el nombre de un equipo médico en muy pocos.

Aplicar MinHash sobre el texto trataría ambas palabras igual y perdería esa información. Se implementan los dos y se comparan sobre pares estratificados por similitud real, no sobre pares aleatorios: con pares aleatorios casi todos tienen similitud cero y la correlación medida sería ruido.

Una limitación de SimHash que conviene conocer: con 64 bits la similitud estimada solo puede tomar 65 valores, así que los puntos se alinean en bandas visibles. Subir a 128 bits afina la escala a costa del doble de memoria.

---

## 3. Parte III. Búsqueda aproximada de vecinos

### 3.1 Por qué aquí no se usa Spark

FAISS es una biblioteca de un solo nodo, el subconjunto cabe holgadamente en memoria y la tarea es búsqueda en un índice, no agregación distribuida. Distribuirla agregaría barajado y serialización sin ganar nada. Reconocer dónde Spark no aporta es parte de lo que evalúa la Parte VI, y afirmar lo contrario sería un error de criterio más grave que no usarlo.

### 3.2 Por qué TF-IDF más SVD

FAISS trabaja sobre vectores densos y TF-IDF es disperso de muy alta dimensión. La SVD truncada reduce a 128 dimensiones conservando la estructura de similitud. Los vectores se normalizan a norma uno para que el producto interno del índice sea exactamente la similitud coseno.

Se construyen dos representaciones, de palabras y de n-gramas de caracteres, para separar el efecto de la representación del efecto del índice. Resultó que con el índice fijo y exacto las dos comparten menos de la mitad de los diez vecinos, lo que obliga a un matiz incómodo: una parte grande de lo que se llama error de un índice aproximado es en realidad una decisión de representación tomada mucho antes.

### 3.3 IVF frente a HNSW

**IVF** parte el espacio con un k-medias previo en nlist celdas y guarda cada vector en la celda de su centroide. La consulta recorre solo las nprobe celdas más cercanas. Su parámetro de calidad es nprobe. Se construye rápido, ocupa poco por encima de los vectores y admite insertar sin reconstruir. Degrada de forma predecible.

**HNSW** construye un grafo donde cada vector se conecta con sus M vecinos más cercanos, en capas: las de arriba dispersas para acercarse rápido, las de abajo densas para afinar. Su parámetro de calidad es efSearch. Da más recall por milisegundo, pero el grafo cuesta construirlo, ocupa bastante más memoria y borrar elementos es incómodo.

La regla práctica: IVF cuando la memoria es el límite y el conjunto cambia seguido; HNSW cuando la latencia es el límite y el conjunto es estable.

### 3.4 El régimen de medición cambia la conclusión

Este fue el error más instructivo del proyecto y conviene dejarlo documentado. La primera versión de esta parte medía la fuerza bruta con lotes de mil consultas y el escalado con lotes de trescientas, y concluía que HNSW era veintiocho veces más rápido. Esa conclusión era falsa y el defecto estaba en el método, no en los índices.

FAISS cambia de implementación según el tamaño del lote. Con un lote grande, el índice plano resuelve la búsqueda como un producto de matrices con BLAS y aprovecha los ocho núcleos; con una sola consulta no tiene nada que amortizar. La diferencia de rendimiento entre ambos regímenes llega a un orden de magnitud, de modo que comparar un índice medido en un régimen contra otro medido en el otro produce cualquier resultado que se quiera.

Corregida la medición, el resultado honesto tiene dos caras.

1. **En lote**, a nuestro volumen el índice aproximado no aporta nada. El índice plano con mil consultas simultáneas es tan rápido como HNSW, y a veces más.
2. **Consulta a consulta**, que es el régimen de un servicio en línea, HNSW sí gana, y su ventaja crece con el tamaño de la base porque la fuerza bruta escala de forma lineal y el grafo en capas casi no escala.

La conclusión para la Parte VI es entonces más matizada que un simple vale la pena: depende del uso. Para un trabajo por lotes a este volumen, no vale la pena. Para un servicio en línea, o a diez o cien veces el volumen, sí.

La lección metodológica general es que toda afirmación sobre velocidad tiene que declarar el régimen en que se midió, y que los dos lados de una comparación tienen que medirse igual. Este proyecto lo aplica también en la Parte I, donde las agregaciones en RDD y en DataFrame se miden con el mismo calentamiento y la misma mediana de tres corridas.

---

## 4. Parte IV. Minería de flujos

La pregunta que el proyecto se hace aquí es la del enunciado: por qué usar unas estructuras y no otras, o por qué usar varias. La respuesta corta es que ninguna sustituye a otra porque responden preguntas distintas. La respuesta larga está abajo.

### 4.1 Tres formas de muestrear y qué pregunta sobrevive a cada una

| Técnica | Qué garantiza | Qué pregunta permite |
| --- | --- | --- |
| Por evento | Una fracción de los eventos, elegidos al azar | Proporciones sobre el flujo |
| Por clave | Todos los eventos de una fracción de las entidades | Métricas por entidad |
| Reservoir | Muestra uniforme de tamaño fijo, sin conocer el largo | Proporciones sobre el flujo |

El muestreo por evento y el reservoir son equivalentes en utilidad: ambos conservan proporciones y ambos rompen las preguntas por entidad, porque cada entidad queda incompleta. El muestreo por clave es el único que permite preguntar cuántas adjudicaciones acumuló un proveedor, porque la entidad entra entera o no entra.

Entonces la elección entre reservoir y muestreo por clave no se decide por precisión sino por la pregunta, y este proyecto necesita las dos.

La ventaja propia del reservoir sobre el muestreo por evento es que no necesita conocer el largo del flujo ni fijar una fracción de antemano: mantiene exactamente k elementos pase lo que pase. En un flujo real, que no termina, eso no es un detalle.

### 4.2 Bloom Filter frente a Count-Min Sketch, y por qué los dos

Es la pregunta natural: un Count-Min estima frecuencias, y una frecuencia mayor que cero es una respuesta de pertenencia. Entonces para qué un Bloom.

La respuesta tiene dos partes.

1. **Responden preguntas distintas.** Bloom responde si un elemento apareció. Count-Min responde cuántas veces. Un Bloom no puede dar una frecuencia por mucha memoria que se le dé.
2. **Forzar uno sobre la tarea del otro cuesta caro.** Un Bloom guarda un bit por posición; un Count-Min guarda un contador de ocho bytes. Para la misma tarea de pertenencia con la misma tasa de error, el sketch necesita del orden de sesenta y cuatro veces más memoria por celda, y no gana nada a cambio: una celda con valor positivo por colisión declara presente a un elemento ausente igual que el Bloom.

Hay además una propiedad del Bloom que el Count-Min no tiene y que importa: los falsos negativos son imposibles por construcción. Un negativo del Bloom es definitivo. Eso lo hace apto para descartar trabajo, que es su uso clásico.

Y un matiz honesto sobre el Count-Min en este proyecto: solo compensa cuando el universo de claves es grande. A nuestro volumen, el diccionario exacto de códigos CUBSO es pequeño y el sketch todavía no gana. Se implementa porque la pregunta de la Parte VI es qué pasaría con cien veces más datos, y ahí sí gana.

### 4.3 DGIM frente a reservoir, y por qué los dos

También se confunden, porque ambos son resúmenes de un flujo con memoria acotada. Responden preguntas ortogonales.

1. El reservoir da una muestra uniforme de todo el flujo, sin noción de recencia: un evento de 2023 tiene la misma probabilidad de estar que uno de 2025.
2. DGIM responde solo sobre los últimos N elementos y olvida el resto por construcción.

Si se intenta responder la pregunta de ventana con un reservoir, hay que filtrar su muestra por posición y queda una fracción diminuta, de modo que se obtiene más error con más memoria. A la inversa, DGIM no puede decir qué proporción de todo el histórico tuvo un solo postor, porque ya lo olvidó.

DGIM guarda cubos de tamaño potencia de dos, a lo más dos de cada tamaño, y su memoria depende del logaritmo de N y no de N. El error relativo está acotado por uno sobre el número de cubos por tamaño, es decir un medio con el valor habitual. Con ventanas pequeñas no compensa, incluso pierde; el cruce aparece en los primeros miles de elementos.

### 4.4 Por qué esta parte no usa Spark

El recorrido es inherentemente secuencial y con estado: cada elemento modifica una estructura que el siguiente consulta. Bloom y Count-Min son aditivos y se podrían combinar por particiones, pero DGIM no, sin reescribirlo. Spark se usa solo para ordenar y materializar el flujo, que es exactamente donde aporta.

---

## 5. Parte V. Conjuntos frecuentes y reglas

### 5.1 La definición de transacción era el problema, no el algoritmo

La definición natural, cada proceso como canasta de códigos CUBSO, no sirve: la enorme mayoría de los procesos tiene un solo ítem o ninguno. Un conjunto de un solo elemento no contiene coocurrencia, de modo que A-Priori y FP-Growth sobre esa definición devolverían solo conjuntos de tamaño uno, es decir un ranking de frecuencias disfrazado de minería de patrones.

El motivo es que el catálogo CUBSO identifica el objeto del proceso, y la mayoría de los procesos peruanos tienen un objeto único. La analogía del supermercado no se sostiene a nivel de acto administrativo.

Se midieron tres definiciones y se adopta la de entidad y mes. Frente a la trimestral: conserva más transacciones, y un mismo umbral de soporte relativo es más exigente cuando hay más transacciones; y es más interpretable, porque a escala trimestral la coocurrencia empieza a capturar simplemente que la entidad compra mucho.

### 5.2 Por qué el prefijo de 8 dígitos del código CUBSO

El código tiene 16 dígitos: los 8 primeros ubican el bien o servicio en la jerarquía del catálogo y los 8 últimos son el correlativo del ítem concreto. El código completo es casi único por ítem y produciría un universo tan disperso que ningún conjunto alcanzaría el soporte mínimo. Esa poda es en sí misma una decisión de diseño.

### 5.3 A-Priori frente a FP-Growth

A-Priori procede por niveles apoyándose en la antimonotonía: si un conjunto no es frecuente, ningún superconjunto suyo puede serlo. Eso poda el espacio, pero obliga a una pasada completa por las transacciones en cada nivel y a generar candidatos, cuyo número explota cuando el umbral baja.

FP-Growth comprime las transacciones en un árbol de prefijos y mina por proyecciones condicionales, sin generar candidatos, con dos pasadas por el dato.

Se corren los dos sobre la misma muestra y se verifica que devuelven exactamente los mismos conjuntos frecuentes. Esa verificación es lo que permite confiar en FP-Growth para el conjunto completo. A-Priori queda como implementación de referencia; su costo al bajar el umbral es precisamente la razón histórica por la que fue desplazado.

### 5.4 Lift y no confianza

Una confianza alta sobre un ítem que de por sí aparece en casi todas las transacciones no dice nada. El lift compara la confianza con la frecuencia base del consecuente, y es el que distingue una asociación real de una coincidencia por frecuencia. Filtrar solo por confianza traería reglas inútiles.

El compromiso que hay que nombrar: las reglas de soporte alto tienen lift cercano a uno, y las de lift alto viven en la zona de soporte bajo. El criterio de selección es lift alto con soporte suficiente para que la regla no sea una anécdota.

### 5.5 La canasta enriquecida

Con solo códigos de catálogo las reglas hablan de qué se compra junto. Para responder la pregunta que dejó abierta la Parte I, es decir dónde se concentra la falta de competencia, se agregan como ítems el método, el nivel de gobierno, el tramo de monto y una marca de postor único. Eso permite que emerjan reglas del tipo cierto rubro junto con cierto método implica un solo postor.

Al leerlas hay que descontar lo esperable: que una contratación directa tenga un solo postor es administrativamente normal y no indica nada irregular. Lo informativo son las combinaciones donde el procedimiento sí preveía concurrencia.

---

## 6. Parte VI. Las preguntas del enunciado

**Qué técnicas aportaron más valor.** Las que respondieron una pregunta planteada de antemano. El EDA y la curva de Lorenz contestan la concentración con un número. Las reglas sobre canasta enriquecida contestan dónde se concentra la falta de competencia. LSH aporta candidatos de entidades duplicadas, que es el paso que faltaba para interpretar la concentración. ANN aportó poco a las preguntas y mucho al aprendizaje sobre el compromiso entre exactitud y latencia, y conviene decirlo así en lugar de inflar su utilidad.

**Cuánto se pierde con los métodos aproximados.** Está medido y no estimado. MinHash con 128 hashes tiene error muy inferior al ancho de decisión de LSH. LSH pierde recall de forma controlada según bandas y filas, y lo que gana es evitar más del noventa y nueve por ciento de las comparaciones. Los índices aproximados pierden unos pocos puntos de recall. Bloom respeta su tasa teórica, Count-Min nunca subestima y respeta su cota, y DGIM queda muy por debajo de su cota del cincuenta por ciento.

**Qué se benefició de Spark.** La ingesta y el EDA, sin duda: 2,77 GB de CSV en 21 tablas se desnormalizan a una tabla analítica en menos de medio minuto. El agrupamiento por bandas de LSH, también, porque es un flatMap y un groupByKey sobre millones de pares. No se benefició la Parte III, donde FAISS en un nodo es mejor herramienta, ni la Parte IV, cuyo recorrido es secuencial con estado. Afirmar que todo mejoró con Spark sería falso.

**Qué cambiaría con diez o cien veces más volumen.** La fuerza bruta de la Parte III dejaría de ser viable y el índice aproximado pasaría de ser un ejercicio a ser obligatorio. El Count-Min empezaría a ganarle al diccionario exacto. A-Priori quedaría definitivamente fuera. El particionado por año dejaría de bastar y habría que subparticionar, probablemente por mes. Y la mala elección del número de particiones de barajado, que hoy la ejecución adaptativa amortigua casi por completo, pasaría a costar tiempo real.

**Implicancias sobre datos públicos peruanos.** Estas técnicas sirven a la transparencia y al control del gasto, y ese es el motivo de que los datos sean abiertos. Al mismo tiempo, un par de proveedores marcado como similar por LSH es una hipótesis estadística, no una acusación; una regla de asociación es una coocurrencia sobre datos de publicación, no una afirmación sobre la conducta de una entidad. El riesgo concreto de este tipo de trabajo es que un hallazgo estadístico se presente con el lenguaje de una conclusión. Los datos además tienen sesgos de publicación documentados en este proyecto, como la subcobertura de los meses recientes, que un lector apresurado leería como caída de la contratación.

---

## 6b. El reporte interactivo

### 6b.1 Por qué los datos van incrustados en el archivo

Una página abierta desde el disco con el esquema de archivo local no puede pedir un JSON vecino, porque el navegador lo bloquea por seguridad. Incrustar los agregados hace que el archivo funcione con un doble clic, sin levantar un servidor, que es lo que hace falta para entregarlo. Son unos setenta kilobytes, así que el costo es nulo.

### 6b.2 Qué se recalcula en vivo y qué no

La regla la da el enunciado: lo pesado se precalcula en Spark y lo barato se recalcula en el navegador. Hay cuatro módulos con parámetros ajustables.

1. La curva S de LSH según bandas y filas. Es una fórmula cerrada, uno menos uno menos s elevado a r, todo elevado a b. Moverla no cuesta nada y enseña algo que una figura fija no puede: que el par de bandas y filas no es un detalle de implementación sino la definición operativa de qué se considera parecido.
2. La tasa de falsos positivos del filtro de Bloom según bits por elemento y número de hashes. También cerrada, y sobre la curva se dibujan los puntos medidos de verdad sobre el flujo, que es lo que permite comprobar que la teoría y la implementación coinciden.
3. La cota de error del Count-Min Sketch según ancho y profundidad, con la misma estructura.
4. El filtrado de reglas por soporte, confianza y lift. Aquí no hay fórmula: se filtran las 218 reglas ya calculadas por FP-Growth. Es barato porque el cálculo pesado ya ocurrió.

Lo que no se recalcula es todo lo que exigiría volver a tocar el dato: las series temporales, los rankings, los Gini por departamento y las latencias de los índices. Esas vienen ya agregadas.

### 6b.3 Por qué D3 y no una biblioteca de gráficos de alto nivel

Porque tres de las cuatro figuras interactivas no son gráficos de catálogo sino curvas analíticas que hay que trazar punto a punto a partir de una fórmula, con un marcador que se mueve y una capa de referencia detrás. Una biblioteca de alto nivel resolvería las figuras estáticas más rápido y estorbaría en estas. D3 da control sobre escalas, ejes y eventos, que es lo que esta página necesita.

---

## 7. Lo que este trabajo no autoriza a concluir

1. Que un par de procesos con objeto casi idéntico implique fraccionamiento o colusión. Implica que dos textos se parecen.
2. Que una concentración alta implique conducta anticompetitiva. Puede reflejar especialización legítima, contratos de gran escala o el propio mecanismo de compra.
3. Que una regla de asociación con lift alto implique causalidad.
4. Que las cifras agregadas aquí sean cifras oficiales. Describen el paquete OCDS descargado, con sus sesgos de publicación, no el gasto público ejecutado.

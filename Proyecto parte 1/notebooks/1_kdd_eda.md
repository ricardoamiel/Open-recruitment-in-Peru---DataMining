# Notebook 1. KDD, análisis exploratorio y procesamiento distribuido

Guía de estudio del notebook [1_kdd_eda.ipynb](1_kdd_eda.ipynb). Explica qué hace cada sección, cómo funciona por dentro cada técnica, qué dice cada figura y qué decisiones se tomaron y se descartaron. El porqué más profundo de cada decisión está en [docs/JUSTIFICACION.md](../docs/JUSTIFICACION.md) y el guion de sustentación de cada figura en [docs/FIGURAS.md](../docs/FIGURAS.md).

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

Qué significa cada campo, cada código CUBSO y cada etiqueta del dato está en [docs/GLOSARIO.md](../docs/GLOSARIO.md).

## 1. Qué responde esta parte

El enunciado pide aplicar el proceso KDD completo y demostrar procesamiento distribuido. Este notebook hace las dos cosas y, de paso, produce la tabla de la que viven las otras cuatro partes.

Las tres preguntas de interés se fijan antes de mirar los datos, que es lo que distingue un análisis de una pesca de correlaciones.

1. Qué tan concentrado está el gasto en pocos proveedores, y si eso cambia por territorio.
2. Qué relación hay entre el número de postores y el monto adjudicado.
3. Si hay apresuramiento del gasto en el cierre del ejercicio presupuestal.

## 2. El dataset

Contrataciones Abiertas del Perú en el estándar **OCDS**, Open Contracting Data Standard, publicadas por el OECE, antes OSCE. Se descargan del [Registro de Datos de Open Contracting Partnership, publicación 135](https://data.open-contracting.org/es/publication/135), paquetes anuales 2023, 2024 y 2025.

Hay que saber explicar tres cosas del formato.

**Qué es OCDS.** Es un estándar internacional que describe una contratación pública como un proceso con etapas: planificación, licitación, adjudicación, contrato y ejecución. Cada proceso tiene un identificador único y estable llamado **ocid**. El paquete descargado trae 21 tablas en CSV que son la versión aplanada de ese documento JSON anidado: main, awards, awards_suppliers, awards_items, parties, contracts, tender_items y demás.

**Qué es el grano del dato.** Las 21 tablas tienen granos distintos. En main hay una fila por proceso; en awards_items hay una fila por ítem adjudicado, de modo que un proceso puede aparecer en veinte filas. Mezclar tablas sin cuidar el grano duplica montos, y ese es el error silencioso más común con estos datos.

**Qué es el código CUBSO.** Es el Catálogo Único de Bienes, Servicios y Obras del Estado peruano, derivado de la codificación UNSPSC. Tiene 16 dígitos: los 8 primeros ubican el bien o servicio en la jerarquía del catálogo y los 8 últimos son el correlativo del ítem concreto. El proyecto usa el prefijo de 8, porque el código completo es casi único por ítem y daría un universo tan disperso que ningún conjunto alcanzaría el soporte mínimo en la Parte V.

Volumen: 2,98 GB de CSV, 281.462 procesos crudos, 177.398 tras la limpieza, 29,8 MB en Parquet.

## 3. Entradas y salidas exactas

**Entrada.** Los tres paquetes anuales. La función **asegurar_datos** de notebooks/scripts/ingesta.py los descarga si faltan, de modo que el notebook corre de cero en otra máquina sin pasos manuales.

**Salida.** La tabla analítica en Parquet particionado por año, en data/processed, más 18 artefactos en CSV y JSON y 15 figuras en SVG y PNG.

## 4. El proceso KDD, que es el esqueleto del notebook

KDD, Knowledge Discovery in Databases, tiene cinco etapas y el notebook está ordenado por ellas. Conviene saber diferenciarlo de **CRISP DM**, que es un modelo de proceso de negocio con seis fases y un bucle explícito; KDD es más estrecho y se centra en el camino del dato.

| Etapa de KDD | Dónde está en el notebook | Qué produce |
| --- | --- | --- |
| Selección | Sección 1 | 5 tablas de 21, desnormalizadas a una fila por proceso |
| Preprocesamiento | Secciones 2 y 3 | Perfil de calidad y seis decisiones de limpieza con bitácora |
| Transformación | Sección 4 | Variables derivadas y Parquet particionado por año |
| Minería | Sección 5 | El análisis exploratorio, y las Partes II a V |
| Interpretación | Sección 8 y Parte VI | Las lecturas de cada figura y el reporte |

## 5. Recorrido sección por sección

### Sección 1. Selección

De las 21 tablas se usan 5 y se unen a una fila por proceso.

1. **main.csv** da el proceso: ocid, fecha de convocatoria, objeto, categoría, método, comprador, monto referencial en soles y número de postores.
2. **awards.csv** y **awards_suppliers.csv** dan el proveedor adjudicado. Un proceso puede tener varias adjudicaciones, así que se usa una ventana **row_number** ordenada por monto adjudicado descendente para quedarse con el proveedor de la mayor, y aparte se cuenta cuántos proveedores distintos hubo, que es una señal de fraccionamiento.
3. **awards_items.csv** da la canasta de códigos CUBSO del proceso, recortados a 8 dígitos y agregados con **collect_set**.
4. **parties.csv** da el departamento del comprador, filtrando por el rol buyer.

Dos detalles que hay que saber defender.

**Todo se lee como texto, con inferSchema en falso.** Si Spark infiriera el esquema, el código CUBSO de 16 dígitos pasaría a coma flotante y volvería en notación científica, perdiendo justo los dígitos que identifican el ítem. Los campos numéricos se convierten después, uno a uno y a propósito.

**La fecha es tender_datePublished y no publishedDate.** La primera es la fecha del evento, cuándo se convocó; la segunda es la fecha del registro, cuándo entró al paquete. Usar la del registro describiría la actividad del publicador y no la del Estado comprador.

### Sección 2. Perfilado y calidad

Antes de decidir nada se mide. El perfil cuenta nulos y cardinalidad de cada columna.

La cardinalidad se calcula con **approx_count_distinct**, que es **HyperLogLog**, con error relativo del 2 por ciento. Conviene saber por qué: contar distintos de forma exacta obliga a mantener en memoria todos los valores vistos, mientras que HyperLogLog guarda un arreglo de registros pequeños y estima la cardinalidad a partir del máximo número de ceros iniciales observado en el hash de cada valor. La intuición es que ver un hash con muchos ceros iniciales es improbable, así que su aparición sugiere que se han visto muchos elementos distintos. Para esta tarea solo hace falta el orden de magnitud, lo justo para distinguir un identificador de una categórica y de una continua, de modo que pagar un conteo exacto sería desperdicio.

El perfil deja ver tres cosas.

1. El monto no tiene ni un solo nulo, pero el valor faltante viene codificado como cero: 22.830 filas.
2. El proveedor falta en uno de cada cinco procesos, 61.807 filas, que son los desiertos, anulados o en trámite.
3. El año muestra trece valores distintos pese a que se bajaron tres paquetes anuales.

Esa tercera anomalía se investiga con una tabla cruzada de año del paquete contra año de convocatoria, que produce la **figura f01**. Si cada paquete trajera solo sus procesos, toda la masa estaría en la diagonal. No lo está: 82.946 filas son convocatorias anteriores a 2023, y en el paquete 2024 casi la mitad son de 2015 y 2016. Es el hallazgo que justifica recortar la ventana temporal.

### Sección 3. Limpieza

Seis decisiones. La política es que eliminar es la última opción y que cada decisión deja constancia: la función **limpiar** devuelve la tabla y una bitácora con cuántas filas tocó cada paso.

| Paso | Qué hace | Filas afectadas | Quedan |
| --- | --- | --- | --- |
| entrada | tabla analítica cruda | 0 | 281.462 |
| duplicados | una fila por ocid, la más reciente | 0 | 281.462 |
| descarte | monto nulo o no positivo | 22.830 | 258.632 |
| descarte | fecha fuera de 2023 a 2025 | 81.234 | 177.398 |
| imputación | postores con la mediana de su método | 6.655 | 177.398 |
| marca | monto extremo en escala logarítmica, se conserva | 565 | 177.398 |
| recorte | postores winsorizados al percentil 99,9, tope 107 | 263 | 177.398 |

Cómo defender cada una.

1. **Duplicados.** Ventana por ocid ordenada por fecha de registro descendente, se conserva la versión registrada más tarde. No elimina nada porque los ocid ya venían únicos, pero el paso se deja porque la unión de tres paquetes no garantiza esa unicidad.
2. **Monto no positivo.** El cero no es un monto bajo, es un campo no publicado. No admite imputación: poner la mediana inventaría gasto público que no existe y hundiría cualquier estimación agregada.
3. **Ventana temporal.** Es la consecuencia de la figura f01.
4. **Postores faltantes.** La ausencia no es al azar, se concentra en ciertos métodos, así que la mediana se calcula **dentro de cada método** y solo se cae a la mediana global si el método no tiene ninguna observación. Y se añade una columna booleana **n_postores_imputado**, de modo que todo análisis de competencia pueda excluir las filas imputadas y la relación no la produzca la propia imputación.
5. **Extremos de monto.** Se marcan y se conservan. El criterio es el intervalo intercuartílico pero aplicado sobre el logaritmo del monto y con factor 3 en lugar de 1,5, porque la distribución es de cola pesada y en escala lineal el criterio clásico marcaría como extremo una fracción enorme. El resultado es que 565 procesos, el 0,3 por ciento de las filas, concentran el 38 por ciento del gasto. Eliminarlos habría dejado una tabla más ordenada y habría borrado un tercio del dinero público que se quiere estudiar.
6. **Postores absurdos.** Aquí el extremo sí es error de carga y no tiene lectura sustantiva, así que se **winsoriza**, es decir se recorta al percentil 99,9, tope 107. Winsorizar no es eliminar: la fila sigue aportando monto, objeto y canasta.

Además hay una reparación de codificación. El SEACE grabó parte de los textos en CP850 y el registro los leyó como Latin-1, de modo que cada letra acentuada quedó convertida siempre en el mismo carácter equivocado. Once sustituciones deshacen esa conversión. Lo ambiguo se deja sin tocar, sobre todo el signo de interrogación invertido, que unas veces sustituye una tilde y otras está puesto a propósito, y se cuenta cuántas filas lo llevan para que el lector sepa el tamaño del residuo. La celda de verificación comprueba que los caracteres reparables quedan en cero.

La **figura f02** es la bitácora hecha gráfico: se pierden 104.064 filas en total, casi todas en dos pasos, y los demás pasos imputan, marcan o recortan sin perder ninguna.

Una columna resultó inservible y se documenta como tal: la duración de la convocatoria daba cero en todas las filas, porque la fecha de cierre de la licitación viene vacía en este paquete.

### Sección 4. Transformación y persistencia

Las variables derivadas son el año, el mes, el año y mes, y el nivel de gobierno.

El **nivel de gobierno** no viene en el dato crudo: se deriva con un CASE de expresiones regulares sobre el nombre de la entidad, con reglas para municipalidades, gobiernos regionales, universidades, establecimientos de salud, unidades educativas, fuerzas armadas y policiales, empresas del Estado y gobierno nacional. Es una heurística, y hay que presentarla como tal. La categoría Otro recoge lo que ninguna regla reconoce y es el 6,1 por ciento de los procesos; esa cifra es la medida honesta de cuánto falla la derivación y por eso se reporta.

La tabla se guarda en **Parquet particionado por año**. Dos propiedades que conviene saber explicar.

1. **Parquet es columnar.** Guarda los valores de una columna juntos y comprimidos, con estadísticas por grupo de filas. El análisis exploratorio lee dos o tres columnas de veinticinco en vez de la fila entera, y la compresión es mucho mejor porque los valores de una misma columna se parecen entre sí. De ahí que 2,98 GB de CSV queden en 29,8 MB.
2. **El particionado crea directorios.** Al escribir **partitionBy** por año Spark crea carpetas anio=2023, anio=2024 y anio=2025, y el año deja de almacenarse en los archivos: se lee del nombre de la carpeta.

La columna de partición se elige por cómo se consulta la tabla. El año es la correcta porque toda la Parte IV la recorre en orden temporal. Particionar por departamento habría dado veinticinco directorios muy desiguales, con Lima concentrando casi todo, y esa asimetría se paga en cada barajado.

### Sección 5. El análisis exploratorio, figura por figura

Todo el cálculo ocurre en Spark y a pandas solo llega el agregado ya reducido. Esa es la regla que hace que el EDA sea distribuido de verdad y no un **toPandas** disfrazado.

**f03, procesos por mes.** Diciembre es el máximo de su año en los dos años con cobertura completa: 7.280 procesos en 2023 y 6.498 en 2024. La cola de 2025 cae a 3.380 en noviembre y 942 en diciembre. Eso no es menos contratación sino subcobertura, porque los procesos tardan en entrar al registro OCDS. Es un sesgo de publicación y hay que decirlo, porque un lector apresurado lo leería como una caída del gasto.

**f04, monto por mes.** Se grafica aparte del conteo a propósito. Con dos series en un eje doble el lector lee una correlación que la figura no sostiene, y el eje doble permite elegir escalas que hagan coincidir dos curvas que no tienen por qué coincidir. El máximo de toda la serie es diciembre de 2024 con 14.373 millones de soles, 1,9 veces el mes anterior: a fin de año no solo se convoca más, se convoca más caro.

**f05, estacionalidad.** Es un mapa de calor de mes contra año y es la figura con la que se responde la pregunta 3. Aísla el efecto calendario del efecto año. Que el patrón del último trimestre se repita en 2023 y en 2024 es la evidencia mínima para atribuirlo al cierre del ejercicio presupuestal y no a un año particular. Con un solo año no se podría afirmar.

**f06, distribución del monto.** Histograma en escala logarítmica, con la mediana marcada. La media es 7,9 veces la mediana, así que la media no describe a ningún proceso representativo. En escala lineal esta figura sería una sola barra pegada al eje; el logaritmo es lo que la hace legible y es la misma escala sobre la que se aplicó el criterio de extremos, de modo que el criterio y su figura son coherentes.

**f07, método de contratación.** Contar procesos y contar soles dan rankings casi inversos. Adjudicación Simplificada encabeza por volumen con 82.503 procesos pero mueve 47,1 mil millones; Licitación Pública, con 9.242 procesos, mueve 106,6 mil millones, el 46 por ciento del total. La consecuencia práctica es que toda afirmación debe decir en qué unidad está contando: la mitad de las lecturas erróneas de datos de contratación vienen de mezclar las dos.

**f08, nivel de gobierno.** Los gobiernos locales convocan 73.456 procesos repartidos en 1.855 entidades y el gobierno nacional los supera en monto con 29.984 procesos y solo 277 entidades.

**f09, los quince compradores con mayor monto.** Se ordena por monto y no por número de procesos porque la pregunta es a dónde va el dinero, no quién hace más trámites. Suman 89,9 mil millones de soles.

**f10, los quince proveedores con mayor monto.** Aquí está el hallazgo que abre la Parte II: hay dos formas distintas de llegar arriba y el ranking las pone una al lado de la otra sin distinguirlas. Un proveedor acumula 581 millones repartidos en 188 adjudicaciones; otro alcanza 1.135 millones en una sola. Recurrencia y magnitud puntual son fenómenos que no se parecen.

**f11, curva de Lorenz y coeficiente de Gini.** Esta es la respuesta cuantitativa a la pregunta 1.

Cómo funciona. Se ordenan los proveedores de menor a mayor monto adjudicado y se dibuja, en el eje horizontal, la fracción acumulada de proveedores y en el vertical la fracción acumulada del monto. Si el reparto fuera perfecto la curva sería la diagonal. El **Gini** es el doble del área entre la diagonal y la curva, y va de 0, reparto perfecto, a 1, un solo proveedor se lleva todo.

El resultado es Gini 0,857 sobre 67.510 proveedores. El uno por ciento superior se lleva el 47,1 por ciento del monto, el cinco por ciento el 70,1, el diez por ciento el 80,2 y el veinticinco por ciento el 91,3. Para dar referencia: los Gini de ingreso de los países suelen estar entre 0,25 y 0,60, así que 0,857 es concentración alta. Lo que no permite afirmar es que la causa sea anticompetitiva: puede ser economía de escala, especialización técnica o barreras de entrada.

**f12, Gini por departamento.** Esta figura corrige lo que la anterior podría hacer creer. El Gini es adimensional, así que hace comparables mercados de tamaños muy distintos, cosa que el monto absoluto no permite. El resultado va en contra de lo esperado: solo 2 de 25 departamentos superan el Gini nacional, Pasco con 0,909 y Lima con 0,899. El resto queda por debajo. La cifra del país no describe a un mercado regional típico, está empujada hacia arriba por Lima. Se exige un mínimo de 50 proveedores por departamento para que el Gini sea estable.

**f13, competencia por tramo de monto.** Responde la pregunta 2 y el hallazgo es que hay dos fenómenos y no uno.

| Tramo | Procesos | Postores medianos | Con un solo postor |
| --- | --- | --- | --- |
| menos de 50 mil | 10.156 | 1 | 57,0 % |
| 50 a 200 mil | 83.628 | 7 | 10,1 % |
| 200 mil a 1 M | 55.872 | 11 | 8,7 % |
| 1 a 5 M | 15.931 | 15 | 10,0 % |
| 5 a 20 M | 3.998 | 18 | 9,7 % |
| más de 20 M | 1.158 | 19 | 11,4 % |

El número mediano de postores sí crece con el monto. Lo que importa es dónde se rompe: debajo de cincuenta mil soles el 57 por ciento tuvo un único postor, y en los demás tramos la proporción se estabiliza cerca del 10 por ciento y ya no baja ni por encima de veinte millones. Son dos cosas distintas, una franja pequeña competitiva solo en el papel y un suelo persistente de uno de cada diez procesos sin competencia. Ese suelo es la pregunta que recogen la Parte IV y la Parte V.

Se agrupa por tramos en lugar de graficar los puntos porque 170.743 puntos son una mancha negra sin estructura legible, y se excluyen los procesos con postores imputados.

### Sección 6. MapReduce sobre RDD frente a DataFrames y Spark SQL

Se implementan dos agregaciones en los dos estilos, cada una ligada a una pregunta: el monto por departamento alimenta la pregunta 1 y los postores por método alimentan la pregunta 2.

**Cómo se escribe el estilo MapReduce.** Se mapea cada fila a un par clave y valor, donde el valor lleva la suma parcial y el conteo, y se combina con **reduceByKey**. Hay que saber por qué se usa **reduceByKey** y no **groupByKey**: el primero aplica la función de combinación **dentro de cada partición antes de barajar**, exactamente como el combiner de MapReduce clásico, de modo que por la red solo viaja un par por clave y partición. Con **groupByKey** viajarían todos los valores.

**Cómo se verifica que dan lo mismo.** No se comparan sumas, que es fácil de hacer coincidir por casualidad, sino los conjuntos completos con **exceptAll** en los dos sentidos, que detecta filas sobrantes y faltantes.

**Cómo se mide el tiempo.** Con calentamiento previo y mediana de tres corridas, porque una sola corrida no es una medición: la primera paga la carga de clases de la máquina virtual de Java y la caché del sistema de archivos.

El resultado, en la **figura f14**, es que el camino RDD tarda entre 3,0 y 3,4 veces más. No es por gusto.

| Aspecto | MapReduce sobre RDD | DataFrame y Spark SQL |
| --- | --- | --- |
| Qué se escribe | Cómo transformar cada fila y cómo combinar los parciales | Qué resultado se quiere; el planificador decide cómo |
| Esquema | Spark ve tuplas opacas y no valida nombres ni tipos hasta ejecutar | Un error de columna se detecta al planificar |
| Optimización | La que escriba a mano el programador | Catalyst poda columnas, reordena filtros y elige la unión |
| Serialización | Cada fila cruza a Python, y ese es el costo dominante | El cómputo se queda en la máquina virtual de Java |
| Cuándo conviene igual | Estado entre elementos, estructuras propias, algoritmos iterativos | Seleccionar, filtrar, agrupar, unir y agregar |

Las dos causas de la brecha son la frontera entre la máquina virtual de Java y el intérprete de Python, que cada fila tiene que cruzar en los dos sentidos, y que el planificador no puede podar columnas ni reordenar filtros sobre tuplas opacas.

Si preguntan por qué implementar el RDD si el DataFrame siempre gana: porque la rúbrica pide demostrar MapReduce, y escribirlo obliga a declarar la clave, el valor y la función de reducción, que es justamente lo que Catalyst esconde; y porque el RDD sigue siendo la herramienta cuando la operación no se expresa en la API de DataFrames, que es lo que ocurre en las firmas MinHash de la Parte II.

### Sección 7. Particionado y plan de ejecución

Una partición es la unidad de paralelismo: Spark lanza una tarea por partición. Dos cosas se verifican leyendo el plan con **explain** en modo formateado en lugar de suponerlas.

1. Un filtro sobre la columna de partición aparece en **PartitionFilters**. Spark lo resuelve en el catálogo de archivos antes de leer un byte y abre un directorio de tres.
2. Un filtro sobre una columna no particionada aparece en **PushedFilters**. Spark abre los tres directorios pero usa las estadísticas por grupo de filas de Parquet, mínimo y máximo de cada columna en cada bloque, para saltar bloques sin descomprimirlos. Es una optimización real pero de segundo orden frente a no abrir el archivo.

La **figura f15** mide el tiempo de una agregación con 4, 16, 64 y 200 particiones de barajado, dos veces: con ejecución adaptativa y sin ella.

Con **ejecución adaptativa**, que es la configuración real, el parámetro casi no cambia el tiempo, porque Spark conoce el tamaño real de la salida del barajado y fusiona las particiones pequeñas, de modo que doscientas declaradas terminan siendo unas pocas efectivas. Al desactivarla aparece el efecto que predice la teoría: 0,32 segundos con 200 particiones frente a 0,14 con 16, porque planificar y recoger doscientas tareas de unos cientos de filas cuesta más que el cálculo.

La conclusión matizada, que es la que hay que decir: la regla de dos a cuatro veces el número de núcleos sigue siendo el punto de partida razonable, y la ejecución adaptativa protege contra declarar demasiadas particiones pero no contra declarar muy pocas, porque fusiona las pequeñas y no puede partir las grandes.

### Sección 8. Qué hereda cada parte

La tabla persistida deja listas tres representaciones que no hay que volver a construir.

1. El objeto contractual normalizado y con la codificación reparada, del que salen los shingles de la Parte II y los vectores TF-IDF de la Parte III.
2. El conjunto de códigos CUBSO por proceso, entrada de Jaccard y MinHash en la Parte II y base de la canasta de la Parte V.
3. La fecha de convocatoria con resolución de minuto, que ordena el flujo simulado de la Parte IV.

Y deja dos preguntas abiertas que otras partes recogen: si los proveedores distintos del ranking son en realidad la misma empresa, que es la Parte II, y en qué combinaciones de entidad, rubro y método se concentra el suelo de procesos sin competencia, que es la Parte V y, sobre una ventana reciente, la Parte IV.

## 6. Alternativas para cada decisión, explicadas

Cada decisión de esta parte tenía al menos otra opción razonable. Saber nombrarla, explicar qué hace y por qué se descartó es lo que distingue una decisión de una costumbre.

### Para los valores faltantes

1. **Imputar el monto cero con la mediana.** Es lo que se haría por defecto. Se descarta porque el cero no es un valor bajo sino un campo no publicado: imputarlo inventaría gasto público que no existe y, como la Parte I estima montos agregados, ese invento se propagaría a todas las conclusiones.
2. **Imputación por vecinos más cercanos.** Rellena con el promedio de las k filas más parecidas en las demás columnas. Es defendible para el número de postores, pero añade una estructura que después se usa como resultado: la Parte I analiza precisamente la relación entre postores y monto, de modo que imputar postores a partir del monto crearía la correlación que se quiere medir.
3. **Imputación múltiple por ecuaciones encadenadas.** Genera varias versiones del dataset y propaga la incertidumbre. Es lo correcto en inferencia estadística, y es desproporcionado aquí: el entregable no es un intervalo de confianza sino un análisis exploratorio.
4. **Lo que se hizo.** Mediana **condicional al método**, porque la ausencia no es al azar y se concentra en ciertos métodos, más una columna booleana que marca la fila como imputada para poder excluirla. Esa columna es la clave: permite que la figura f13 se calcule solo sobre datos observados.

### Para los valores extremos

1. **Puntuación z, es decir más de tres desviaciones típicas.** Supone normalidad. Con una distribución de cola pesada como el monto, la desviación típica está dominada por los propios extremos y el criterio deja de discriminar.
2. **Criterio de Tukey clásico, 1,5 veces el rango intercuartílico, en escala lineal.** Marcaría como extrema una fracción enorme de las filas, porque la distribución es asimétrica por naturaleza.
3. **Recorte por percentil, por ejemplo al 99.** Es arbitrario y además elimina.
4. **Bosque de aislamiento.** Detección multivariante de anomalías. Resuelve otro problema: aquí no se busca una fila rara en varias dimensiones, sino un monto alto, que es univariante y además es el objeto de estudio.
5. **Lo que se hizo.** Tukey con factor 3 sobre el logaritmo del monto, y **marcar en lugar de eliminar**. La escala logarítmica es la que hace simétrica la distribución, y el factor 3 en lugar de 1,5 reconoce que la cola es real. El resultado es que los 565 marcados concentran el 38 por ciento del gasto, que es justamente la razón para no borrarlos.

### Para el perfilado de cardinalidad

1. **Conteo exacto de distintos.** Obliga a mantener todos los valores vistos. Sobre 25 columnas y 281.462 filas es un gasto innecesario para una decisión que solo necesita el orden de magnitud.
2. **Flajolet y Martin.** El antecesor de HyperLogLog: estima la cardinalidad a partir del máximo número de ceros iniciales en los hashes de los elementos. Tiene varianza alta con un solo estimador.
3. **Lo que se hizo.** HyperLogLog, que es Flajolet y Martin promediando muchos registros con media armónica y corrigiendo el sesgo, con error relativo fijado en el 2 por ciento.

### Para la duplicación

1. **Desduplicación difusa por nombre.** Dos proveedores escritos distinto que son la misma empresa. No se hace aquí a propósito: es precisamente el problema de la Parte II, y resolverlo con una regla de texto antes de medirlo sería dar por supuesto lo que se quiere demostrar.
2. **Lo que se hizo.** Desduplicación exacta por ocid, conservando la versión registrada más tarde.

### Para el modelo de proceso

1. **CRISP-DM.** Seis fases, con comprensión del negocio al inicio y despliegue al final, y bucles explícitos. Es un modelo de proyecto.
2. **SEMMA.** Muestrear, explorar, modificar, modelar y evaluar. Está centrado en el modelado y da por hecha la fase de datos.
3. **Lo que se hizo.** KDD, porque es el que el curso usa y porque su foco es el camino del dato, que es lo que esta parte entrega. Se menciona CRISP-DM porque la diferencia es una pregunta probable.

### Para el almacenamiento

1. **CSV.** Lo que vino. Fila a fila, sin esquema y sin compresión por columna.
2. **ORC o Avro.** ORC es también columnar y comparable a Parquet; Avro es por filas, bueno para escribir flujos y malo para agregar columnas sueltas.
3. **Particionar por departamento.** Veinticinco directorios muy desiguales, con Lima concentrando casi todo. La asimetría se paga en cada barajado y ninguna parte recorre la tabla por territorio.
4. **No particionar.** Pierde la poda de directorios, que es lo que hace que un filtro por año no abra dos tercios de los archivos.
5. **Lo que se hizo.** Parquet particionado por año, porque toda la Parte IV recorre la tabla en orden temporal.

### Para el procesamiento

1. **pandas sobre la máquina entera.** Cabría, con 177 mil filas. No demostraría lo que la rúbrica pide y no serviría al escenario de diez veces más volumen.
2. **Solo DataFrames, sin RDD.** Sería lo más rápido, pero el RDD es donde se ve MapReduce con su clave, su valor y su función de reducción, que es justo lo que Catalyst esconde.
3. **Lo que se hizo.** Las dos, con la misma agregación, verificando que coinciden y midiendo la diferencia.

## 7. Preguntas probables y qué responder

**¿Por qué eliminar el 37 por ciento de las filas no es demasiado?** Porque está concentrado en dos decisiones defendibles, el monto no publicado y la ventana temporal, y los otros cinco pasos juntos no pierden ninguna fila.

**¿Cómo saben que la caída de 2025 es subcobertura y no una caída real del gasto?** Porque el patrón de los dos años completos es el inverso, con máximo en diciembre, y porque la caída empieza justo donde termina la ventana de publicación del registro.

**¿Qué confianza tiene el nivel de gobierno si es una expresión regular?** La medimos en lugar de suponerla: la categoría Otro es el 6,1 por ciento y esa cifra es la cota de error de la derivación.

**¿Un Gini de 0,857 es mucho?** Comparado con el caso teórico, cero es reparto perfecto y uno un solo proveedor; y comparado con los Gini de ingreso de los países, que suelen estar entre 0,25 y 0,60, es concentración alta. No permite afirmar conducta anticompetitiva.

**¿Qué aporta Spark aquí de verdad?** La ingesta y el análisis exploratorio, sin duda: 2,98 GB en 21 tablas por año se desnormalizan a una tabla analítica en menos de medio minuto. Y queda demostrado con medición, no con afirmación, dónde conviene cada API.

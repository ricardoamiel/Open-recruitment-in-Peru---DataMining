# Notebook 1. Transformación y construcción de la base relacional con Spark

Guía de estudio del notebook [1_base_relacional.ipynb](1_base_relacional.ipynb). Recorre el notebook sección por sección, explica por dentro cada técnica, interpreta cada figura, dice qué se descartó y por qué, y cierra con las preguntas previsibles de la sustentación.

**Integrantes:** Ricardo Acuña, Juan Aquino y Camilo Soto.

## 1. Qué responde esta parte

El enunciado pide dejar lista, sobre Spark, la base relacional que alimentará a las demás partes: vectores de características, una matriz de interacción y un grafo. Pero esta parte no es solo infraestructura. Al construir esos tres objetos aparecieron tres hechos que cambian lo que se puede concluir después, y conviene saberlos contar como hallazgos y no como detalles técnicos:

1. **La identidad del proveedor no es confiable en el dato publicado.** La mitad de los identificadores son códigos de consorcio, y 4 de cada 10 están repetidos.
2. **El mercado se renueva.** Tres de cada cuatro relaciones entidad y proveedor de 2025 son nuevas.
3. **Hay pares de proveedores que se presentan juntos casi siempre.** 4.897 pares coinciden en el 80 por ciento o más de las participaciones del menos activo.

**Dónde corre:** todo en Spark, como exige el enunciado, con una sesión local acotada a 2 GB y 3 hilos.

## 2. Las tres preguntas del proyecto

El notebook abre con las preguntas que guían todo el proyecto 2, porque el enunciado exige preguntas propias y no descriptivas:

1. ¿Qué tipos de proveedor existen y cuáles combinan dependencia de un solo cliente con poca competencia? Se responde en la Parte II.
2. ¿Es predecible con quién contrata una entidad, y qué relaciones se salen de lo esperable? Se responde en la Parte III.
3. ¿Quiénes son los actores centrales y hay grupos de proveedores que compiten siempre entre sí? Se responderá en las Partes IV y V.

Las tres se presentan siempre como señales para priorizar una revisión, nunca como acusaciones. Es el encuadre ético que pide el enunciado.

## 3. El vocabulario mínimo

1. **Entidad.** El comprador estatal: una municipalidad, un gobierno regional, un hospital, un ministerio. Hay 2.968.
2. **Proveedor.** Quien vende al Estado: empresa, persona natural, consorcio o extranjero.
3. **Participante o postor.** Proveedor que se registró en un proceso. Gane o pierda, es participante.
4. **Adjudicación.** El acto que decide a quién se le compra. Un proceso puede tener varias, una por ítem o por lote.
5. **Contrato.** El documento que se firma después de la adjudicación. No siempre está publicado.
6. **Familia CUBSO.** Los cuatro primeros dígitos del código del Catálogo Único de Bienes, Servicios y Obras. Es la granularidad de un mercado, por ejemplo medicamentos o maquinaria pesada. Hay 368 en la ventana.
7. **Grano.** Lo que representa una fila. Aquí el grano de la tabla de hechos es una adjudicación a un proveedor, que lleva la entidad, el proveedor y la familia del ítem.

## 4. Recorrido sección por sección

### Sección 1. Del proceso a la relación

La tabla limpia del proyecto 1 tiene una fila por proceso y guarda solo al proveedor de la adjudicación mayor. Servía para describir el gasto, pero para construir relaciones le faltan dos cosas: los demás proveedores adjudicados de un mismo proceso, que son 6.342 procesos con más de un proveedor, y todos los postores que perdieron, que son la materia prima del grafo de competencia.

Por eso se vuelve a los CSV crudos solo para cuatro tablas, siempre restringidas a los 177.398 procesos ya limpios: tender_tenderers, awards_suppliers, awards, contracts y awards_items. Resultan 2.253.911 participaciones y 156.629 adjudicaciones.

**Por qué se escribe un Parquet intermedio.** Leer 3 GB de CSV es lo más caro del notebook. Se hace una vez y se guarda en data/processed/intermedio; las corridas siguientes lo reutilizan, y borrar la carpeta fuerza la relectura.

### Sección 2. Enlaces incompletos

| Caso | Filas | Porcentaje |
| --- | --- | --- |
| Adjudicación con contrato | 143.030 | 90,7 % |
| Adjudicación sin contrato | 14.653 | 9,3 % |
| Contrato sin adjudicación | 1.169 | 0,7 % |
| Adjudicación sin proveedor | 1.054 | 0,7 % |

**Figura f01.** Porcentaje de adjudicaciones sin contrato por método. La falta de contrato no es aleatoria: en Concurso Público de Servicios llega al 17 por ciento, casi el doble del promedio.

**La decisión y su porqué.** La arista entidad a proveedor es la adjudicación, con o sin contrato, y la falta de contrato queda como atributo con_contrato. Tres razones: la adjudicación es el acto que decide a quién se le compra; descartar las que no tienen contrato borraría casi una de cada diez relaciones y lo haría de forma sesgada, porque se concentran en ciertos métodos; y conservar la marca permite a cualquier análisis posterior filtrarlas si lo necesita. Los contratos sin adjudicación se descartan porque no tienen un proveedor confiable al cual atribuirlos.

### Sección 3. Resolución de entidades

**3.1 Compradores.** Se cruzó el identificador de catálogo de cada entidad con su RUC. Resultado: relación uno a uno perfecta, cero identificadores con dos RUC y cero RUC con dos identificadores. Los dos únicos nombres repetidos son municipalidades distritales homónimas de departamentos distintos, Mariscal Cáceres en Huancavelica y Arequipa, y San Miguel en Puno y Lima. Son entidades distintas y fusionarlas sería un error. **El lado comprador no necesita resolución.**

**3.2 Proveedores.** Aquí está el problema que advierte la fuente. Todos los identificadores llevan el prefijo PE-RUC, pero no todos son un RUC. El prefijo del número dice qué es:

| Tipo | Cómo se reconoce | Identificadores | Tratamiento |
| --- | --- | --- | --- |
| Empresa | RUC de 11 dígitos que empieza en 20 | 71.146 | El RUC es la identidad |
| Persona natural | RUC que empieza en 10, 15 o 17 | 32.017 | El RUC es la identidad |
| Consorcio | código interno de 6 o 7 dígitos | 105.881 | Nombre normalizado más departamento, validado |
| Extranjero | código que empieza con L, o falso RUC 99 | 2.741 | Nombre normalizado |

**Normalización del nombre.** Mayúsculas, sin tildes, sin puntuación y sin forma jurídica, porque S.A.C., SAC y SOCIEDAD ANONIMA CERRADA son la misma empresa.

**El paso clave: validar la hipótesis con el propio dato.** Usar nombre más departamento como clave de un consorcio es una hipótesis, porque hay más de 160 consorcios distintos llamados Santa Rosa en el país. La validación es una observación simple: **dos códigos que participaron en el mismo proceso son, con certeza, dos proveedores distintos, porque nadie compite contra sí mismo.** Resultado: 1.655 claves agrupaban 12.829 códigos que compitieron entre sí, y esas claves no se fusionan; cada código vuelve a ser su propio proveedor.

**El segundo paso: nombres casi iguales con MinHash y LSH.** La clave exacta no ve variantes como CONSORCIO SUPERVISOR VILLAREAL y VILLARREAL, o el mismo consorcio con y sin la palabra CONSORCIO. Se reutiliza el método del proyecto 1, escrito con DataFrames de Spark:

1. Se quita la palabra CONSORCIO y se **ordenan las palabras**, porque FRANCO SANTOS TANIA y TANIA FRANCO SANTOS son la misma persona.
2. Tejas de 3 caracteres del nombre.
3. Firma MinHash de 40 funciones: para cada función hash, el mínimo sobre las tejas. La probabilidad de que dos nombres compartan ese mínimo es exactamente su similitud de Jaccard.
4. LSH con 10 bandas de 4 filas: dos nombres son candidatos si coinciden en las 4 filas de al menos una banda.
5. Cada candidato se verifica con su Jaccard exacto y se fusiona si es al menos 0,85.
6. Solo se comparan nombres del mismo tipo, y en consorcios del mismo departamento.
7. Los números y romanos sueltos deben coincidir, porque CONSORCIO VIAL AN 104 y VIAL AN 107 son consorcios distintos aunque su Jaccard sea 0,8.

Los pares fusionables se unen con union-find y se vuelve a aplicar la validación de rivalidad. Resultado: 140.582 candidatos, 1.420 fusiones y 82 grupos deshechos por rivalidad, en 50 segundos.

**Por qué no el MinHashLSH de Spark MLlib.** Se probó primero y no terminó en veinte minutos. Sus bandas tienen una sola fila, así que dos nombres son candidatos si coinciden en un solo mínimo de entre seis. Como casi todos los consorcios comparten las tejas de la palabra CONSORCIO, casi todos los pares chocaban. Con 4 filas por banda, el umbral de la curva S es (1/10) elevado a 1/4, unos 0,56, y un par con Jaccard 0,85 sigue siendo candidato con probabilidad mayor a 0,999. Es la misma lección del proyecto 1: las filas por banda son lo que hace selectivo a LSH.

**Figura f02.** Identificadores publicados frente a proveedores resueltos, por tipo. 105.881 códigos de consorcio son 62.045 consorcios, una reducción del 41 por ciento; los extranjeros bajan un 24 por ciento; empresas y personas naturales no cambian. En total, 211.785 identificadores pasan a 167.293 proveedores.

**Cómo contarlo como hallazgo.** Sin este paso, un consorcio que gana diez obras en un departamento aparece como diez proveedores de una obra cada uno: justo el patrón de concentración que se quiere detectar queda escondido por un artefacto de registro. **Acción propuesta:** que el OECE asigne a cada consorcio un identificador estable vinculado a los RUC de sus integrantes.

### Sección 4. La tabla de hechos

Una fila por adjudicación y proveedor resuelto, con la entidad, la familia CUBSO de su ítem principal, el monto en soles y el contexto del proceso. Son 156.629 filas, escritas en Parquet **particionado por año**. La familia del ítem principal es la de mayor valor dentro de la adjudicación. En el 2 por ciento de adjudicaciones en moneda extranjera se usa el valor referencial en soles del proceso, que la fuente ya trae convertido.

### Sección 5. Vectores de características

| Característica del proveedor | Qué mide |
| --- | --- |
| n_ganados, monto_total, monto_mediano | Escala |
| n_entidades, n_departamentos | Alcance |
| cuota_cliente_top | Dependencia de su mayor cliente |
| n_familias | Especialización |
| meses_activos | Continuidad |
| tasa_victoria, n_participaciones | Éxito competitivo |
| pct_postor_unico, pct_sin_concurso | Cuánto gana sin rivales o sin concurso |
| pct_obras, pct_servicios | Rubro dominante |
| pct_sin_contrato | Calidad del enlace |

Para la entidad: volumen, número de proveedores, índice de Herfindahl de su gasto entre proveedores, postores medios, porcentaje con un solo postor y sin concurso, y variedad de familias.

Se guardan en su escala natural; la estandarización se decide en la Parte II, donde se usan.

**Figura f03.** Tres histogramas: adjudicaciones ganadas, cuota del mayor cliente y tasa de victoria. El proveedor típico es pequeño y de un solo cliente: el 79 por ciento de los 63.204 proveedores con alguna adjudicación le vendió a una sola entidad en tres años, y la mediana de adjudicaciones es 1. La cuota del mayor cliente se amontona en 1, y es lo que pasa cuando se gana una sola vez. Por eso la dependencia solo es informativa entre recurrentes: entre los 12.235 con tres o más adjudicaciones, 4.277 obtienen al menos el 80 por ciento de su monto de una sola entidad.

### Sección 6. Matrices de interacción

| Matriz | Filas | Columnas | Celdas llenas | Densidad |
| --- | --- | --- | --- | --- |
| Entidad por proveedor | 2.964 | 63.204 | 107.701 | 0,0575 % |
| Entidad por familia | 2.955 | 368 | 35.454 | 3,26 % |

La señal implícita es el número de adjudicaciones, y se guarda también el monto y el año, para poder evaluar la recomendación con una partición temporal.

**Figura f04.** Distribución complementaria acumulada del grado en escala logarítmica, para entidades y para proveedores. La mediana de entidades por proveedor es 1 y la de proveedores por entidad es 16; el 10 por ciento de entidades con más proveedores reúne el 49 por ciento de las relaciones. **Consecuencia para la Parte III:** la mayoría de proveedores tiene una sola entidad de historia, así que el filtrado colaborativo puro no puede decir nada de ellos y hace falta un perfil de contenido.

**El hallazgo de la renovación.** De los 37.529 pares entidad y proveedor activos en 2025, solo el 26,3 por ciento ya había contratado en 2023 o 2024. Esos pares repetidos pesan el 32 por ciento de las adjudicaciones y el 17 por ciento del monto. **La relación nueva es la norma.** Un tablero que solo mire relaciones conocidas deja fuera la mayor parte de lo que pasa, y anticipar la relación nueva es el trabajo del recomendador de la Parte III.

### Sección 7. Grafo de coparticipación

**Nodos:** proveedores resueltos. **Arista:** dos proveedores participaron en el mismo proceso. Es la relación de competencia.

**Por qué coparticipación y no un grafo KNN.** Aquí la relación existe en el dato y no hay que inventarla. Un grafo KNN uniría proveedores parecidos en sus características; la coparticipación une proveedores que efectivamente se encuentran.

**El criterio de aristas, con sus tres decisiones medidas:**

1. **Tope de 50 participantes por proceso.** Un proceso con n participantes genera n(n-1)/2 pares; con 300 son 44.850 aristas que no dicen nada.
2. **Peso de Newman, 1/(n-1).** Competir en un proceso de 3 dice más que competir en uno de 40.
3. **Mínimo de 2 procesos compartidos.** Una sola coincidencia puede ser azar.

El autojoin de todas las participaciones produce 32.979.939 pares en 26 segundos, y se persiste en disco para medir las nueve combinaciones.

**Figura f05.** Mapa de calor de millones de aristas según tope y mínimo. El criterio que más pesa es el mínimo: con una coincidencia hay 12,2 millones de aristas y con dos, 4,2 millones. Se adopta tope 50 y mínimo 2: 2.528.285 aristas y 70.843 nodos.

**Figura f06.** Grado de los proveedores y cuántas veces coincide cada par. La componente gigante reúne al 97 por ciento de los nodos: la competencia forma una sola red. Hay pares que coinciden en más de 2.000 procesos, pero **eso no es por sí solo una señal**: hay proveedores que se registran en miles de procesos, hasta 8.476 en tres años, y dos participantes masivos coinciden por pura frecuencia.

**De la coincidencia a la afinidad.** La afinidad de un par es procesos compartidos dividido entre el mínimo de las participaciones de los dos, el coeficiente de solapamiento. Una afinidad de 0,9 dice que, de las veces que el menos activo se presentó, nueve de cada diez estuvo el otro. Se exigen al menos 10 procesos compartidos.

**Figura f07.** Dispersión de procesos compartidos contra afinidad. De 245.120 pares con 10 o más procesos compartidos, 4.897 tienen afinidad de 0,8 o más. Es el patrón que las guías de competencia asocian a ofertas de acompañamiento, pero también el de empresas vinculadas o de un mercado regional con dos oferentes. **Acción propuesta:** usar esos pares como cola de revisión, cruzando quién gana cuando se presentan juntos y si el perdedor alguna vez gana solo.

### Sección 8. Particionamiento y plan de ejecución

Tres decisiones, cada una con su plan físico y su tiempo medido:

1. **Particionado en disco por año.** El plan muestra un PartitionFilter: al filtrar 2025, Spark ni abre los archivos de los otros años. Leyó 2,6 veces más rápido, 0,05 frente a 0,13 segundos.
2. **Broadcast frente a sort merge.** Al unir los hechos con la tabla de entidades, que es pequeña, Spark elige un BroadcastHashJoin: copia la tabla pequeña a cada tarea y no baraja la grande. Forzando un SortMergeJoin, que baraja los dos lados, la consulta tardó 0,17 segundos frente a 0,14. **A esta escala la ventaja es pequeña**, porque la tabla de hechos tiene 156 mil filas; crece con el tamaño de la tabla grande, que es la que el broadcast evita mover.
3. **Particiones de barajado en el autojoin del grafo.** El plan muestra un Exchange hashpartitioning por ocid, que lleva los participantes de cada proceso a la misma partición. Se mide con la ejecución adaptativa apagada, para que Spark no corrija el valor por su cuenta.

| Particiones | Segundos |
| --- | --- |
| 1 | 23,2 |
| 8 | 7,2 |
| 64 | 6,7 |
| 200 | 8,5 |

**Figura f08.** Tiempo del autojoin según particiones. **La única diferencia robusta es la de una sola partición**, 3,4 veces el mejor caso, porque toda la agregación queda en un hilo. Entre 8, 64 y 200 la diferencia es de un 26 por ciento y **el orden cambió entre corridas**: en una corrida anterior el mínimo estuvo en 8 y 64, y en otra en 200. La máquina estaba compartida con otro trabajo, y esa variación es del tamaño de la carga. Lo que sí se sostiene es el criterio: al menos tantas particiones como hilos para usar el paralelismo, y no cientos de tareas pequeñas si las particiones no son grandes. La sesión usa 8 con la ejecución adaptativa encendida.

**Cómo contarlo en la sustentación.** Decir que una medición no es concluyente es parte del resultado. Lo honesto es separar lo robusto, una partición es siempre la peor, de lo que depende de la carga de la máquina.

### Sección 9. Lo que queda listo

| Tabla | Contenido | Filas | La usa |
| --- | --- | --- | --- |
| hechos | adjudicación y proveedor resuelto, por año | 156.629 | todas |
| participaciones | proceso y participante resuelto | 2.253.911 | IV, V |
| mapa_proveedores | identificador publicado y su clave | 211.785 | todas |
| caracteristicas_proveedores | un vector por proveedor | 63.204 | II, VI |
| caracteristicas_entidades | un vector por entidad | 2.968 | II, IV |
| interaccion_entidad_proveedor | entidad, proveedor, año, adjudicaciones, monto | 125.757 | III, IV |
| interaccion_entidad_familia | entidad, familia, año, adjudicaciones, monto | 55.346 | III, VI |
| grafo_nodos | proveedor con grado, fuerza y participaciones | 70.843 | IV, V, VI |
| grafo_aristas | par, procesos compartidos y peso de Newman | 2.528.285 | IV, V, VI |

## 5. Técnicas consideradas y descartadas

1. **MinHashLSH de Spark MLlib para nombres.** No terminó: bandas de una fila hacen colisionar a casi todos los consorcios.
2. **Fusionar consorcios solo por nombre.** Agruparía consorcios distintos con nombres genéricos; la validación por rivalidad lo demostró.
3. **Descartar adjudicaciones sin contrato.** Borraría el 9 por ciento de las relaciones de forma sesgada por método.
4. **Grafo KNN sobre los vectores.** Inventaría una relación que el dato ya trae.
5. **Grafo con una sola coincidencia.** 12 millones de aristas dominadas por coincidencias únicas.
6. **Ordenar pares por número de coincidencias.** Encuentra participantes masivos, no relaciones; se reemplaza por la afinidad.
7. **Componentes conexos distribuidos para el union-find.** Los pares a unir son unos miles; en el driver es más simple y suficiente.

## 6. Preguntas previsibles y su respuesta

**¿Por qué volver a los CSV crudos si el proyecto 1 ya tenía la base limpia?** Porque la base del proyecto 1 tiene una fila por proceso con un solo proveedor. Para relaciones hacen falta todos los adjudicados y todos los postores. La base limpia se usa igual: define los 177.398 procesos válidos y todo se restringe a ellos.

**¿Cómo saben que la resolución de entidades no fusiona proveedores distintos?** Por la validación de rivalidad: dos códigos que compitieron en el mismo proceso no pueden ser el mismo proveedor. Toda clave que juntara rivales se deshizo, tanto en el paso exacto como en el difuso.

**¿Y que no deja duplicados sin fusionar?** No se puede garantizar. Un consorcio con nombre genérico que opera en un departamento con homónimos rivales queda partido en varios nodos. Es un error conservador: preferimos dos nodos para un proveedor antes que un nodo para dos.

**¿Por qué el umbral de 0,85 de Jaccard?** Porque en una primera pasada con 0,8 aparecían fusiones falsas de nombres cortos, como BICENTENARIO y CENTENARIO, y con 0,85 más la regla de números las muestras revisadas son variantes del mismo nombre.

**¿Por qué coparticipación y no adjudicación para el grafo de proveedores?** Porque la adjudicación une proveedor con entidad, y esa relación ya está en la matriz de interacción, que también es un grafo bipartito para la Parte IV. Entre proveedores, la relación observable es haber competido en el mismo proceso.

**¿Una afinidad alta prueba colusión?** No. Es una señal descriptiva con explicaciones legítimas: dos empresas del mismo grupo, o los dos únicos oferentes de un rubro en una región. Sirve para ordenar qué revisar primero.

**¿Por qué Spark si todo cabe en una máquina?** Porque el enunciado lo exige en esta parte y porque el código es el mismo que correría distribuido. Además se usan sus primitivas de verdad: lectura de 3 GB de CSV, autojoin de 33 millones de pares con spill a disco, particionado por año y broadcast, cada una con su plan físico mostrado y su tiempo medido.

**¿Qué hace la ejecución adaptativa?** Ajusta el plan con estadísticas reales al terminar cada etapa: fusiona particiones pequeñas después de un barajado y puede cambiar un sort merge por un broadcast si descubre que un lado es pequeño. Por eso se apaga al medir las particiones, para que no corrija el valor que se está midiendo.

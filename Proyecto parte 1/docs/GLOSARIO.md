# Glosario del dato

Qué significa cada campo, cada código y cada etiqueta del dataset de contrataciones públicas del Perú que usa el proyecto. Está pensado para la sustentación: si en la presentación aparece un rubro 8013 o un Régimen Especial, aquí está qué es y de dónde salió.

Las cifras son las de la tabla analítica construida en la Parte I, es decir 177.398 procesos de 2023 a 2025. El porqué de cada decisión de limpieza está en [JUSTIFICACION.md](JUSTIFICACION.md) y el recorrido del notebook en [notebooks/1_kdd_eda.md](../notebooks/1_kdd_eda.md).

## 1. De dónde viene el dato

1. **OCDS**, Open Contracting Data Standard. Es un estándar internacional para publicar contratación pública con una estructura común, de modo que un mismo análisis pueda correr sobre países distintos. El Perú publica sus contrataciones en este formato.
2. **Paquete anual.** La descarga viene en un paquete por año, y cada paquete son **21 tablas CSV** que son la versión plana del documento OCDS, una por nivel de anidamiento. El proyecto usa **5 de las 21**, lo justo para el grano de proceso.
3. **ocid**, Open Contracting Identifier. Es la llave del proceso de contratación, única y estable a lo largo de todas las tablas. Se ve así: ocds-dgv273-seacev3-1000028. Hay 177.398 valores distintos y ninguno repetido, porque el grano de la tabla analítica es exactamente un proceso.
4. **SEACE** es el Sistema Electrónico de Contrataciones del Estado, la plataforma donde las entidades publican. El prefijo seacev3 del ocid viene de ahí.

**Las cinco tablas que se usan y para qué:**

| Tabla cruda | Qué aporta |
| --- | --- |
| main.csv | El proceso: fechas, objeto, método, categoría, comprador, monto y número de postores |
| awards.csv | El monto de cada adjudicación, usado para quedarse con la mayor cuando hay varias |
| awards_suppliers.csv | Quién ganó, es decir el proveedor, y cuántos proveedores distintos hubo |
| awards_items.csv | Los ítems adjudicados con su código CUBSO y su descripción, que es la canasta de la Parte V |
| parties.csv | Los participantes y su rol, de donde sale el departamento de la entidad compradora |

## 2. Los actores, que es la confusión más común

1. **Entidad, o entidad compradora.** El Estado que compra. En el dato es el campo **comprador_id** y hay 2.968 distintas. Puede ser una municipalidad distrital, un gobierno regional, un hospital, una UGEL, un ministerio, una universidad pública, una empresa del Estado o un programa social.
2. **Postor.** La empresa o persona que se presenta a competir en un proceso. Lo que se cuenta en **n_postores**.
3. **Proveedor, o adjudicatario.** El postor que ganó. En el dato es **proveedor_id** y hay 67.510 distintos.

La regla para no equivocarse: **postor es el que compite, proveedor es el que ganó, entidad es la que paga.** Todo postor es una empresa; la entidad nunca lo es, aunque haya empresas del Estado entre los compradores.

## 3. El ciclo de un proceso y qué significa que falte algo

1. **Convocatoria.** La entidad publica el proceso con su objeto, su valor estimado y su método. La fecha de esa publicación es el campo **fecha**.
2. **Presentación de ofertas.** Se presentan los postores, y su número queda en n_postores.
3. **Adjudicación.** Se elige al ganador, que queda en proveedor_id. Un proceso puede tener **varias adjudicaciones**, por ejemplo un proceso por ítems en el que cada lote lo gana una empresa distinta. Se guarda el proveedor de la adjudicación de mayor monto y aparte el conteo, porque tener varios proveedores en un mismo proceso es una señal de fraccionamiento que conviene medir. Ocurre en 6.342 procesos.
4. **Un proceso sin adjudicación** quedó desierto, fue anulado o seguía en trámite cuando se publicó el paquete. Son 31.373, el 17,7 por ciento. No es un error del dato, así que el proyecto lo **marca** con el campo adjudicado en lugar de borrarlo.

## 4. Los campos de la tabla analítica

| Campo | Qué es | Detalle que conviene saber |
| --- | --- | --- |
| ocid | Llave del proceso | Única, 177.398 valores |
| fecha | Cuándo se convocó el proceso | Es tender_datePublished, el evento, no el registro |
| fecha_registro | Cuándo lo publicó el sistema | Es publishedDate. Se separa a propósito porque el paquete anual republica procesos convocados años antes, y usar esta fecha describiría la actividad del publicador y no la del Estado comprador |
| objeto | La descripción libre del proceso | 237.298 valores distintos en el dato crudo. Es el texto sobre el que trabajan las Partes II y III |
| categoria | goods, services o works | Bienes 79.287, servicios 78.135, obras 19.976 |
| metodo | El procedimiento de selección | 40 valores distintos, dominados por doce |
| comprador_id, comprador_nombre | La entidad compradora | 2.968 entidades |
| nivel_gobierno | Nivel al que pertenece la entidad | Campo **derivado**, no viene en el dato. Ver la sección 7 |
| departamento | Departamento de la entidad | Sale de parties.csv. Es dónde está la entidad, **no** dónde se ejecuta la obra |
| monto_pen | Valor del proceso en soles | Es el **valor referencial o estimado de la convocatoria**, no lo que finalmente se pagó. Mediana 178 mil soles, máximo 1.135 millones |
| moneda | Moneda original | 98,2 por ciento en soles; el resto se convierte |
| n_postores | Cuántos compitieron | Mediana 9, máximo 107 tras el recorte |
| proveedor_id, proveedor_nombre | Quién ganó | Nulo si el proceso no se adjudicó |
| n_proveedores | Cuántos proveedores distintos ganaron en el proceso | Mayor que uno en 6.342 procesos |
| items | Los códigos CUBSO adjudicados | Es la canasta de la Parte V. Ver la sección 5 |
| n_items | Cuántos ítems tiene el proceso | Cero en 52.838 procesos: 31.369 porque no se adjudicaron y 21.469 porque no publicaron clasificación |
| anio, mes, anio_mes | Derivados de fecha | anio es la columna de partición del Parquet |
| adjudicado | Si tiene proveedor | 146.025 sí, 31.373 no |
| n_postores_imputado | Si el número de postores se imputó | Verdadero en 6.655. Ver la sección 9 |
| monto_outlier | Si el monto quedó fuera del rango de Tukey | Verdadero en 565, y se conservan |

## 5. El código CUBSO, dígito por dígito

**CUBSO** es el Catálogo Único de Bienes, Servicios y Obras, el catálogo oficial con el que el Estado peruano nombra lo que contrata. Es importante entender que **incluye servicios y obras y no solo bienes**, porque de ahí salen ítems como servicio de alquiler de excavadora hidráulica.

El código tiene **16 dígitos** y es jerárquico:

| Tramo | Qué identifica | Ejemplo con 8013150200094959 |
| --- | --- | --- |
| Dígitos 1 y 2 | Segmento, la gran familia económica | 80, servicios de gestión y administración |
| Dígitos 3 y 4 | Familia dentro del segmento | 13, alquiler de inmuebles |
| Dígitos 5 a 8 | Clase y artículo, el bien o servicio concreto | 1502, servicio de alquiler de inmueble |
| Dígitos 9 a 16 | Correlativo de la ficha concreta del catálogo | 00094959 |

**Los tres niveles que usa el proyecto y por qué cada uno:**

1. **16 dígitos, el código completo.** No se usa. Es casi único por ítem, de modo que el universo sería tan disperso que ningún conjunto alcanzaría el soporte mínimo en la Parte V.
2. **8 dígitos, el prefijo de catálogo.** Es el nivel del campo items y el que se usa para las reglas de productos. Da 4.664 ítems distintos en la tabla analítica, que es un universo minable.
3. **4 dígitos, el rubro.** Es segmento más familia. Se usa en la canasta enriquecida, donde interesa el sector grueso y no el producto exacto, para que las condiciones salgan legibles. Da 368 rubros, repartidos en 56 segmentos.

**Los segmentos más frecuentes**, obtenidos contando las descripciones del propio dato:

| Segmento | Qué agrupa | Ítem más frecuente |
| --- | --- | --- |
| 72 | Construcción y mantenimiento de infraestructura | Servicio de mantenimiento rutinario de caminos |
| 81 | Servicios de ingeniería y supervisión | Supervisión de obra de construcción de calles |
| 80 | Servicios de gestión, consultoría y alquileres | Servicio de seguimiento y monitoreo de actividades de campo |
| 30 | Materiales de construcción | Cemento Portland puzolánico tipo IP de 42,5 kg |
| 42 | Equipamiento y material médico | Respirador de polipropileno tipo N-95 |
| 50 | Alimentos y bebidas | Leche evaporada entera de 400 g |
| 15 | Combustibles | Diésel B5 S-50 |
| 51 | Medicamentos | Cloruro de sodio al 0,9 por ciento inyectable |
| 41 | Laboratorio y medición | Hemograma automatizado diferencial |
| 78 | Transporte y alquiler de vehículos | Servicio de alquiler de camión volquete |
| 25 | Vehículos | Camioneta pick up cabina doble 4 por 4 |
| 82 | Publicidad, diseño e impresión | Servicio de publicidad en página web |

**Los cuatro rubros que aparecen en los resultados de la Parte V:**

| Rubro | Qué agrupa | Por qué aparece |
| --- | --- | --- |
| 8010 | Consultoría y monitoreo de proyectos de inversión pública | Es el rubro de las condiciones de postor único con Régimen Especial |
| 8013 | Alquiler de inmuebles, locales y oficinas | Postor único con Contratación Directa: el dueño de un local es el único que puede ofrecerlo |
| 8210 | Publicidad y difusión en medios | Postor único con Contratación Internacional |
| 5013 | Leche y derivados | El rubro del Vaso de Leche, que aparece en las reglas de productos |

## 6. Los métodos de contratación

El método es el procedimiento de selección, y es el campo que dice **cuánta competencia preveía la norma**. Por eso es la variable central de la pregunta sobre postor único: comparar el número de postores entre métodos sin tener esto en cuenta es comparar peras con manzanas.

| Método | Procesos | Monto, miles de millones de soles | Postores en promedio | Para qué sirve |
| --- | --- | --- | --- | --- |
| Adjudicación Simplificada | 82.503 | 47,1 | 16,1 | El procedimiento ordinario de monto intermedio, el más usado con diferencia |
| Subasta Inversa Electrónica | 21.150 | 10,0 | 8,2 | Bienes y servicios estandarizados con ficha de catálogo, donde solo se compite por precio |
| Comparación de Precios | 12.555 | 0,9 | 3,1 | Bienes y servicios de disponibilidad inmediata y bajo monto |
| Contratación Directa | 11.049 | 14,5 | 1,2 | Excepcional y con causal: desabastecimiento, emergencia, proveedor único o servicio personalísimo |
| Licitación Pública Abreviada | 9.601 | 6,3 | 13,6 | Versión abreviada de la licitación, solo en 2025 |
| Licitación Pública | 9.242 | 106,6 | 21,0 | Bienes y obras de mayor monto. Es el 5 por ciento de los procesos y el mayor monto del dataset |
| Concurso Público Abreviado | 8.926 | 1,9 | 14,6 | Versión abreviada del concurso, solo en 2025 |
| Concurso Público | 6.627 | 27,1 | 26,1 | Servicios y consultorías de mayor monto. El más competido de todos |
| Régimen Especial | 4.367 | 4,8 | 1,6 | Procedimientos sujetos a un régimen propio o excluidos del régimen general |
| Convenio | 4.009 | 10,3 | 2,0 | Convenios marco y convenios entre entidades |
| Contratación Internacional | 2.981 | 1,4 | 1,1 | Contratación en el exterior o con organismos internacionales |
| Concurso Público de Servicios | 974 | 2,9 | 25,0 | Variante del concurso, solo en 2025 |

**Un hallazgo del propio dato que conviene saber explicar.** Licitación Pública Abreviada, Concurso Público Abreviado y Concurso Público de Servicios tienen **cero procesos en 2023 y 2024 y aparecen enteros en 2025**, con 19.501 procesos entre los tres. Al mismo tiempo la Adjudicación Simplificada cae de 33.201 en 2024 a 12.919 en 2025. Es decir que **hay un cambio de régimen normativo dentro de la ventana de análisis**, el paso a la nueva Ley General de Contrataciones Públicas, y la serie por método no es comparable de punta a punta. Cualquier conclusión que mezcle métodos a lo largo de los tres años tiene que decirlo.

## 7. Los niveles de gobierno

**Es un campo derivado, no viene en el dato.** Se construye con una regla sobre el nombre de la entidad, porque OCDS no publica el nivel de gobierno y sin él no se puede comparar una municipalidad con un ministerio. Conviene declararlo abiertamente, porque es una decisión del equipo y tiene un margen de error conocido.

| Nivel | Procesos | Cómo se reconoce |
| --- | --- | --- |
| Gobierno local | 73.456 | El nombre contiene municipalidad o municipio |
| Gobierno regional | 39.776 | Gobierno regional, dirección regional, gerencia regional |
| Gobierno nacional | 29.984 | Ministerio, instituto, superintendencia, organismo, programa, y otros nombres de entidades nacionales |
| Otro | 10.742 | No encaja en ninguna regla, el 6,1 por ciento |
| Empresa del Estado | 8.048 | Sociedad anónima, empresa, entidad prestadora de servicios, Electro, Sedapal, Banco de la Nación |
| Universidad pública | 7.094 | El nombre contiene universidad |
| Fuerzas armadas y policiales | 5.812 | Ejército, Marina, Fuerza Aérea, Policía, ministerios de Defensa e Interior |
| Establecimiento de salud | 2.278 | Hospital, red de salud, red asistencial, Diresa |
| Unidad educativa | 208 | Unidad de gestión educativa local o UGEL |

Las dos cosas que hay que decir si preguntan: que el 6,1 por ciento cae en Otro y que la clasificación es por nombre, de modo que una entidad con un nombre atípico puede quedar mal ubicada. Es suficiente para agregar y comparar, y no lo sería para una afirmación sobre una entidad individual.

## 8. La categoría y el tramo de monto

**Categoría** es el campo de OCDS mainProcurementCategory y tiene tres valores: goods para bienes, services para servicios y works para obras. Están casi empatados en número de procesos, pero no en monto: las obras son el 11 por ciento de los procesos y concentran mucho más dinero por proceso.

**Tramo de monto** no es un campo del dato, es una discretización que el proyecto construye donde hace falta. Se usa en dos sitios con cortes distintos y a propósito:

1. En la Parte I, seis tramos, para describir la competencia a lo largo de toda la escala: menos de 50 mil, 50 a 200 mil, 200 mil a 1 millón, 1 a 5 millones, 5 a 20 millones y más de 20 millones.
2. En la canasta enriquecida de la Parte V, cuatro tramos, porque un algoritmo de patrones frecuentes solo entiende ítems y no puede recibir una variable continua: menos de 50 mil, 50 mil a 500 mil, 500 mil a 5 millones y más de 5 millones.

El monto se trabaja **en escala logarítmica** en casi todas las figuras. No es un adorno: va de cuatro céntimos a 1.135 millones de soles, así que en escala lineal todo el dataset se apelmaza contra el eje y solo se ven los extremos.

## 9. Las marcas y los indicadores derivados

1. **Postor único**, n_postores menor o igual a uno. Es el indicador central del proyecto y la tasa base es del **12,4 por ciento** de los procesos. Atraviesa todos los tramos de monto, y en el tramo de menos de 50 mil soles llega al 57 por ciento. Esa es la pregunta que la Parte I deja abierta y que la Parte V responde.
2. **n_postores_imputado.** El número de postores faltaba en el 8,3 por ciento del dato crudo, y en la tabla final se imputó en 6.655 procesos con la mediana de su propio método, no con la mediana global, porque la competencia depende del procedimiento. La marca existe para poder **excluir esos procesos** cuando el análisis es sobre la competencia misma, y así evitar que la propia imputación genere el patrón. La Parte V la usa exactamente para eso.
3. **monto_outlier.** Se marca con el criterio de Tukey sobre el logaritmo del monto y factor 3, lo que da un rango de 584 soles a 65 millones. Quedan fuera 565 procesos, el 0,3 por ciento, y **se conservan**: un contrato de mil millones de soles no es un error de digitación, es la obra grande del año, y borrarlo sería borrar el objeto de estudio.
4. **Gini del monto, 0,857.** Mide la desigualdad en el reparto del dinero. Cero sería reparto perfectamente igual y uno sería que todo el monto está en un solo proceso. El 1 por ciento de los procesos concentra el 47,1 por ciento del monto, y el 10 por ciento concentra el 80,2 por ciento. Es la curva de Lorenz de la Parte I.
5. **Fraccionamiento.** No se mide directamente, pero n_proveedores mayor que uno y la coocurrencia mensual de la Parte V son las dos señales que lo rodean.

## 10. Confusiones frecuentes y cómo responderlas

1. **El monto no es lo que se pagó.** monto_pen es el valor referencial de la convocatoria. El monto adjudicado existe en awards.csv y se usa para elegir la adjudicación principal, pero la cifra que recorre las figuras es la del proceso. Decir que el Estado gastó tanto es impreciso; lo correcto es que convocó procesos por ese valor.
2. **Un proceso no es un contrato.** Un proceso puede terminar en varios contratos, quedar desierto o ser anulado. El grano del proyecto es el proceso.
3. **El departamento es el de la entidad.** Un ministerio con sede en Lima que financia una obra en Puno aparece en Lima. Por eso Lima tiene el 30 por ciento de los procesos.
4. **La fecha es la de convocatoria, no la de publicación del paquete.** Son dos campos distintos y la diferencia importa: 81.234 filas del dato crudo quedan fuera de la ventana de 2023 a 2025, casi todas por ser anteriores, y se descartan para que la serie temporal mida actividad y no republicación.
5. **Postor único no es irregularidad.** En Contratación Directa, Régimen Especial o Contratación Internacional es administrativamente esperable, y en el alquiler de un inmueble es inevitable. El análisis entrega una lista priorizada de dónde mirar, no una conclusión sobre conducta.
6. **Nada de esto es una afirmación sobre una entidad o un proveedor concreto.** Son asociaciones estadísticas sobre datos de publicación. En contratación pública esa distinción no es un formalismo: confundirla convierte un ejercicio de minería en una acusación sin sustento.

## 11. Cifras que conviene tener en la cabeza

| Cifra | Valor |
| --- | --- |
| Procesos en la tabla analítica | 177.398 |
| Período | 2023 a 2025 |
| Entidades compradoras distintas | 2.968 |
| Proveedores distintos | 67.510 |
| Ítems CUBSO distintos, a 8 dígitos | 4.664 |
| Rubros distintos, a 4 dígitos | 368 |
| Monto mediano de un proceso | 178 mil soles |
| Monto máximo de un proceso | 1.135 millones de soles |
| Postores en la mediana | 9 |
| Procesos con un solo postor | 12,4 por ciento |
| Procesos sin adjudicación | 31.373, el 17,7 por ciento |
| Gini del monto | 0,857 |
| Tablas OCDS usadas, de 21 | 5 |

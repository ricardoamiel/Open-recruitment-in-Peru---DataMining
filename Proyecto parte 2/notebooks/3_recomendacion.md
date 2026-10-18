# Notebook 3. Sistemas de recomendación

Guía de estudio del notebook [3_recomendacion.ipynb](3_recomendacion.ipynb). Recorre el notebook sección por sección, explica por dentro cada técnica, interpreta cada figura, dice qué se descartó y por qué, y cierra con las preguntas previsibles de la sustentación.

**Integrantes:** Ricardo Acuña, Juan Aquino y Camilo Soto.

## 1. Qué responde esta parte

**Pregunta 2 del proyecto:** ¿es predecible con quién contrata una entidad, y qué relaciones se salen de lo esperable?

**El encuadre, que hay que saber defender.** El recomendador no se construye para decirle a una entidad a quién contratar: eso sería prescriptivo y ajeno a la ley de contrataciones, que exige elegir por concurso. Se construye como **modelo del mercado**. Si predice bien las relaciones nuevas de un año a partir de los anteriores, entonces su puntaje mide qué tan esperable es cada relación, y eso es lo que le interesa a quien supervisa.

**Los tres hallazgos:**

1. **Las relaciones nuevas siguen patrones que se pueden modelar.** El híbrido recupera el 10 por ciento de las relaciones nuevas de 2025 en su lista de diez, con una precisión 361 veces la del azar y un NDCG 32 por ciento mayor que la popularidad regional.
2. **Una relación improbable no es, por sí sola, una relación con menos competencia.** Es un resultado negativo, y por eso cambia cómo debe usarse el modelo.
3. **Los factores latentes revelan sustitutos de mercado** útiles para ampliar la competencia.

**Dónde corre.** El ALS de MLlib en Spark; vecindario, contenido y evaluación en local con numpy y scipy.

## 2. El vocabulario mínimo

1. **Usuario e ítem.** Aquí el usuario es la entidad y el ítem es el proveedor.
2. **Matriz de utilidad.** Entidades por proveedores, con la señal en cada celda conocida.
3. **Señal implícita.** No hay calificaciones; hay adjudicaciones. Una celda vacía no es un rechazo, es desconocimiento.
4. **Arranque en frío.** Un usuario o ítem sin historia no tiene fila en la matriz y el filtrado colaborativo no puede decir nada de él.
5. **Precisión en 10.** De las diez recomendaciones, qué fracción resultó relevante.
6. **Recall en 10.** De las relaciones relevantes de la entidad, qué fracción aparece en sus diez recomendaciones.
7. **NDCG en 10.** Como el recall, pero premia que los aciertos estén arriba en la lista: cada acierto se descuenta por el logaritmo en base 2 de su posición más uno, y se divide por el máximo posible.
8. **Cobertura.** Qué fracción del catálogo aparece en alguna recomendación.

## 3. Recorrido sección por sección

### Sección 1. La matriz y la partición temporal

**Entrenamiento con 2023 y 2024, prueba con 2025.** Una partición aleatoria de celdas sería tramposa: dejaría en el entrenamiento adjudicaciones de 2025 que ayudan a predecir otras del mismo año. La temporal reproduce el uso real.

**Qué se predice: solo relaciones nuevas.** Pares de 2025 que no existían en el entrenamiento. Predecir una repetición es trivial y no necesita un recomendador.

**La señal:** log(1 + n), con n las adjudicaciones del par, para que una entidad que contrata cien veces al mismo proveedor no domine la similitud.

La matriz de entrenamiento tiene 2.828 entidades por 48.380 proveedores, 80.033 celdas, densidad de 0,058 por ciento. 2.129 entidades tienen al menos una relación nueva predecible.

**Figura f16.** Qué tipo de relación es cada par de 2025:

| Tipo | Pares | Porcentaje |
| --- | --- | --- |
| Se repite de 2023 o 2024 | 9.861 | 26,3 % |
| Nuevo, proveedor sin historia | 16.155 | 43,0 % |
| Nuevo, entidad sin historia | 97 | 0,3 % |
| Nuevo y predecible | 11.416 | 30,4 % |

**Lectura para un gerente:** el 43 por ciento de las relaciones de 2025 son con proveedores que no habían ganado nada en los dos años anteriores. Es el arranque en frío, y ningún filtrado colaborativo puede anticiparlo. También es una buena noticia para la competencia: cada año entra una fracción grande de proveedores nuevos al mercado estatal.

### Sección 2. Líneas base

1. **Popularidad global:** los proveedores con más entidades distintas, iguales para todos.
2. **Popularidad en el departamento:** los proveedores con más entidades en el departamento de la entidad. Es la línea base honesta, porque la mayoría de proveedores opera en su región.

Todos los métodos se evalúan igual: diez recomendaciones por entidad, excluyendo los proveedores que ya contrató, contra sus relaciones nuevas de 2025.

### Sección 3. Vecindario usuario a usuario

**Cómo funciona, la versión de la lecture.** Para cada entidad x se buscan las k entidades más similares por coseno, N(x). El puntaje de un proveedor i es el promedio de las señales de los vecinos ponderado por la similitud: la suma de s(x, y) por r(y, i) sobre los vecinos, dividida entre la suma de los valores absolutos de s(x, y).

**Por qué usuario a usuario y no ítem a ítem.** La lecture recomienda ítem a ítem porque en un comercio los ítems son pocos y estables. Aquí es al revés: 2.828 entidades y 48.380 proveedores, la mayoría con un solo cliente. La similitud entre dos proveedores casi siempre se calcularía sobre una o ninguna entidad en común. La matriz entidad por entidad es pequeña y cabe entera en memoria: 0,2 segundos en numpy.

**Por qué coseno y no Pearson.** Pearson centra las calificaciones para corregir a usuarios generosos o exigentes. Con señal implícita no hay calificaciones bajas: una celda vacía no es un rechazo, y restar la media convertiría todas las celdas vacías en valoraciones negativas.

**Elección de k por validación interna.** Entrenar con 2023 y predecir las relaciones nuevas de 2024, sin tocar 2025:

| k | NDCG de validación |
| --- | --- |
| 10 | 0,058 |
| 25 | 0,075 |
| 50 | 0,081 |
| 100 | 0,081 |
| 200 | 0,080 |

Se adopta k = 50. Con pocos vecinos el promedio es ruidoso; con muchos, se diluye con entidades poco parecidas.

### Sección 4. Basado en contenido

**Cómo funciona.** Cada proveedor es un documento cuyos términos son las familias CUBSO que vende y los departamentos donde gana: 358 familias y 25 departamentos. Se pondera con **TF-IDF** como en la lecture: TF es la frecuencia del término normalizada por la máxima del proveedor, e IDF es log(N / n_i), con n_i el número de proveedores que tienen el término. Una familia que vende casi todo el mundo pesa poco; una rara pesa mucho. El perfil de la entidad es el promedio de los vectores de los proveedores que contrató, ponderado por su señal, y la predicción es el coseno entre los dos perfiles.

**Su resultado, y por qué.** Es el peor método, con NDCG de 0,0105, por debajo incluso de la popularidad global. Miles de proveedores comparten la misma familia y el mismo departamento, así que sus perfiles son casi idénticos y el coseno no puede ordenarlos entre sí. Su virtud es la cobertura: es el que más catálogo recomienda, el 15 por ciento.

### Sección 5. Factores latentes con ALS de Spark MLlib

**La idea, de la lecture.** Cada entidad y cada proveedor reciben un vector de r factores, y la predicción es su producto punto. Los factores no se definen a mano: emergen del dato.

**Por qué no la SVD directa.** La SVD clásica necesita una matriz completa, y la nuestra tiene el 99,94 por ciento vacío. Imputar ceros introduce sesgo.

**Por qué ALS implícito y no el descenso de gradiente de la lecture.** El descenso de gradiente con sesgos minimiza el error sobre calificaciones conocidas. Aquí no hay calificaciones. El ALS implícito de Hu, Koren y Volinsky, que MLlib implementa con implicitPrefs, trata cada celda como una preferencia binaria, 1 si hubo contrato y 0 si no, con una **confianza** de 1 más alfa por la señal: los ceros cuentan, pero poco. Alterna entre fijar los factores de proveedor y resolver los de entidad por mínimos cuadrados, y viceversa; cada paso es un problema cerrado por fila, y por eso se paraleliza.

**Validación de hiperparámetros:** rango 16 o 48, regularización 0,01 o 0,1, alfa 5 o 20. El mejor fue rango 48 con alfa 20, NDCG de validación de 0,087. Más factores ayudan; la regularización casi no cambia el resultado.

Ajustar ALS en Spark toma unos 22 segundos.

### Sección 6. Recomendador híbrido

**Cómo combina.** Los puntajes de cada método se estandarizan por entidad, restando su media y dividiendo entre su desviación, y se suman. Se incluye la popularidad en el departamento como cuarta señal. **No se ajustan pesos**, para no sobreajustar a la validación.

**Resultados en 2025:**

| Método | Precisión en 10 | Recall en 10 | NDCG en 10 | Cobertura |
| --- | --- | --- | --- | --- |
| Popularidad global | 0,012 | 0,026 | 0,022 | 0,04 % |
| Popularidad en el departamento | 0,028 | 0,080 | 0,066 | 0,77 % |
| Vecindario, k = 50 | 0,035 | 0,083 | 0,076 | 7,5 % |
| Contenido, TF-IDF | 0,005 | 0,014 | 0,011 | 15,0 % |
| ALS implícito, rango 48 | 0,033 | 0,088 | 0,071 | 4,0 % |
| **Híbrido** | **0,040** | **0,104** | **0,088** | 6,0 % |

**Figura f17.** NDCG por método y recall frente a cobertura. **Cómo decirlo en voz alta:** de cada cien proveedores que el híbrido propone, 4 son contratados por primera vez por esa entidad en 2025. Parece poco, pero el catálogo tiene 48.380 proveedores y una lista al azar acertaría 0,011 de cada cien: el híbrido es 361 veces mejor.

**Ablación: qué aporta cada señal.**

| Sin la señal | NDCG | Cambio |
| --- | --- | --- |
| Vecindario | 0,078 | menos 11,1 % |
| Departamento | 0,083 | menos 5,6 % |
| Contenido | 0,086 | menos 2,3 % |
| ALS | 0,086 | menos 2,0 % |

El vecindario es la señal que más aporta. El contenido, que solo es el peor método, todavía suma un 2 por ciento al híbrido, porque se equivoca en casos distintos. **Esa es la lección del premio Netflix que cierra la lecture:** combinar modelos que fallan distinto gana a cualquiera de ellos.

**Spark o local, con números.** ALS se queda en Spark porque su paso de mínimos cuadrados alternos se reparte por bloques y es lo que escalaría a millones de entidades y proveedores sin cambiar el código. El vecindario necesita solo la matriz de similitud entre 2.828 entidades, que numpy calcula en 0,2 segundos; en Spark exigiría un autojoin distribuido para lo mismo. El contenido es un producto de matrices de unos cientos de columnas.

### Sección 7. Interpretación

**7.1 Relaciones nuevas improbables.** Para cada relación nueva de 2025 se calcula en qué percentil de los puntajes híbridos de su entidad cae el proveedor contratado. Percentil bajo significa que nada en la historia de la entidad, de las entidades parecidas ni del rubro la anticipaba.

La pregunta es si esa sorpresa dice algo más allá del modelo. Se contrasta con dos variables que **el modelo nunca vio**, postor único y contratación sin concurso, entre las 682 relaciones improbables, debajo del percentil 50, y las 8.441 esperadas, desde el percentil 95, con una prueba de dos proporciones.

| Variable | Improbables | Esperadas | Valor p |
| --- | --- | --- | --- |
| Postor único | 5,9 % | 5,3 % | 0,56 |
| Sin concurso | 7,2 % | 6,3 % | 0,38 |

**Figura f18.** Porcentaje con postor único y sin concurso por tramo de percentil. Las diferencias van en la dirección esperada pero no son significativas.

**Cómo contar este resultado negativo, porque es una fortaleza y no una debilidad.** Una primera versión del análisis comparaba porcentajes a ojo y concluía que lo inesperado se gana sin competencia. Al aplicar la prueba estadística, la diferencia resultó compatible con el azar. Lo correcto es decirlo: la sorpresa del modelo, por sí sola, no anticipa menos competencia. **Acción que se deriva:** no usar el percentil como alerta aislada, sino para ordenar, dentro de las adjudicaciones que ya son sin concurso o con un solo postor, cuáles además son relaciones que nada en el mercado anticipaba. La tabla p3_inusuales lista las de mayor monto; la primera es una adjudicación del Ministerio de Salud a una oficina de Naciones Unidas, sin concurso y con un solo postor, que tiene una explicación institucional evidente y muestra por qué la señal requiere revisión humana.

**7.2 Proveedores sustitutos.** Los factores de ALS ubican cerca a los proveedores que atienden a las mismas entidades. Los vecinos de un proveedor son sus **sustitutos de mercado**.

**Validación sin trampa.** Se mide si los diez vecinos comparten la familia CUBSO principal del proveedor, y el modelo nunca vio las familias. Resultado: 14,7 por ciento frente a 2,5 por ciento al azar, casi seis veces.

**Un detalle que hay que saber explicar.** Solo se comparan proveedores con cinco o más entidades. En una primera versión, el ejemplo daba ocho sustitutos con similitud idéntica de 0,814: eran proveedores de un solo cliente, cuyo vector en ALS es casi el mismo que el de ese cliente, y por eso todos los proveedores de esa entidad salían como sustitutos perfectos entre sí.

**Acción.** Cuando una entidad depende de un proveedor cautivo de la Parte II, usar sus sustitutos de mercado como lista de invitación a cotizar en el siguiente estudio de mercado. Amplía la competencia sin prescribir un ganador.

**Exportación.** Los factores de ALS de entidades y proveedores quedan en data/processed como archivos numpy, con sus índices, para usarlos como embeddings en la Parte VI. La curva de recall y precisión según el número de recomendaciones queda en artifacts/p3_curva_k para el reporte web.

## 4. Técnicas consideradas y descartadas

1. **Partición aleatoria de celdas.** Filtra información del futuro al entrenamiento.
2. **Evaluar también las repeticiones.** Inflaría las métricas con lo trivial.
3. **Ítem a ítem.** La mayoría de proveedores tiene un solo cliente; su similitud no tiene base.
4. **Pearson.** Con señal implícita convierte las celdas vacías en rechazos.
5. **SVD directa y descenso de gradiente con calificaciones.** Suponen calificaciones explícitas o una matriz completa.
6. **Ajustar pesos del híbrido.** Riesgo de sobreajuste a la validación con una ganancia marginal.
7. **Búsqueda aproximada de vecinos, IVF o HNSW, para el contenido.** Con 48 mil proveedores y 383 términos el producto exacto es inmediato; se justificaría con millones.
8. **Usar el percentil del modelo como alerta aislada.** La prueba de dos proporciones mostró que no anticipa menos competencia.

## 5. Preguntas previsibles y su respuesta

**¿Una precisión de 0,04 no es muy baja?** En un catálogo de 48.380 proveedores, el azar da 0,0001. El híbrido es 361 veces mejor. Las métricas de recomendación con catálogos grandes y relaciones nuevas son bajas en términos absolutos; lo que importa es la comparación con las líneas base.

**¿Por qué recomendar proveedores no es prescriptivo?** Porque el modelo no se usa para sugerir contrataciones, sino para medir qué tan esperable es una relación. Es una herramienta de análisis del mercado.

**¿Por qué el contenido sale tan mal?** Porque familia y departamento no distinguen entre los miles de proveedores que los comparten. Aun así aporta al híbrido, porque se equivoca en casos distintos.

**¿Qué hace alfa en ALS implícito?** Controla cuánto más pesa una celda con contratos que una vacía. La confianza es 1 más alfa por la señal.

**¿Por qué no publicar el resultado de la sorpresa como un hallazgo positivo?** Porque no es significativo. Presentarlo como positivo sería sobreinterpretar ruido, y el enunciado pide encuadre ético: con datos de compras públicas, una conclusión débil puede convertirse en una acusación injusta.

**¿Por qué Spark solo para ALS?** Se midió: ALS en Spark tarda 22 segundos y es la parte que escala por bloques; el vecindario en numpy tarda 0,2 segundos y en Spark necesitaría un autojoin distribuido.

**¿Cómo se usaría esto en el SEACE?** Con un puntaje por relación nueva al momento de la adjudicación, que se combine con las alertas existentes de postor único o contratación directa para ordenar la revisión.

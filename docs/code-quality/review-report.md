# Код-рев'ю Spectrum

Об'єкт огляду: [Spectrum-project](https://github.com/ukma-fin-ssdm-2026/Spectrum-project), коміт [`5c6b1703c9f42d779fa66dd92575cd275134406b`](https://github.com/ukma-fin-ssdm-2026/Spectrum-project/tree/5c6b1703c9f42d779fa66dd92575cd275134406b). Оновлено 31.10.2026 за вихідним кодом цього коміту; висновки не описують пізніші версії. Перевірено контролер готелів, DTO, обробник валідації, конфігурацію застосунку, Maven і CI. Застосунок Spectrum під час оновлення не запускався.

## 3 сильні сторони

1. **Валідація запитів на межі API.** У [CreateHotel.java:10–15][create-hotel] назва обов'язкова й обмежена 3–40 символами, адреса обов'язкова та перевіряється каскадно через `@Valid`. [HotelController.java:45–48][create-handler] застосовує `@Valid @NotNull` до тіла запиту. У [PaginationParams.java:9–11][pagination] задано `page >= 0` і `1 <= limit <= 100`. Це централізує перевірки та обмежує розмір однієї відповіді списку.

2. **Явна обробка помилок валідації та відсутнього ресурсу.** [ValidationExceptionMapper.java:13–29][mapper] перетворює `ConstraintViolationException` на HTTP `400` зі списком полів і повідомлень у `ValidationError`. Клієнт може прив'язати повідомлення до конкретних полів форми. [HotelController.java:81–91][get-hotel] окремо повертає `404`, якщо готелю немає, і `200` для знайденого готелю. Тіло `404` порожнє — уніфікація формату лишається пропозицією нижче.

3. **Автоматична перевірка форматування у CI.** [.github/workflows/formatting-check.yml:3–27][format-ci] запускає `./mvnw -B spotless:check` на відкритті й оновленні PR до `main`. [pom.xml:119–153][spotless] фіксує Spotless і Google Java Format та задає `ratchetFrom=origin/main`. Це дає відтворюваний стиль для зміненого коду й зменшує кількість стилістичних зауважень під час рев'ю. Наявність workflow не підтверджує, що його перевірка обов'язкова в налаштуваннях захисту гілки.

## 3 пропозиції покращення

1. **Доповнити опис параметрів і відповідей OpenAPI.** У [PaginationParams.java:9–11][pagination] є межі й значення за замовчуванням, але немає пояснення нумерації `page` з нуля та прикладів запитів. Для `hotelId` у [HotelController.java:81–91][get-hotel] немає окремого опису параметра, а відповідь `404` не має схеми тіла. Додати описи й приклади через OpenAPI-анотації, визначити спільну модель помилки та узгодити з нею фактичну відповідь `404`. Це зробить контракт зрозумілим без читання Java-коду; результат слід перевірити у згенерованій специфікації та контрактних тестах.

2. **Документувати нетривіальні рішення й відокремити зберігання від HTTP-обробників.** [HotelController.java:28–48][controller] одночасно містить REST-контракт, `ConcurrentHashMap`, створення доменної сутності та запис даних. Публічний клас і метод не мають Javadoc, який пояснив би тимчасовий характер сховища та очікуваний життєвий цикл даних. Винести операції у сервіс і репозиторій, задати їхній scope та задокументувати інваріанти й обмеження зберігання. Це спростить заміну сховища і незалежне тестування логіки. Початкове формулювання «відсутні коментарі» було надто широким: наприклад, у [ValidationExceptionMapper.java:22–25][mapper-comment] коментар уже є; потрібні пояснення рішень, а не коментар до кожного рядка.

3. **Забезпечити стабільну та масштабовану пагінацію `getHotels`.** У [HotelController.java:61–69][get-hotels] використано `hotels.values().stream().skip(page * limit).limit(limit)` без сортування. Контракт не задає стабільного порядку, а конкурентні зміни можуть спричинити пропуски чи повтори між сторінками; окремий `size()` також не утворює спільного з вибіркою знімка. Для далеких сторінок `skip` мусить пройти попередні елементи. Для прототипу варто робити впорядкований знімок із унікальним ключем сортування; після переходу на БД — виконувати вибірку в репозиторії з явним `ORDER BY`, індексом і, за потреби, курсорною пагінацією. Додати тести меж сторінок, стабільності порядку та поведінки при змінах даних.

## 1 потенційна вразливість або ризик

**Створення готелів без контролю доступу.** [HotelController.java:28–48][controller] оголошує `POST /v1/hotels` і без перевірки користувача записує надані дані у сховище. У класі немає захисних анотацій, у [application.properties:1–5][properties] — правил HTTP-авторизації, а в [pom.xml:33–71][dependencies] — залежностей механізму автентифікації. Це висновок з огляду вихідного коду, а не результат атаки на розгорнутий сервіс; зовнішній шлюз у межах огляду не перевірявся.

Якщо API доступне з мережі без додаткового захисту, сторонній клієнт може створювати довільні записи та засмічувати сховище. Пропозиція: визначити політику доступу до читання й запису, додати автентифікацію та рольову перевірку для створення готелів. Перевірка виправлення: запит без облікових даних отримує `401`, користувач без потрібної ролі — `403`, уповноважений користувач — `201`. Ризик стосується готелів; дошок і карток у цьому контролері немає.

## Додаткове завдання: порівняння з AI Review

1. Початковий ШІ-огляд збігся з командою щодо валідації, обробки помилок і форматування. Підстави — [CreateHotel.java:10–15][create-hotel], [ValidationExceptionMapper.java:13–29][mapper] і [formatting-check.yml:3–27][format-ci]; їхні переваги та межі розгорнуто вище.
2. ШІ додатково запропонував розділити відповідальності `HotelController`: поле сховища та запис у нього справді видно в [HotelController.java:28–48][controller]. Рекомендацію включено до пропозиції 2.
3. ШІ деталізував відсутність гарантованого порядку пагінації та неповну документацію помилок. Висновки уточнено за [HotelController.java:61–69][get-hotels] і [81–91][get-hotel] у пропозиціях 1 і 3.
4. Хибне зауваження ШІ про «операції з дошками й картками» відхилено: [HotelController.java:28–48][controller] визначає ресурс готелів. У розділі ризиків залишено лише підтверджений кодом сценарій створення готелю.

## Використання ШІ

- **Попередній запис:** у вихідному звіті вже було зазначено Gemini як допоміжний інструмент структурування та формулювання критеріїв. Модель, що створила наведений там окремий AI Review, не була уточнена.
- **Оновлення 31.10.2026 — інструмент:** Codex.
- **Застосування:** розгортання семи пунктів огляду, уточнення впливу та рекомендацій, виправлення помилкової предметної області й додавання посилань на файли та рядки.
- **Верифікація:** вихідні файли прочитано через `git show` на зафіксованому SHA; посилання прив'язано до цього SHA. Runtime-перевірки та запропоновані тести Spectrum не виконувалися. Оновлення не означає нового затвердження звіту командою.

[create-hotel]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/hotel/CreateHotel.java#L10-L15
[create-handler]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/hotel/HotelController.java#L45-L48
[pagination]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/common/page/PaginationParams.java#L9-L11
[mapper]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/common/error/ValidationExceptionMapper.java#L13-L29
[get-hotel]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/hotel/HotelController.java#L81-L91
[format-ci]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/.github/workflows/formatting-check.yml#L3-L27
[spotless]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/pom.xml#L119-L153
[controller]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/hotel/HotelController.java#L28-L48
[mapper-comment]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/common/error/ValidationExceptionMapper.java#L22-L25
[get-hotels]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/java/edu/ukma/ssdm/teamspectrum/api/hotel/HotelController.java#L61-L69
[properties]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/src/main/resources/application.properties#L1-L5
[dependencies]: https://github.com/ukma-fin-ssdm-2026/Spectrum-project/blob/5c6b1703c9f42d779fa66dd92575cd275134406b/spectrum-app/pom.xml#L33-L71
